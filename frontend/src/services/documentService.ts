import api from './api';

export type DocumentCategory = 'documents' | 'scripts' | 'links' | 'docs' | 'trainings';
export type AccessLevel = 'public' | 'members' | 'administrators';

export interface Document {
  id: string;
  filename: string;
  original_name: string;
  mime_type: string;
  size: number;
  category: DocumentCategory;
  access_level: AccessLevel;
  uploaded_by: string;
  download_count: number;
  created_at: string;
  updated_at: string;
  target_url?: string | null;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export const documentService = {
  async listDocuments(): Promise<DocumentListResponse> {
    const response = await api.get<DocumentListResponse>('/documents');
    return response.data;
  },

  async uploadDocument(file: File, accessLevel: AccessLevel = 'public'): Promise<Document> {
    const form = new FormData();
    form.append('file', file);
    form.append('access_level', accessLevel);
    const response = await api.post<{ document: Document }>('/documents/upload', form);
    return response.data.document;
  },

  async downloadDocument(id: string, originalName: string): Promise<void> {
    const response = await api.get(`/documents/${id}/download`, { responseType: 'blob' });
    const url = window.URL.createObjectURL(response.data as Blob);
    const anchor = window.document.createElement('a');
    anchor.href = url;
    anchor.download = originalName;
    window.document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(url);
  },

  async deleteDocument(id: string): Promise<void> {
    await api.delete(`/documents/${id}`);
  },
};
