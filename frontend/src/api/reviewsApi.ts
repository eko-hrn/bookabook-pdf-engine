import { apiClient } from '@/api/client';
import {
  CreateReviewSessionRequest,
  DocumentReviewSummary,
  PageReviewRecord,
  RecordDecisionRequest,
  ReviewHistoryEntry,
  ReviewSession,
  UpdateNotesRequest,
} from '@/types/api';

export const reviewsApi = {
  async createSession(payload: CreateReviewSessionRequest): Promise<ReviewSession> {
    const response = await apiClient.post<ReviewSession>('/api/reviews/sessions', payload);
    return response.data;
  },

  async getSession(sessionId: string): Promise<ReviewSession> {
    const response = await apiClient.get<ReviewSession>(
      `/api/reviews/sessions/${encodeURIComponent(sessionId)}`
    );
    return response.data;
  },

  async getPageRecord(sessionId: string, pageNumber: number): Promise<PageReviewRecord> {
    const response = await apiClient.get<PageReviewRecord>(
      `/api/reviews/sessions/${encodeURIComponent(sessionId)}/pages/${pageNumber}`
    );
    return response.data;
  },

  async recordDecision(
    sessionId: string,
    pageNumber: number,
    payload: RecordDecisionRequest
  ): Promise<PageReviewRecord> {
    const response = await apiClient.post<PageReviewRecord>(
      `/api/reviews/sessions/${encodeURIComponent(sessionId)}/pages/${pageNumber}/decision`,
      payload
    );
    return response.data;
  },

  async updateNotes(
    sessionId: string,
    pageNumber: number,
    payload: UpdateNotesRequest
  ): Promise<PageReviewRecord> {
    const response = await apiClient.patch<PageReviewRecord>(
      `/api/reviews/sessions/${encodeURIComponent(sessionId)}/pages/${pageNumber}/notes`,
      payload
    );
    return response.data;
  },

  async getHistory(sessionId: string, pageNumber?: number): Promise<ReviewHistoryEntry[]> {
    const response = await apiClient.get<ReviewHistoryEntry[]>(
      `/api/reviews/sessions/${encodeURIComponent(sessionId)}/history`,
      {
        params: pageNumber !== undefined ? { page_number: pageNumber } : undefined,
      }
    );
    return response.data;
  },

  async getSummary(sessionId: string): Promise<DocumentReviewSummary> {
    const response = await apiClient.get<DocumentReviewSummary>(
      `/api/reviews/sessions/${encodeURIComponent(sessionId)}/summary`
    );
    return response.data;
  },
};

