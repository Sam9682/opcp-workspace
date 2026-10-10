import api from './api';

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_email_verified: boolean;
  membership_expires_at: string | null;
  membership_status: string;
  created_at: string;
}

export interface UserListResponse {
  members: User[];
  total: number;
}

export interface UpdateUserRequest {
  email?: string;
  first_name?: string;
  last_name?: string;
  role?: string;
}

export interface CreateUserRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  role: string;
}

export interface LoginLogEntry {
  id: string;
  user_id: string | null;
  user_email: string | null;
  user_name: string | null;
  action: string;
  ip_address: string | null;
  user_agent: string | null;
  reason: string | null;
  timestamp: string;
}

export interface LoginLogResponse {
  entries: LoginLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface LoginLogParams {
  action?: string;
  page?: number;
  page_size?: number;
}

export type AIProviderId = 'shai' | 'kiro' | 'openai' | 'opcp_companion';

export interface AIProviderStatus {
  provider: AIProviderId;
  name: string;
  enabled: boolean;
  always_enabled: boolean;
}

export interface AIProviderConfigResponse {
  providers: AIProviderStatus[];
}

export interface ForumConfig {
  view_button_enabled: boolean;
}

export interface EncryptionConfig {
  enabled: boolean;
  key_is_set: boolean;
}

export const adminService = {
  async listUsers(): Promise<UserListResponse> {
    const response = await api.get('/admin/members');
    return response.data;
  },

  async getLoginLogs(params: LoginLogParams = {}): Promise<LoginLogResponse> {
    const response = await api.get('/admin/login-logs', { params });
    return response.data;
  },

  async updateUserRole(userId: string, role: string): Promise<void> {
    await api.put(`/admin/members/${userId}/role`, { role });
  },

  async updateMembershipStatus(userId: string, membershipExpiresAt: string | null, membershipStatus?: string): Promise<void> {
    const payload: any = { 
      membership_expires_at: membershipExpiresAt 
    };
    if (membershipStatus) {
      payload.membership_status = membershipStatus;
    }
    await api.put(`/admin/members/${userId}/membership-status`, payload);
  },

  async updateEmailVerification(userId: string, isEmailVerified: boolean): Promise<void> {
    await api.put(`/admin/members/${userId}/email-verification`, { 
      is_email_verified: isEmailVerified 
    });
  },

  async deleteUser(userId: string): Promise<void> {
    await api.put(`/admin/members/${userId}/deactivate`);
  },

  async createUser(data: CreateUserRequest): Promise<void> {
    await api.post('/auth/register', {
      email: data.email,
      password: data.password,
      first_name: data.first_name,
      last_name: data.last_name,
    });
  },

  async getAIProviderConfig(): Promise<AIProviderConfigResponse> {
    const response = await api.get('/admin/ai-providers');
    return response.data;
  },

  async updateAIProviderConfig(
    updates: { provider: AIProviderId; enabled: boolean }[]
  ): Promise<AIProviderConfigResponse> {
    const response = await api.put('/admin/ai-providers', { providers: updates });
    return response.data;
  },

  async getForumConfig(): Promise<ForumConfig> {
    const response = await api.get('/admin/forum-config');
    return response.data;
  },

  async updateForumConfig(view_button_enabled: boolean): Promise<ForumConfig> {
    const response = await api.put('/admin/forum-config', { view_button_enabled });
    return response.data;
  },

  async getEncryptionConfig(): Promise<EncryptionConfig> {
    const response = await api.get('/admin/encryption-config');
    return response.data;
  },

  async updateEncryptionConfig(
    password_key: string,
    enabled: boolean
  ): Promise<EncryptionConfig> {
    const response = await api.put('/admin/encryption-config', { password_key, enabled });
    return response.data;
  },
};
