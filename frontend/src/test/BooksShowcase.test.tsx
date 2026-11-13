import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { booksApi, healthApi } from '@/api';
import { AppRoutes } from '@/App';
import { WorkspaceProvider } from '@/hooks/useWorkspaceContext';
import { BookDetailResponse } from '@/types/api';

vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return {
    ...actual,
    healthApi: { getHealth: vi.fn() },
    booksApi: {
      processPdf: vi.fn(),
      saveBook: vi.fn(),
      listBooks: vi.fn(),
      getBook: vi.fn(),
      getDownloadHref: vi.fn((path: string) => path),
      fetchBlobForDownload: vi.fn(),
    },
  };
});

const SAMPLE_BOOK_DETAIL: BookDetailResponse = {
  book_id: 'book_showcase_01',
  title: 'Comic Anthology 2026',
  author: 'Alleric Tansil',
  authors_all: 'Alleric Tansil, Francis',
  description: 'Published comic showcase edition.',
  year: 2026,
  age_group: '7-12',
  sponsor: 'COFA Studio',
  content_pages: 2,
  phone: '+62811111111',
  email: 'comics@bookabook.id',
  source_filename: 'anthology.pdf',
  total_exported_pages: 4,
  cover_filename: 'COVER.jpg',
  backcover_filename: 'BACKCOVER.jpg',
  cover_url: '/api/books/book_showcase_01/pages/COVER.jpg',
  storage_backend: 'local',
  created_at: '2026-11-11T10:00:00Z',
  validation_summary: {},
  zip_download_url: '/api/books/book_showcase_01/download.zip',
  pages: [
    {
      page_key: 'COVER',
      filename: 'COVER.jpg',
      page_kind: 'COVER',
      order_index: 0,
      source_pdf_page: 1,
      quadrant: null,
      width_px: 1894,
      height_px: 2657,
      dpi: 300,
      file_size_bytes: 540_000,
      quality_used: 85,
      subsampling_used: '4:2:2',
      compression_tier: 'TARGET_300_700KB',
      sha256: 's0',
      object_key: 'books/book_showcase_01/COVER.jpg',
      is_blank: false,
      preview_url: '/api/books/book_showcase_01/pages/COVER.jpg',
      download_url: '/api/books/book_showcase_01/pages/COVER.jpg?download=true',
    },
    {
      page_key: 'PAGE-01',
      filename: 'PAGE-01.jpg',
      page_kind: 'CONTENT',
      order_index: 1,
      source_pdf_page: 2,
      quadrant: 1,
      width_px: 1773,
      height_px: 2538,
      dpi: 300,
      file_size_bytes: 490_000,
      quality_used: 85,
      subsampling_used: '4:2:2',
      compression_tier: 'TARGET_300_700KB',
      sha256: 's1',
      object_key: 'books/book_showcase_01/PAGE-01.jpg',
      is_blank: false,
      preview_url: '/api/books/book_showcase_01/pages/PAGE-01.jpg',
      download_url: '/api/books/book_showcase_01/pages/PAGE-01.jpg?download=true',
    },
    {
      page_key: 'PAGE-02',
      filename: 'PAGE-02.jpg',
      page_kind: 'CONTENT',
      order_index: 2,
      source_pdf_page: 2,
      quadrant: 2,
      width_px: 1773,
      height_px: 2538,
      dpi: 300,
      file_size_bytes: 500_000,
      quality_used: 85,
      subsampling_used: '4:2:2',
      compression_tier: 'TARGET_300_700KB',
      sha256: 's2',
      object_key: 'books/book_showcase_01/PAGE-02.jpg',
      is_blank: false,
      preview_url: '/api/books/book_showcase_01/pages/PAGE-02.jpg',
      download_url: '/api/books/book_showcase_01/pages/PAGE-02.jpg?download=true',
    },
    {
      page_key: 'BACKCOVER',
      filename: 'BACKCOVER.jpg',
      page_kind: 'BACKCOVER',
      order_index: 3,
      source_pdf_page: 1,
      quadrant: null,
      width_px: 1886,
      height_px: 2657,
      dpi: 300,
      file_size_bytes: 550_000,
      quality_used: 82,
      subsampling_used: '4:2:0',
      compression_tier: 'TARGET_300_700KB',
      sha256: 's3',
      object_key: 'books/book_showcase_01/BACKCOVER.jpg',
      is_blank: false,
      preview_url: '/api/books/book_showcase_01/pages/BACKCOVER.jpg',
      download_url: '/api/books/book_showcase_01/pages/BACKCOVER.jpg?download=true',
    },
  ],
};

describe('Public Books Showcase (/books & /books/:id)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(healthApi.getHealth).mockResolvedValue({
      status: 'ok',
      app_name: 'Bookabook PDF Engine API',
      version: '1.0.0',
      database_connected: true,
      timestamp: '2026-11-11T10:00:00Z',
    });
  });

  it('lists published books on /books showcase page', async () => {
    vi.mocked(booksApi.listBooks).mockResolvedValue({
      total: 1,
      books: [SAMPLE_BOOK_DETAIL],
    });

    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/books']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Comic Anthology 2026')).toBeInTheDocument();
    });
    expect(screen.getByText('2 content pages')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Comic Anthology 2026/i })).toHaveAttribute(
      'href',
      '/books/book_showcase_01'
    );
  });

  it('navigates spreads, thumbnails, and provides Save Current Page + Download Book (ZIP) on /books/:id', async () => {
    const user = userEvent.setup();
    vi.mocked(booksApi.getBook).mockResolvedValue(SAMPLE_BOOK_DETAIL);

    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/books/book_showcase_01']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Comic Anthology 2026')).toBeInTheDocument();
    });

    expect(screen.getByText(/Front Cover/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download Book \(ZIP\)/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Save Current Page/i })).toBeInTheDocument();

    // Advance to interior spread PAGE-01 + PAGE-02
    await user.click(screen.getByRole('button', { name: /Next/i }));
    expect(screen.getByText(/PAGE-01 \+ PAGE-02/i)).toBeInTheDocument();

    // Advance to Backcover
    await user.click(screen.getByRole('button', { name: /Next/i }));
    expect(screen.getByText(/Back Cover/i)).toBeInTheDocument();
  });
});

