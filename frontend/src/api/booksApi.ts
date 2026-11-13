import { AxiosProgressEvent } from 'axios';
import { apiClient, resolveApiUrl } from '@/api/client';
import {
  BookDetailResponse,
  BookListResponse,
  ProcessPdfResponse,
  SaveBookRequest,
} from '@/types/api';

export const booksApi = {
  async processPdf(
    file: File,
    onUploadProgress?: (percentCompleted: number) => void
  ): Promise<ProcessPdfResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post<ProcessPdfResponse>(
      '/api/books/process-pdf',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 180_000,
        onUploadProgress: (progressEvent: AxiosProgressEvent) => {
          if (!onUploadProgress || !progressEvent.total) return;
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onUploadProgress(Math.min(100, Math.max(0, percent)));
        },
      }
    );
    return response.data;
  },

  async saveBook(payload: SaveBookRequest): Promise<BookDetailResponse> {
    const response = await apiClient.post<BookDetailResponse>('/api/books', payload);
    return response.data;
  },

  async listBooks(): Promise<BookListResponse> {
    const response = await apiClient.get<BookListResponse>('/api/books');
    return response.data;
  },

  async getBook(bookId: string): Promise<BookDetailResponse> {
    const response = await apiClient.get<BookDetailResponse>(
      `/api/books/${encodeURIComponent(bookId)}`
    );
    return response.data;
  },

  getDownloadHref(path: string): string {
    return resolveApiUrl(path);
  },

  async fetchBlobForDownload(path: string): Promise<Blob> {
    const response = await apiClient.get<Blob>(resolveApiUrl(path), {
      responseType: 'blob',
    });
    return response.data;
  },
};

