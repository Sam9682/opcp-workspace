import { useState, useEffect } from 'react';
import { eventService, type Event } from '../services/eventService';
import { adminService, type User } from '../services/adminService';
import { MultiUserPicker } from '../components/MultiUserPicker';
import { useTranslation } from '../hooks/useLanguage';

/**
 * Extract a human-readable message from an axios error raised by the events
 * API. The backend returns either { detail: { error: { message } } } for
 * business errors or { detail: [ { msg } ] } for Pydantic validation (422).
 * Falls back to the provided default message.
 */
export function extractApiError(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined;
    if (first?.msg) {
      // Pydantic v2 prefixes ValueError messages with "Value error, ".
      // Strip it so the admin sees a natural, specific reason, and prefer
      // this specific message over the generic fallback.
      return first.msg.replace(/^Value error, /, '');
    }
  }
  const nested = (detail as { error?: { message?: string } } | undefined)?.error?.message;
  if (nested) return nested;
  return fallback;
}

export const AdminEventsPage = () => {
  const { t } = useTranslation();
  const [events, setEvents] = useState<Event[]>([]);
  const [members, setMembers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingEvent, setEditingEvent] = useState<Event | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [formData, setFormData] = useState<{
    title: string;
    description: string;
    start_date: string;
    end_date: string;
    location: string;
    max_participants: string;
    assigned_user_ids: string[];
  }>({
    title: '',
    description: '',
    start_date: '',
    end_date: '',
    location: '',
    max_participants: '',
    assigned_user_ids: [],
  });

  const emptyForm = {
    title: '',
    description: '',
    start_date: '',
    end_date: '',
    location: '',
    max_participants: '',
    assigned_user_ids: [] as string[],
  };

  useEffect(() => {
    loadEvents();
    loadMembers();
  }, []);

  const loadEvents = async () => {
    try {
      setLoading(true);
      const data = await eventService.listEvents();
      setEvents(data);
    } catch (error) {
      console.error('Failed to load events:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMembers = async () => {
    try {
      const data = await adminService.listUsers();
      setMembers(data.members);
    } catch (error) {
      console.error('Failed to load members:', error);
    }
  };

  const handleEdit = (event: Event) => {
    setEditError(null);
    setEditingEvent(event);
    setFormData({
      title: event.title,
      description: event.description || '',
      start_date: event.start_date.slice(0, 16),
      end_date: event.end_date.slice(0, 16),
      location: event.location || '',
      max_participants: event.max_participants?.toString() || '',
      assigned_user_ids: event.assigned_user_ids ?? [],
    });
  };

  const handleSave = async () => {
    if (!editingEvent) return;
    setEditError(null);
    try {
      await eventService.updateEvent(editingEvent.id, {
        title: formData.title,
        description: formData.description || undefined,
        start_date: formData.start_date,
        end_date: formData.end_date,
        location: formData.location || undefined,
        max_participants: formData.max_participants ? parseInt(formData.max_participants) : undefined,
        assigned_user_ids: formData.assigned_user_ids,
      });
      setEditingEvent(null);
      loadEvents();
    } catch (error) {
      console.error('Failed to update event:', error);
      setEditError(extractApiError(error, t('page.adminEvents.error.update')));
    }
  };

  const handleDelete = async (eventId: string) => {
    if (!confirm(t('page.adminEvents.confirm.cancel'))) return;
    try {
      await eventService.deleteEvent(eventId);
      loadEvents();
    } catch (error) {
      console.error('Failed to delete event:', error);
    }
  };

  const handleCreate = async () => {
    setCreateError(null);
    try {
      await eventService.createEvent({
        title: formData.title,
        description: formData.description || undefined,
        start_date: formData.start_date,
        end_date: formData.end_date,
        location: formData.location || undefined,
        max_participants: formData.max_participants ? parseInt(formData.max_participants) : undefined,
        assigned_user_ids: formData.assigned_user_ids,
      });
      setShowCreateModal(false);
      setFormData({ ...emptyForm });
      loadEvents();
    } catch (error) {
      console.error('Failed to create event:', error);
      setCreateError(extractApiError(error, t('page.adminEvents.error.create')));
    }
  };

  if (loading) {
    return <div className="text-center py-8 text-gray-500">{t('page.adminEvents.loading')}</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-[#000E9C]">{t('page.adminEvents.title')}</h1>
        <button
          onClick={() => {
            setCreateError(null);
            setFormData({ ...emptyForm });
            setShowCreateModal(true);
          }}
          className="px-4 py-2 text-sm font-medium bg-[#000E9C] text-white rounded hover:bg-[#4949FF] transition-colors"
        >
          {t('page.adminEvents.newEvent')}
        </button>
      </div>

      <div className="grid gap-4">
        {events.map((event) => (
          <div key={event.id} className="card p-5">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900 mb-1">{event.title}</h3>
                {event.description && <p className="text-sm text-gray-600 mb-2">{event.description}</p>}
                <div className="text-xs text-gray-500 space-y-0.5">
                  <p>{t('page.adminEvents.start')} {new Date(event.start_date).toLocaleString('fr-FR')}</p>
                  <p>{t('page.adminEvents.end')} {new Date(event.end_date).toLocaleString('fr-FR')}</p>
                  {event.location && <p>{t('page.adminEvents.location')} {event.location}</p>}
                  <p>{t('page.adminEvents.participants')} {event.participant_count}{event.max_participants ? `/${event.max_participants}` : ''}</p>
                  <p>
                    <span className={`inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium ${
                      event.status === 'scheduled' ? 'bg-green-100 text-green-800' :
                      event.status === 'cancelled' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {event.status}
                    </span>
                  </p>
                </div>
              </div>
              <div className="flex gap-2 ml-4">
                <button
                  onClick={() => handleEdit(event)}
                  className="text-xs font-medium text-[#4949FF] hover:underline"
                >
                  {t('page.adminEvents.action.edit')}
                </button>
                <button
                  onClick={() => handleDelete(event.id)}
                  className="text-xs font-medium text-red-600 hover:underline"
                >
                  {t('page.adminEvents.action.cancel')}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Edit Modal */}
      {editingEvent && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-[#000E9C] mb-4">{t('page.adminEvents.edit.title')}</h2>
            {editError && (
              <div role="alert" className="mb-4 px-3 py-2 rounded bg-red-100 text-red-800 text-sm">
                {editError}
              </div>
            )}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminEvents.field.title')}</label>
                <input type="text" value={formData.title} onChange={(e) => setFormData({ ...formData, title: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminEvents.field.description')}</label>
                <textarea value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" rows={3} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminEvents.field.startDate')}</label>
                  <input type="datetime-local" value={formData.start_date} onChange={(e) => setFormData({ ...formData, start_date: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminEvents.field.endDate')}</label>
                  <input type="datetime-local" value={formData.end_date} onChange={(e) => setFormData({ ...formData, end_date: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminEvents.field.location')}</label>
                <input type="text" value={formData.location} onChange={(e) => setFormData({ ...formData, location: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminEvents.field.maxParticipants')}</label>
                <input type="number" value={formData.max_participants} onChange={(e) => setFormData({ ...formData, max_participants: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
              </div>
              <div>
                <MultiUserPicker
                  users={members}
                  value={formData.assigned_user_ids}
                  onChange={(userIds) => setFormData({ ...formData, assigned_user_ids: userIds })}
                  label={t('page.adminEvents.field.assignees')}
                  placeholder={t('page.adminEvents.assignees.placeholder')}
                  emptyText={t('page.adminEvents.assignees.none')}
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => { setEditError(null); setEditingEvent(null); }} className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded hover:bg-gray-50 transition-colors">
                  {t('page.adminEvents.cancel')}
                </button>
                <button onClick={handleSave} className="px-4 py-2 text-sm font-medium text-white bg-[#000E9C] rounded hover:bg-[#4949FF] transition-colors">
                  {t('page.adminEvents.save')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-[#000E9C] mb-4">{t('page.adminEvents.create.title')}</h2>
            {createError && (
              <div role="alert" className="mb-4 px-3 py-2 rounded bg-red-100 text-red-800 text-sm">
                {createError}
              </div>
            )}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminEvents.field.title')}</label>
                <input type="text" value={formData.title} onChange={(e) => setFormData({ ...formData, title: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminEvents.field.description')}</label>
                <textarea value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" rows={3} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminEvents.field.startDate')}</label>
                  <input type="datetime-local" value={formData.start_date} onChange={(e) => setFormData({ ...formData, start_date: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminEvents.field.endDate')}</label>
                  <input type="datetime-local" value={formData.end_date} onChange={(e) => setFormData({ ...formData, end_date: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminEvents.field.location')}</label>
                <input type="text" value={formData.location} onChange={(e) => setFormData({ ...formData, location: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminEvents.field.maxParticipants')}</label>
                <input type="number" value={formData.max_participants} onChange={(e) => setFormData({ ...formData, max_participants: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
              </div>
              <div>
                <MultiUserPicker
                  users={members}
                  value={formData.assigned_user_ids}
                  onChange={(userIds) => setFormData({ ...formData, assigned_user_ids: userIds })}
                  label={t('page.adminEvents.field.assignees')}
                  placeholder={t('page.adminEvents.assignees.placeholder')}
                  emptyText={t('page.adminEvents.assignees.none')}
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => { setCreateError(null); setShowCreateModal(false); }} className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded hover:bg-gray-50 transition-colors">
                  {t('page.adminEvents.cancel')}
                </button>
                <button onClick={handleCreate} className="px-4 py-2 text-sm font-medium text-white bg-[#000E9C] rounded hover:bg-[#4949FF] transition-colors">
                  {t('page.adminEvents.create')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
