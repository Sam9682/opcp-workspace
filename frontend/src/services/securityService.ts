import api from './api';

export interface TwoFactorStatus {
  totp_enabled: boolean;
  email_2fa_enabled: boolean;
}

export interface TotpSetup {
  secret: string;
  otpauth_uri: string;
}

export const securityService = {
  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await api.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },

  async getTwoFactorStatus(): Promise<TwoFactorStatus> {
    const response = await api.get('/auth/2fa/status');
    return response.data;
  },

  async startTotpSetup(): Promise<TotpSetup> {
    const response = await api.post('/auth/2fa/totp/setup');
    return response.data;
  },

  async confirmTotp(code: string): Promise<void> {
    await api.post('/auth/2fa/totp/confirm', { code });
  },

  async disableTotp(): Promise<void> {
    await api.post('/auth/2fa/totp/disable');
  },

  async enableEmail2fa(): Promise<void> {
    await api.post('/auth/2fa/email/enable');
  },

  async disableEmail2fa(): Promise<void> {
    await api.post('/auth/2fa/email/disable');
  },
};
