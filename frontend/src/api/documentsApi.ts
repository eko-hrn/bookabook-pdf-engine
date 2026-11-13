import { AxiosProgressEvent } from 'axios';
import { apiClient } from '@/api/client';
import { DocumentMetadataResponse, DocumentUploadResponse } from '@/types/api';

export const documentsApi = {
  async uploadDocument(
    file: File,
    onUploadProgress?: (percentCompleted: number) => void
  ): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post<DocumentUploadResponse>(
      '/api/documents/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent: AxiosProgressEvent) => {
          if (!onUploadProgress || !progressEvent.total) return;
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onUploadProgress(Math.min(100, Math.max(0, percent)));
        },
      }
    );

    return response.data;
  },

  async getDocument(documentId: string): Promise<DocumentMetadataResponse> {
    const response = await apiClient.get<DocumentMetadataResponse>(
      `/api/documents/${encodeURIComponent(documentId)}`
    );
    return response.data;
  },
};

