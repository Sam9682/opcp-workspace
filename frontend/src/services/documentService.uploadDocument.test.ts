import { describe, it, expect, vi, beforeEach } from 'vitest';

// The service imports the default axios instance from './api' and calls
// `.post` on it for uploads. We replace that module with a stub whose methods
// we can assert against, so this is a pure contract test (HTTP verb, path,
// multipart body) with no live backend.
vi.mock('./api', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

// Import after the mock is registered so the service binds to the stub.
import api from './api';
import { documentService, type Document } from './documentService';

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  mockedApi.get.mockReset();
  mockedApi.put.mockReset();
  mockedApi.post.mockReset();
  mockedApi.delete.mockReset();
  mockedApi.post.mockResolvedValue({ data: {} });
});

describe('documentService.uploadDocument contract', () => {
  // Feature: admin-document-upload-categories — service upload wiring (task 6.1)
  // Validates: Requirement 3.3

  const sampleDocument: Document = {
    id: 'doc-1',
    filename: 'stored-uuid.pdf',
    original_name: 'guide.pdf',
    mime_type: 'application/pdf',
    size: 1234,
    category: 'documents',
    access_level: 'public',
    uploaded_by: 'admin-1',
    download_count: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  };

  it('posts multipart form data to /documents/upload with file and access_level, omits category, and returns the document', async () => {
    mockedApi.post.mockResolvedValueOnce({ data: { document: sampleDocument } });

    const file = new File(['hello'], 'guide.pdf', { type: 'application/pdf' });
    const result = await documentService.uploadDocument(file);

    expect(mockedApi.post).toHaveBeenCalledTimes(1);

    const [url, body] = mockedApi.post.mock.calls[0];
    expect(url).toBe('/documents/upload');
    expect(body).toBeInstanceOf(FormData);

    const form = body as FormData;
    expect(form.get('file')).toBe(file);
    expect(form.get('access_level')).toBe('public');
    // Category is server-derived; the client must NOT send it.
    expect(form.has('category')).toBe(false);

    expect(mockedApi.get).not.toHaveBeenCalled();
    expect(mockedApi.put).not.toHaveBeenCalled();
    expect(result).toEqual(sampleDocument);
  });

  it('forwards a caller-supplied access_level', async () => {
    mockedApi.post.mockResolvedValueOnce({ data: { document: sampleDocument } });

    const file = new File(['x'], 'notes.md', { type: 'text/markdown' });
    await documentService.uploadDocument(file, 'members');

    const form = mockedApi.post.mock.calls[0][1] as FormData;
    expect(form.get('access_level')).toBe('members');
    expect(form.has('category')).toBe(false);
  });
});
