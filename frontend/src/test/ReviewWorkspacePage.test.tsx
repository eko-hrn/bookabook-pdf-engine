import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { documentsApi, healthApi, previewsApi, reviewsApi } from '@/api';
import { AppRoutes } from '@/App';
import { WorkspaceProvider } from '@/hooks/useWorkspaceContext';
import { ReviewSession } from '@/types/api';

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

function buildSession(overrides?: Partial<ReviewSession>): ReviewSession {
  const base: ReviewSession = {
    session_id: 'rev_test_01',
    source_filename: 'Preview COMIC COLLECTION vol 1.pdf',
    created_at: '2026-11-11T10:00:00Z',
    updated_at: '2026-11-11T10:05:00Z',
    metadata: { document_id: 'doc_real123' },
    page_records: [
      {
        pdf_page_index: 0,
        pdf_page_number: 1,
        layout_type: 'COVER_SPREAD',
        classification_status: 'CLASSIFIED',
        crop_readiness: 'MANUAL_REVIEW_REQUIRED',
        review_decision: 'PENDING',
        reviewer_id: null,
        reviewed_at: null,
        notes: null,
        warnings: ['Cover protected spine zone requires manual verification.'],
        unresolved_discrepancies: [],
        is_cover: true,
        is_non_nominal: false,
        history: [],
      },
      {
        pdf_page_index: 1,
        pdf_page_number: 2,
        layout_type: null,
        classification_status: 'UNKNOWN_LAYOUT',
        crop_readiness: 'NOT_APPLICABLE',
        review_decision: 'PENDING',
        reviewer_id: null,
        reviewed_at: null,
        notes: null,
        warnings: ['Dimensions fall outside supported v1.3.4 profiles.'],
        unresolved_discrepancies: ['Unknown layout cannot be approved'],
        is_cover: false,
        is_non_nominal: true,
        history: [],
      },
    ],
    document_summary: {
      session_id: 'rev_test_01',
      source_filename: 'Preview COMIC COLLECTION vol 1.pdf',
      total_pages: 2,
      approved_pages_count: 0,
      rejected_pages_count: 0,
      needs_revision_pages_count: 0,
      pending_pages_count: 2,
      status: 'PENDING_REVIEW',
      is_review_completed: false,
      requires_production_authorization: true,
      summary_message: '2 pages awaiting operator decision.',
      unresolved_discrepancies: [],
      reviewed_at: null,
    },
    history: {
      entries: [
        {
          entry_id: 'ev_init',
          pdf_page_index: null,
          pdf_page_number: null,
          event_type: 'SESSION_CREATED',
          previous_decision: null,
          new_decision: null,
          reviewer_id: 'system',
          timestamp: '2026-11-11T10:00:00Z',
          notes: 'Session initialized',
          reason: null,
        },
      ],
    },
  };
  return { ...base, ...overrides };
}

describe('ReviewWorkspacePage', () => {
  beforeEach(() => {
    vi.mocked(healthApi.getHealth).mockResolvedValue({
      status: 'ok',
      app_name: 'Bookabook API',
      version: '1.0.0',
      database_connected: true,
      timestamp: '2026-11-11T10:00:00Z',
    });
    vi.mocked(documentsApi.getDocument).mockResolvedValue({
      document_id: 'doc_real123',
      filename: 'Preview COMIC COLLECTION vol 1.pdf',
      file_size_bytes: 50_430_718,
      page_count: 2,
      created_at: '2026-11-11T09:00:00Z',
      status: 'UPLOADED',
      pages: [],
    });
    vi.mocked(previewsApi.getDocumentPreview).mockResolvedValue({
      document_id: 'doc_real123',
      source_filename: 'Preview COMIC COLLECTION vol 1.pdf',
      total_pages: 2,
      expected_book_pages: 0,
      document_status: 'MANUAL_REVIEW_REQUIRED',
      has_unknown_layout: true,
      has_manual_review_required: true,
      pages: [
        {
          page_number: 1,
          pdf_page_index: 0,
          width_pt: 866,
          height_pt: 612,
          orientation: 'LANDSCAPE',
          layout_type: 'COVER_SPREAD',
          crop_readiness: 'MANUAL_REVIEW_REQUIRED',
          expected_page_yield: 0,
          preview_image_url: '/api/documents/doc_real123/pages/1/preview.png',
          status_badge: {
            status: 'MANUAL_REVIEW_REQUIRED',
            badge_text: 'MANUAL REVIEW',
            accessibility_label: 'Manual review',
            stroke_color: '#d97706',
            fill_color: '#fef3c7',
            pattern_type: 'solid',
          },
          warnings: [],
          unresolved_discrepancies: [],
        },
      ],
      validation_summary: {
        is_valid: true,
        overall_status: 'PASS_WITH_WARNINGS',
        total_regions: 2,
        valid_regions_count: 2,
        invalid_regions_count: 0,
        errors: [],
        warnings: [],
      },
    });
    vi.mocked(previewsApi.fetchPreviewPngByPath).mockResolvedValue(
      new Blob(['png'], { type: 'image/png' })
    );
    vi.mocked(previewsApi.fetchPagePreviewPng).mockResolvedValue(
      new Blob(['png'], { type: 'image/png' })
    );
  });

  it('creates a new review session for a document and displays initial records', async () => {
    const user = userEvent.setup();
    const initialSession = buildSession();

    vi.mocked(reviewsApi.createSession).mockResolvedValue(initialSession);
    vi.mocked(reviewsApi.getSession).mockResolvedValue(initialSession);
    vi.mocked(reviewsApi.getHistory).mockResolvedValue(initialSession.history.entries);

    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/documents/doc_real123/review']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    await waitFor(() => {
      expect(
        screen.getByText('Initialize Operator Review Session')
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /Create Review Session/i }));

    await waitFor(() => {
      expect(screen.getByText('Document Review Summary')).toBeInTheDocument();
    });
    expect(vi.mocked(reviewsApi.createSession)).toHaveBeenCalledWith({
      document_id: 'doc_real123',
      session_id: undefined,
    });
    expect(screen.getByText(/Production Authorization Guardrail:/i)).toBeInTheDocument();
  });

  it('requires modal confirmation for Reject and blocks direct Approval on UNKNOWN_LAYOUT or REJECTED pages', async () => {
    const user = userEvent.setup();
    const sessionPending = buildSession();
    const sessionRejected = buildSession({
      page_records: [
        {
          ...sessionPending.page_records[0],
          review_decision: 'REJECTED',
          reviewer_id: 'operator_1',
          notes: 'Spine split off-center',
        },
        sessionPending.page_records[1],
      ],
      document_summary: {
        ...sessionPending.document_summary,
        rejected_pages_count: 1,
        pending_pages_count: 1,
        status: 'REVIEW_REJECTED',
      },
    });

    vi.mocked(reviewsApi.getSession)
      .mockResolvedValueOnce(sessionPending)
      .mockResolvedValue(sessionRejected);
    vi.mocked(reviewsApi.recordDecision).mockResolvedValue(
      sessionRejected.page_records[0]
    );
    vi.mocked(reviewsApi.getHistory).mockResolvedValue([
      ...sessionPending.history.entries,
      {
        entry_id: 'ev_rej',
        pdf_page_index: 0,
        pdf_page_number: 1,
        event_type: 'DECISION_RECORDED',
        previous_decision: 'PENDING',
        new_decision: 'REJECTED',
        reviewer_id: 'operator_1',
        timestamp: '2026-11-11T10:12:00Z',
        notes: 'Spine split off-center',
        reason: 'Spine Alignment Issue',
      },
    ]);

    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/reviews/rev_test_01']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Document Review Summary')).toBeInTheDocument();
    });

    // Click Reject on Sheet 1 -> opens confirmation modal
    await user.click(screen.getByRole('button', { name: /^Reject$/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(
      screen.getByText(/Confirm Page Rejection — Sheet 1/i)
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText(/Rejection Reason/i), 'Spine Alignment Issue');
    await user.click(screen.getByRole('button', { name: /Confirm Reject Page/i }));

    await waitFor(() => {
      expect(vi.mocked(reviewsApi.recordDecision)).toHaveBeenCalledWith(
        'rev_test_01',
        1,
        expect.objectContaining({
          decision: 'REJECTED',
          reason: 'Spine Alignment Issue',
        })
      );
    });

    // Now Sheet 1 is REJECTED -> Approve must be disabled & transition notice shown
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Approve$/i })).toBeDisabled();
    });
    expect(
      screen.getByText('Direct Approval Blocked:')
    ).toBeInTheDocument();

    // Switch to Sheet 2 (UNKNOWN_LAYOUT) -> Approve must stay disabled
    await user.click(screen.getByRole('button', { name: /Sheet 2/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Approve$/i })).toBeDisabled();
    });
    expect(
      screen.getByText(/Pages with unclassified layout cannot be approved/i)
    ).toBeInTheDocument();
  });
});

