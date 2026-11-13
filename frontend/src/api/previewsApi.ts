import { apiClient } from '@/api/client';
import { DocumentPreviewResponse } from '@/types/api';

export function withOverlayQuery(path: string, overlay = true): string {
  const qIndex = path.indexOf('?');
  const base = qIndex >= 0 ? path.slice(0, qIndex) : path;
  const existingQuery = qIndex >= 0 ? path.slice(qIndex + 1) : '';
  const params = new URLSearchParams(existingQuery);
  params.set('overlay', overlay ? 'true' : 'false');
  return `${base}?${params.toString()}`;
}

export const previewsApi = {
  async getDocumentPreview(documentId: string): Promise<DocumentPreviewResponse> {
    const response = await apiClient.get<DocumentPreviewResponse>(
      `/api/documents/${encodeURIComponent(documentId)}/preview`
    );
    return response.data;
  },

  getPagePreviewPngPath(documentId: string, pageNumber: number, overlay = true): string {
    return withOverlayQuery(
      `/api/documents/${encodeURIComponent(documentId)}/pages/${pageNumber}/preview.png`,
      overlay
    );
  },

  getRegionPreviewPngPath(
    documentId: string,
    pageNumber: number,
    regionId: string,
    overlay = true
  ): string {
    return withOverlayQuery(
      `/api/documents/${encodeURIComponent(documentId)}/pages/${pageNumber}/regions/${encodeURIComponent(regionId)}/preview.png`,
      overlay
    );
  },

  async fetchPagePreviewPng(
    documentId: string,
    pageNumber: number,
    overlay = true,
    signal?: AbortSignal
  ): Promise<Blob> {
    const url = previewsApi.getPagePreviewPngPath(documentId, pageNumber, overlay);
    const response = await apiClient.get<Blob>(url, {
      responseType: 'blob',
      signal,
      headers: {
        Accept: 'image/png',
      },
    });
    return response.data;
  },

  async fetchRegionPreviewPng(
    documentId: string,
    pageNumber: number,
    regionId: string,
    overlay = true,
    signal?: AbortSignal
  ): Promise<Blob> {
    const url = previewsApi.getRegionPreviewPngPath(documentId, pageNumber, regionId, overlay);
    const response = await apiClient.get<Blob>(url, {
      responseType: 'blob',
      signal,
      headers: {
        Accept: 'image/png',
      },
    });
    return response.data;
  },

  async fetchPreviewPngByPath(
    previewImageUrl: string,
    overlay = true,
    signal?: AbortSignal
  ): Promise<Blob> {
    const response = await apiClient.get<Blob>(withOverlayQuery(previewImageUrl, overlay), {
      responseType: 'blob',
      signal,
      headers: {
        Accept: 'image/png',
      },
    });
    return response.data;
  },
};

