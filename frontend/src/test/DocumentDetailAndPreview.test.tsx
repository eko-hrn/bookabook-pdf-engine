import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { documentsApi, healthApi, previewsApi } from '@/api';
import { AppRoutes } from '@/App';
import { WorkspaceProvider } from '@/hooks/useWorkspaceContext';
import { DocumentMetadataResponse, DocumentPreviewResponse } from '@/types/api';

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

const MOCK_DOC_META: DocumentMetadataResponse = {
  document_id: 'doc_real123',
  filename: 'Preview COMIC COLLECTION vol 1.pdf',
  file_size_bytes: 50_430_718,
  page_count: 2,
  created_at: '2026-11-11T09:00:00Z',
  status: 'UPLOADED',
  pages: [
    {
      page_number: 1,
      width_pt: 866.2,
      height_pt: 612.8,
      orientation: 'LANDSCAPE',
      detected_layout: 'COVER_SPREAD',
    },
    {
      page_number: 2,
      width_pt: 918.4,
      height_pt: 1303.9,
      orientation: 'PORTRAIT',
      detected_layout: 'IMPOSITION_4UP',
    },
  ],
};

const MOCK_PREVIEW_META: DocumentPreviewResponse = {
  document_id: 'doc_real123',
  source_filename: 'Preview COMIC COLLECTION vol 1.pdf',
  total_pages: 2,
  expected_book_pages: 4,
  document_status: 'MANUAL_REVIEW_REQUIRED',
  has_unknown_layout: false,
  has_manual_review_required: true,
  pages: [
    {
      page_number: 1,
      pdf_page_index: 0,
      width_pt: 866.2,
      height_pt: 612.8,
      orientation: 'LANDSCAPE',
      layout_type: 'COVER_SPREAD',
      crop_readiness: 'MANUAL_REVIEW_REQUIRED',
      expected_page_yield: 0,
      preview_image_url: '/api/documents/doc_real123/pages/1/preview.png',
      status_badge: {
        status: 'MANUAL_REVIEW_REQUIRED',
        badge_text: 'MANUAL REVIEW',
        accessibility_label: 'Cover spread requires manual review',
        stroke_color: '#d97706',
        fill_color: '#fef3c7',
        pattern_type: 'solid',
      },
      warnings: ['Cover auto-crop disabled; protected spine zone must be preserved.'],
      unresolved_discrepancies: [],
    },
    {
      page_number: 2,
      pdf_page_index: 1,
      width_pt: 918.4,
      height_pt: 1303.9,
      orientation: 'PORTRAIT',
      layout_type: 'IMPOSITION_4UP',
      crop_readiness: 'CROP_READY',
      expected_page_yield: 4,
      preview_image_url: '/api/documents/doc_real123/pages/2/preview.png',
      status_badge: {
        status: 'CROP_READY',
        badge_text: 'CROP READY',
        accessibility_label: '4-Up sheet Q1-Q4 ready for inspection',
        stroke_color: '#059669',
        fill_color: '#d1fae5',
        pattern_type: 'solid',
      },
      warnings: [],
      unresolved_discrepancies: [],
    },
  ],
  validation_summary: {
    is_valid: true,
    overall_status: 'PASS_WITH_WARNINGS',
    total_regions: 6,
    valid_regions_count: 6,
    invalid_regions_count: 0,
    errors: [],
    warnings: ['Cover requires manual review due to v1.3.4 spine guard.'],
  },
};

describe('DocumentDetailPage & PreviewWorkspacePage', () => {
  beforeEach(() => {
    vi.mocked(healthApi.getHealth).mockResolvedValue({
      status: 'ok',
      app_name: 'Bookabook API',
      version: '1.0.0',
      database_connected: true,
      timestamp: '2026-11-11T10:00:00Z',
    });
    vi.mocked(documentsApi.getDocument).mockResolvedValue(MOCK_DOC_META);
    vi.mocked(previewsApi.getDocumentPreview).mockResolvedValue(MOCK_PREVIEW_META);
    vi.mocked(previewsApi.fetchPreviewPngByPath).mockResolvedValue(
      new Blob(['png-bytes'], { type: 'image/png' })
    );
    vi.mocked(previewsApi.fetchPagePreviewPng).mockResolvedValue(
      new Blob(['png-bytes'], { type: 'image/png' })
    );
  });

  it('renders document detail geometry table, size, and preview availability', async () => {
    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/documents/doc_real123']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    await waitFor(
      () => {
        expect(
          screen.getByRole('heading', { name: 'Preview COMIC COLLECTION vol 1.pdf' })
        ).toBeInTheDocument();
      },
      { timeout: 5000 }
    );

    expect(screen.getByText(/866.2 × 612.8 pt/)).toBeInTheDocument();
    expect(screen.getByText(/918.4 × 1303.9 pt/)).toBeInTheDocument();
    expect(screen.getByText('Cover Spread')).toBeInTheDocument();
    expect(screen.getByText('4-Up Imposition')).toBeInTheDocument();
    expect(screen.getByText('2 Sheets Ready')).toBeInTheDocument();
    expect(screen.getByText('4 pages')).toBeInTheDocument();
  });

  it('navigates between Cover and 4-Up sheets and adjusts zoom controls in PreviewWorkspace', async () => {
    const user = userEvent.setup();
    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/documents/doc_real123/preview']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    await waitFor(() => {
      expect(
        screen.getByText(
          (_content, node) =>
            node?.tagName === 'SPAN' && node?.textContent === 'Sheet 1 of 2'
        )
      ).toBeInTheDocument();
    });

    expect(screen.getByText('Sheet 1 Metadata')).toBeInTheDocument();
    expect(
      screen.getByText(/Cover auto-crop disabled; protected spine zone/i)
    ).toBeInTheDocument();
    expect(
      await screen.findByAltText(
        /Preview of Sheet 1 \(Cover Spread\) with backend crop boundaries/i
      )
    ).toBeInTheDocument();

    // Test Zoom controls
    expect(screen.getByRole('button', { name: /Fit Screen/i })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Zoom in' }));
    expect(screen.getByText('125%')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Fit Screen/i }));
    expect(screen.getByText('Fit')).toBeInTheDocument();

    // Navigate to Sheet 2 (4-Up)
    await user.click(screen.getByRole('button', { name: 'Next sheet' }));

    await waitFor(() => {
      expect(
        screen.getByText(
          (_content, node) =>
            node?.tagName === 'SPAN' && node?.textContent === 'Sheet 2 of 2'
        )
      ).toBeInTheDocument();
    });
    expect(screen.getByText('Sheet 2 Metadata')).toBeInTheDocument();
    expect(screen.getByText('4 pages')).toBeInTheDocument();
  });

  it('navigates Book Spread (Cover standalone, Q1+Q2, Q3+Q4), bottom thumbnails, Overlays On/Off, and Full Sheet mode', async () => {
    const user = userEvent.setup();
    const previewWithRegions: DocumentPreviewResponse = {
      ...MOCK_PREVIEW_META,
      pages: [
        {
          ...MOCK_PREVIEW_META.pages[0],
          regions: [
            {
              region_id: 'BACKCOVER',
              quadrant: null,
              width_pt: 425.6,
              height_pt: 612.8,
              target_width_px: 591,
              target_height_px: 851,
              blank_page_status: 'CONTENT_PRESENT',
              preview_image_url: '/api/documents/doc_real123/pages/1/regions/BACKCOVER/preview.png',
            },
            {
              region_id: 'COVER',
              quadrant: null,
              width_pt: 425.6,
              height_pt: 612.8,
              target_width_px: 591,
              target_height_px: 851,
              blank_page_status: 'CONTENT_PRESENT',
              preview_image_url: '/api/documents/doc_real123/pages/1/regions/COVER/preview.png',
            },
          ],
        },
        {
          ...MOCK_PREVIEW_META.pages[1],
          regions: [1, 2, 3, 4].map((q) => ({
            region_id: `PAGE-0${q}`,
            quadrant: q,
            width_pt: 425.52,
            height_pt: 609.12,
            target_width_px: 1773,
            target_height_px: 2538,
            blank_page_status: 'CONTENT_PRESENT',
            preview_image_url: `/api/documents/doc_real123/pages/2/regions/PAGE-0${q}/preview.png`,
          })),
        },
      ],
    };

    vi.mocked(previewsApi.getDocumentPreview).mockResolvedValue(previewWithRegions);

    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/documents/doc_real123/preview']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    // 1. Starts on standalone COVER SPREAD
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'COVER SPREAD' })).toBeInTheDocument();
    });

    // 2. Step <previous / next> -> PAGE-01 + PAGE-02 (Q1 + Q2)
    await user.click(screen.getByRole('button', { name: 'Next spread' }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'PAGE-01 + PAGE-02' })).toBeInTheDocument();
    });
    expect(await screen.findByAltText(/Left spread page PAGE-01/i)).toBeInTheDocument();
    expect(await screen.findByAltText(/Right spread page PAGE-02/i)).toBeInTheDocument();

    // 3. Step next -> PAGE-03 + PAGE-04 (Q3 + Q4)
    await user.click(screen.getByRole('button', { name: 'Next spread' }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'PAGE-03 + PAGE-04' })).toBeInTheDocument();
    });

    // 4. Jump via horizontal bottom thumbnail PAGE-01 -> jumps back to PAGE-01 + PAGE-02
    await user.click(screen.getByRole('listitem', { name: /PAGE-01/i }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'PAGE-01 + PAGE-02' })).toBeInTheDocument();
    });

    // 5. Toggle Overlays On -> Off triggers backend request with overlay=false
    await user.click(screen.getByRole('button', { name: /Overlays On/i }));
    await waitFor(() => {
      expect(vi.mocked(previewsApi.fetchPreviewPngByPath)).toHaveBeenCalledWith(
        '/api/documents/doc_real123/pages/2/regions/PAGE-01/preview.png',
        false
      );
    });

    // 6. Toggle Full Sheet mode
    await user.click(screen.getByRole('button', { name: 'Full Sheet' }));
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Sheet 2 Full Inspection' })
      ).toBeInTheDocument();
    });
  });
});

