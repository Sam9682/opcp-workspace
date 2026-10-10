import { useState, useEffect } from 'react';
import { adminService, type User } from '../services/adminService';
import { useTranslation } from '../hooks/useLanguage';

export const AdminUsersPage = () => {
  const { t } = useTranslation();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    first_name: '',
    last_name: '',
    role: 'member',
    password: '',
    membership_expires_at: '',
    membership_status: '',
  });

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const response = await adminService.listUsers();
      setUsers(response.members);
    } catch (error) {
      console.error('Failed to load users:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    const expiresAt = user.membership_expires_at 
      ? new Date(user.membership_expires_at).toISOString().slice(0, 16)
      : '';
    setFormData({
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      role: user.role,
      password: '',
      membership_expires_at: expiresAt,
      membership_status: user.membership_status,
    });
  };

  const handleStatusChange = (newStatus: string) => {
    setFormData({ ...formData, membership_status: newStatus });
  };

  const handleSave = async () => {
    if (!editingUser) return;
    try {
      await adminService.updateUserRole(editingUser.id, formData.role);
      const membershipExpiresAt = formData.membership_expires_at 
        ? new Date(formData.membership_expires_at).toISOString()
        : null;
      await adminService.updateMembershipStatus(editingUser.id, membershipExpiresAt, formData.membership_status);
      const previousStatus = editingUser.membership_status;
      const newStatus = formData.membership_status;
      if ((previousStatus === 'pending' || previousStatus === 'expired') && newStatus === 'active') {
        await adminService.updateEmailVerification(editingUser.id, true);
      }
      setEditingUser(null);
      loadUsers();
    } catch (error) {
      console.error('Failed to update user:', error);
    }
  };

  const handleDelete = async (userId: string) => {
    if (!confirm(t('page.adminUsers.confirm.deactivate'))) return;
    try {
      await adminService.deleteUser(userId);
      loadUsers();
    } catch (error) {
      console.error('Failed to delete user:', error);
    }
  };

  const handleCreate = async () => {
    try {
      await adminService.createUser({
        email: formData.email,
        password: formData.password,
        first_name: formData.first_name,
        last_name: formData.last_name,
        role: formData.role,
      });
      setShowCreateModal(false);
      setFormData({ email: '', first_name: '', last_name: '', role: 'member', password: '', membership_expires_at: '', membership_status: '' });
      loadUsers();
    } catch (error) {
      console.error('Failed to create user:', error);
    }
  };

  if (loading) {
    return <div className="text-center py-8 text-gray-500">{t('page.adminUsers.loading')}</div>;
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
        <h1 className="text-2xl font-bold text-[#000E9C]">{t('page.adminUsers.title')}</h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 text-sm font-medium bg-[#000E9C] text-white rounded hover:bg-[#4949FF] transition-colors"
        >
          {t('page.adminUsers.newUser')}
        </button>
      </div>

      <div className="card overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('page.adminUsers.col.email')}</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('page.adminUsers.col.lastName')}</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('page.adminUsers.col.firstName')}</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('page.adminUsers.col.role')}</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('page.adminUsers.col.status')}</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('page.adminUsers.col.actions')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {users.map((user) => (
              <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 text-sm text-gray-900">{user.email}</td>
                <td className="px-4 py-3 text-sm text-gray-700">{user.last_name}</td>
                <td className="px-4 py-3 text-sm text-gray-700">{user.first_name}</td>
                <td className="px-4 py-3 text-sm">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    user.role === 'administrator' ? 'bg-purple-100 text-purple-800' :
                    user.role === 'member' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {user.role}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    user.membership_status === 'active' ? 'bg-green-100 text-green-800' :
                    user.membership_status === 'expired' ? 'bg-red-100 text-red-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {user.membership_status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm space-x-3">
                  <button onClick={() => handleEdit(user)} className="text-xs font-medium text-[#4949FF] hover:underline">
                    {t('page.adminUsers.action.edit')}
                  </button>
                  <button onClick={() => handleDelete(user.id)} className="text-xs font-medium text-red-600 hover:underline">
                    {t('page.adminUsers.action.deactivate')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Edit Modal */}
      {editingUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-[#000E9C] mb-4">{t('page.adminUsers.edit.title')}</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminUsers.field.email')}</label>
                <input type="email" value={formData.email} disabled className="w-full px-3 py-2 border border-gray-300 rounded text-sm bg-gray-50 text-gray-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminUsers.field.role')}</label>
                <select value={formData.role} onChange={(e) => setFormData({ ...formData, role: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent">
                  <option value="visitor">{t('page.adminUsers.role.visitor')}</option>
                  <option value="member">{t('page.adminUsers.role.member')}</option>
                  <option value="administrator">{t('page.adminUsers.role.administrator')}</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminUsers.field.membershipStatus')}</label>
                <select value={formData.membership_status} onChange={(e) => handleStatusChange(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent">
                  <option value="pending">{t('page.adminUsers.status.pending')}</option>
                  <option value="active">{t('page.adminUsers.status.active')}</option>
                  <option value="expired">{t('page.adminUsers.status.expired')}</option>
                </select>
                {editingUser && 
                 (editingUser.membership_status === 'pending' || editingUser.membership_status === 'expired') && 
                 formData.membership_status === 'active' && (
                  <p className="text-xs text-green-600 mt-1">{t('page.adminUsers.emailAutoVerified')}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminUsers.field.expiration')}</label>
                <input type="datetime-local" value={formData.membership_expires_at} onChange={(e) => setFormData({ ...formData, membership_expires_at: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
                <p className="text-xs text-gray-500 mt-1">{t('page.adminUsers.expiration.hint')}</p>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => setEditingUser(null)} className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded hover:bg-gray-50 transition-colors">
                  {t('page.adminUsers.cancel')}
                </button>
                <button onClick={handleSave} className="px-4 py-2 text-sm font-medium text-white bg-[#000E9C] rounded hover:bg-[#4949FF] transition-colors">
                  {t('page.adminUsers.save')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-bold text-[#000E9C] mb-4">{t('page.adminUsers.create.title')}</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminUsers.field.email')}</label>
                <input type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminUsers.field.firstName')}</label>
                <input type="text" value={formData.first_name} onChange={(e) => setFormData({ ...formData, first_name: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminUsers.field.lastName')}</label>
                <input type="text" value={formData.last_name} onChange={(e) => setFormData({ ...formData, last_name: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminUsers.field.password')}</label>
                <input type="password" value={formData.password} onChange={(e) => setFormData({ ...formData, password: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('page.adminUsers.field.role')}</label>
                <select value={formData.role} onChange={(e) => setFormData({ ...formData, role: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent">
                  <option value="visitor">{t('page.adminUsers.role.visitor')}</option>
                  <option value="member">{t('page.adminUsers.role.member')}</option>
                  <option value="administrator">{t('page.adminUsers.role.administrator')}</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => setShowCreateModal(false)} className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded hover:bg-gray-50 transition-colors">
                  {t('page.adminUsers.cancel')}
                </button>
                <button onClick={handleCreate} className="px-4 py-2 text-sm font-medium text-white bg-[#000E9C] rounded hover:bg-[#4949FF] transition-colors">
                  {t('page.adminUsers.create')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
