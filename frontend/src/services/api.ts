import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
  withCredentials: false, // Set to true if using cookies
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // For multipart uploads the body is a FormData instance. The instance
    // default `Content-Type: application/json` would drop the multipart
    // boundary and cause the backend to reject the request with 400. Remove
    // the forced content type so the browser generates
    // `multipart/form-data; boundary=...` itself. JSON bodies are untouched.
    if (config.data instanceof FormData && config.headers) {
      delete config.headers['Content-Type'];
      delete config.headers['content-type'];
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Endpoints where a 401 is an expected, caller-handled outcome (e.g. bad
// credentials or an invalid 2FA code). For these we must NOT trigger the
// global "session expired" redirect, otherwise the login page reroutes to
// itself and the error message the page just displayed is wiped instantly.
const AUTH_ENDPOINTS = ['/auth/login', '/auth/login/2fa'];

function isAuthEndpoint(url?: string): boolean {
  if (!url) {
    return false;
  }
  return AUTH_ENDPOINTS.some((endpoint) => url.includes(endpoint));
}

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Only force a redirect when an authenticated session has actually expired
    // on a protected request. Login/2FA 401s are surfaced to the caller so the
    // login page can show the error message and keep the user in place.
    if (error.response?.status === 401 && !isAuthEndpoint(error.config?.url)) {
      // Clear token and redirect to login
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
