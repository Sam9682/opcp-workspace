import api from './api';

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegistrationData {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
}

export interface AuthUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_email_verified: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user?: AuthUser;
}

/**
 * Second-step challenge returned by `/auth/login` when the user has 2FA enabled.
 * No session token is issued/stored at this point; the caller must complete the
 * flow via `verifyLogin2fa`.
 */
export interface Login2FAChallenge {
  requires_2fa: true;
  methods: string[];
  challenge_token: string;
}

/**
 * Result of `login()`. Callers should narrow on the `requires_2fa` field:
 * - `Login2FAChallenge` (`requires_2fa === true`): a second step is required.
 * - `AuthResponse`: login completed and a session token was stored.
 */
export type LoginResult = AuthResponse | Login2FAChallenge;

/** Type guard to distinguish a 2FA challenge from a completed login. */
export function isLogin2FAChallenge(result: LoginResult): result is Login2FAChallenge {
  return (result as Login2FAChallenge).requires_2fa === true;
}

/** The authenticated user object persisted under the `user` key in `localStorage`. */
export type CurrentUser = NonNullable<AuthResponse['user']>;

function persistSession(data: AuthResponse): void {
  const { access_token, user } = data;
  localStorage.setItem('access_token', access_token);
  if (user) {
    localStorage.setItem('user_role', user.role);
    localStorage.setItem('user', JSON.stringify(user));
  }
}

export const authService = {
  async login(credentials: LoginCredentials): Promise<LoginResult> {
    const response = await api.post('/auth/login', credentials);
    // When 2FA is enabled the backend returns a challenge instead of a token.
    // Do NOT store anything in this case; the caller completes via verifyLogin2fa.
    if (response.data?.requires_2fa) {
      return response.data as Login2FAChallenge;
    }
    persistSession(response.data);
    return response.data as AuthResponse;
  },

  async verifyLogin2fa(challengeToken: string, code: string): Promise<AuthResponse> {
    const response = await api.post('/auth/login/2fa', {
      challenge_token: challengeToken,
      code,
    });
    persistSession(response.data);
    return response.data as AuthResponse;
  },

  async register(data: RegistrationData): Promise<void> {
    // Convertir les noms de champs en snake_case pour le backend
    await api.post('/auth/register', {
      email: data.email,
      password: data.password,
      first_name: data.firstName,
      last_name: data.lastName,
    });
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout');
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('user');
  },

  async verifyEmail(token: string): Promise<void> {
    await api.post('/auth/verify-email', { token });
  },

  async requestPasswordReset(email: string): Promise<void> {
    await api.post('/auth/password-reset', { email });
  },

  async resetPassword(token: string, newPassword: string): Promise<void> {
    await api.post('/auth/password-reset/confirm', { 
      token, 
      new_password: newPassword 
    });
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem('access_token');
  },

  isAdmin(): boolean {
    return localStorage.getItem('user_role') === 'administrator';
  },

  getCurrentUser(): CurrentUser | null {
    const raw = localStorage.getItem('user');
    if (raw === null) {
      return null; // Requirement 4.2: absent -> null
    }
    try {
      return JSON.parse(raw) as CurrentUser; // Requirement 4.1: parsed object
    } catch {
      return null; // Requirement 4.3: unparseable -> null
    }
  },
};
