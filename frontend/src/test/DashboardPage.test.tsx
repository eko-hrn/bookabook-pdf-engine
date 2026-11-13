import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { documentsApi, healthApi, previewsApi, reviewsApi } from '@/api';
import { AppRoutes } from '@/App';
import { WorkspaceProvider } from '@/hooks/useWorkspaceContext';

vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return {
    ...actual,
    healthApi: { getHealth: vi.fn() },
    documentsApi: {
      uploadDocument: vi.fn(),
      getDocument: vi.fn(),
    },
    previewsApi: {
      getDocumentPreview: vi.fn(),
      fetchPagePreviewPng: vi.fn(),
      fetchPreviewPngByPath: vi.fn(),
    },
    reviewsApi: {
      createSession: vi.fn(),
      getSession: vi.fn(),
      getPageRecord: vi.fn(),
      recordDecision: vi.fn(),
      updateNotes: vi.fn(),
      getHistory: vi.fn(),
      getSummary: vi.fn(),
    },
  };
});

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.mocked(healthApi.getHealth).mockResolvedValue({
      status: 'ok',
      app_name: 'Bookabook PDF Preview & Review API',
      version: '1.0.0',
      database_connected: true,
      timestamp: '2026-11-11T10:00:00Z',
    });
  });

  it('displays live backend health and honest Unavailable metrics instead of fake stats', async () => {
    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    await waitFor(() => {
      expect(
        screen.getByText('Bookabook PDF Preview & Review API')
      ).toBeInTheDocument();
    });

    expect(screen.getAllByText('Unavailable')).toHaveLength(4);
    expect(
      screen.getByText(/Global listing and aggregate metric endpoints unavailable/i)
    ).toBeInTheDocument();
    expect(screen.getByText('Total Uploaded Documents')).toBeInTheDocument();
    expect(screen.getByText('Documents Awaiting Review')).toBeInTheDocument();
    expect(screen.getByText('Documents Under Review')).toBeInTheDocument();
    expect(screen.getByText('Completed Review Sessions')).toBeInTheDocument();
    expect(
      screen.getByText('No documents opened in this workspace yet')
    ).toBeInTheDocument();
  });

  it('verifies workspace-tracked documents and review sessions live from backend endpoints', async () => {
    window.localStorage.setItem(
      'bookabook_operator_workspace_v1',
      JSON.stringify({
        activeDocumentId: 'doc_sample_1',
        activeSessionId: 'rev_sample_1',
        reviewerId: 'operator_1',
        documents: [
          {
            document_id: 'doc_sample_1',
            filename: 'Preview COMIC COLLECTION vol 1.pdf',
            page_count: 6,
            added_at: '2026-11-11T09:00:00Z',
          },
        ],
        sessions: [
          {
            session_id: 'rev_sample_1',
            document_id: 'doc_sample_1',
            source_filename: 'Preview COMIC COLLECTION vol 1.pdf',
            added_at: '2026-11-11T09:05:00Z',
          },
        ],
        documentSessionMap: { doc_sample_1: 'rev_sample_1' },
      })
    );

    vi.mocked(documentsApi.getDocument).mockResolvedValue({
      document_id: 'doc_sample_1',
      filename: 'Preview COMIC COLLECTION vol 1.pdf',
      file_size_bytes: 50_430_718,
      page_count: 6,
      created_at: '2026-11-11T09:00:00Z',
      status: 'UPLOADED',
      pages: [],
    });

    vi.mocked(previewsApi.getDocumentPreview).mockResolvedValue({
      document_id: 'doc_sample_1',
      source_filename: 'Preview COMIC COLLECTION vol 1.pdf',
      total_pages: 6,
      expected_book_pages: 20,
      document_status: 'MANUAL_REVIEW_REQUIRED',
      has_unknown_layout: false,
      has_manual_review_required: true,
      pages: [],
      validation_summary: {
        is_valid: true,
        overall_status: 'PASS_WITH_WARNINGS',
        total_regions: 20,
        valid_regions_count: 20,
        invalid_regions_count: 0,
        errors: [],
        warnings: [],
      },
    });

    vi.mocked(reviewsApi.getSummary).mockResolvedValue({
      session_id: 'rev_sample_1',
      source_filename: 'Preview COMIC COLLECTION vol 1.pdf',
      total_pages: 6,
      approved_pages_count: 2,
      rejected_pages_count: 0,
      needs_revision_pages_count: 0,
      pending_pages_count: 4,
      status: 'PARTIALLY_REVIEWED',
      is_review_completed: false,
      requires_production_authorization: true,
      summary_message: 'Review in progress',
      unresolved_discrepancies: [],
      reviewed_at: null,
    });

    vi.mocked(reviewsApi.getHistory).mockResolvedValue([
      {
        entry_id: 'hist_1',
        pdf_page_index: 1,
        pdf_page_number: 2,
        event_type: 'DECISION_RECORDED',
        previous_decision: 'PENDING',
        new_decision: 'APPROVED',
        reviewer_id: 'operator_1',
        timestamp: '2026-11-11T09:10:00Z',
        notes: 'Q1-Q4 crisp',
        reason: null,
      },
    ]);

    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    await waitFor(() => {
      expect(
        screen.getAllByText('Preview COMIC COLLECTION vol 1.pdf').length
      ).toBeGreaterThanOrEqual(2);
    });

    expect(screen.getByText('2/6 approved')).toBeInTheDocument();
    expect(screen.getByText('Latest Recorded Audit Events')).toBeInTheDocument();
    expect(screen.getByText(/DECISION_RECORDED/)).toBeInTheDocument();
  });
});

