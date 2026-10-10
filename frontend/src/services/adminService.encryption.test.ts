import { describe, expect, it, vi, beforeEach } from 'vitest';
import { adminService } from './adminService';
import api from './api';

vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
};

describe('adminService encryption config', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getEncryptionConfig issues GET /admin/encryption-config', async () => {
    mockedApi.get.mockResolvedValueOnce({ data: { enabled: false, key_is_set: false } });

    const result = await adminService.getEncryptionConfig();

    expect(mockedApi.get).toHaveBeenCalledWith('/admin/encryption-config');
    expect(result).toEqual({ enabled: false, key_is_set: false });
  });

  it('updateEncryptionConfig PUTs the password key and desired enabled flag', async () => {
    mockedApi.put.mockResolvedValueOnce({ data: { enabled: false, key_is_set: true } });

    const result = await adminService.updateEncryptionConfig('super-secret-key', true);

    expect(mockedApi.put).toHaveBeenCalledTimes(1);
    expect(mockedApi.put).toHaveBeenCalledWith('/admin/encryption-config', {
      password_key: 'super-secret-key',
      enabled: true,
    });
    // The response never carries the key back, only the non-secret summary.
    expect(result).toEqual({ enabled: false, key_is_set: true });
  });

  it('lets errors propagate so the page can show a save-error banner', async () => {
    mockedApi.put.mockRejectedValueOnce(new Error('save failed'));

    await expect(
      adminService.updateEncryptionConfig('super-secret-key', true)
    ).rejects.toThrow('save failed');
  });
});
