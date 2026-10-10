import { useState, useEffect } from 'react';
import { eventService, type Event } from '../services/eventService';
import { useTranslation } from '../hooks/useLanguage';

/**
 * Member-facing, read-only events view. Mirrors the data-loading pattern and
 * card layout of AdminEventsPage but strips all management controls (create,
 * edit, cancel, member picker). Members see their assigned and public events
 * as scoped by the backend `GET /events` endpoint.
 */
export const EventsPage = () => {
  const { t } = useTranslation();
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadEvents();
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

  if (loading) {
    return <div className="text-center py-8 text-gray-500">{t('page.events.loading')}</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-[#000E9C]">{t('page.events.title')}</h1>
      </div>

      {events.length === 0 ? (
        <div className="text-center py-8 text-gray-500">{t('page.events.empty')}</div>
      ) : (
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
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
