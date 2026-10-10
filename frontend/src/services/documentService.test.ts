import { describe, expect, it, vi, beforeEach } from 'vitest';
import { documentService } from './documentService';
import api from './api';

vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('documentService.deleteDocument', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('issues DELETE /documents/{id} and resolves to void', async () => {
    mockedApi.delete.mockResolvedValueOnce({ data: undefined });

    const result = await documentService.deleteDocument('abc-123');

    expect(mockedApi.delete).toHaveBeenCalledTimes(1);
    expect(mockedApi.delete).toHaveBeenCalledWith('/documents/abc-123');
    expect(result).toBeUndefined();
  });

  it('lets errors propagate so the page can surface a delete-error banner', async () => {
    const error = new Error('delete failed');
    mockedApi.delete.mockRejectedValueOnce(error);

    await expect(documentService.deleteDocument('xyz-999')).rejects.toThrow('delete failed');
    expect(mockedApi.delete).toHaveBeenCalledWith('/documents/xyz-999');
  });
});
