import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { booksApi, healthApi } from '@/api';
import { ApiClientError } from '@/api/client';
import { AppRoutes } from '@/App';
import { WorkspaceProvider } from '@/hooks/useWorkspaceContext';
import { BookDetailResponse, ProcessPdfResponse } from '@/types/api';

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

function createTestPdfFile(name = 'cofa_comic.pdf', content = '%PDF-1.7\n1 0 obj\n'): File {
  const file = new File([content], name, { type: 'application/pdf' });
  Object.defineProperty(file, 'arrayBuffer', {
    value: async () => new TextEncoder().encode(content).buffer,
  });
  return file;
}

const MOCK_PROCESS_RES: ProcessPdfResponse = {
  job_id: 'job_123456789abc',
  source_filename: 'cofa_comic.pdf',
  target_dpi: 300,
  content_pages_count: 4,
  total_exported_files: 6,
  zip_download_url: '/api/books/jobs/job_123456789abc/download.zip',
  validation: {
    is_valid: true,
    auto_validated: true,
    total_pdf_pages: 2,
    cover_detected: true,
    backcover_detected: true,
    content_pages_count: 4,
    blank_pages_detected: 0,
    total_exported_files: 6,
    files_under_300kb: 0,
    files_300_to_700kb: 6,
    files_700kb_to_1mb: 0,
    files_1mb_to_2mb: 0,
    files_over_2mb: 0,
    warnings: [],
    errors: [],
  },
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
      file_size_bytes: 510_000,
      quality_used: 84,
      subsampling_used: '4:2:2',
      compression_tier: 'TARGET_300_700KB',
      is_blank: false,
      sha256: 'abc0',
      preview_url: '/api/books/jobs/job_123456789abc/images/COVER.jpg',
      download_url: '/api/books/jobs/job_123456789abc/images/COVER.jpg?download=true',
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
      is_blank: false,
      sha256: 'abc1',
      preview_url: '/api/books/jobs/job_123456789abc/images/PAGE-01.jpg',
      download_url: '/api/books/jobs/job_123456789abc/images/PAGE-01.jpg?download=true',
    },
    {
      page_key: 'BACKCOVER',
      filename: 'BACKCOVER.jpg',
      page_kind: 'BACKCOVER',
      order_index: 2,
      source_pdf_page: 1,
      quadrant: null,
      width_px: 1886,
      height_px: 2657,
      dpi: 300,
      file_size_bytes: 520_000,
      quality_used: 82,
      subsampling_used: '4:2:0',
      compression_tier: 'TARGET_300_700KB',
      is_blank: false,
      sha256: 'abc2',
      preview_url: '/api/books/jobs/job_123456789abc/images/BACKCOVER.jpg',
      download_url: '/api/books/jobs/job_123456789abc/images/BACKCOVER.jpg?download=true',
    },
  ],
};

const MOCK_SAVED_BOOK: BookDetailResponse = {
  book_id: 'book_9876543210aa',
  title: 'COFA Comic Vol. 1',
  author: 'Alleric Tansil',
  authors_all: 'Alleric Tansil, Allison Alexandra',
  description: 'A student comic showcase',
  year: 2026,
  age_group: '7-12',
  sponsor: 'COFA Studio',
  content_pages: 4,
  phone: '+62812345678',
  email: 'hello@bookabook.id',
  source_filename: 'cofa_comic.pdf',
  total_exported_pages: 6,
  cover_filename: 'COVER.jpg',
  backcover_filename: 'BACKCOVER.jpg',
  cover_url: '/api/books/book_9876543210aa/pages/COVER.jpg',
  storage_backend: 'local',
  created_at: '2026-11-11T10:00:00Z',
  validation_summary: {},
  zip_download_url: '/api/books/book_9876543210aa/download.zip',
  pages: [],
};

describe('CreateBookPage', () => {
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

  it('combines metadata form + PDF upload, renders inline crops without review redirect, and saves book', async () => {
    const user = userEvent.setup();
    vi.mocked(booksApi.processPdf).mockResolvedValue(MOCK_PROCESS_RES);
    vi.mocked(booksApi.saveBook).mockResolvedValue(MOCK_SAVED_BOOK);

    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/books/new']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    // Ensure sidebar has no manual Review link in normal workflow
    expect(screen.queryByRole('link', { name: /^Review$/i })).not.toBeInTheDocument();

    // Fill metadata fields
    await user.type(screen.getByLabelText(/Title/i), 'COFA Comic Vol. 1');
    await user.type(screen.getByLabelText(/^Author$/i), 'Alleric Tansil');
    await user.type(screen.getByLabelText(/Authors All/i), 'Alleric Tansil, Allison Alexandra');
    await user.type(screen.getByLabelText(/Description/i), 'A student comic showcase');
    await user.type(screen.getByLabelText(/Age Group/i), '7-12');
    await user.type(screen.getByLabelText(/Sponsor/i), 'COFA Studio');
    await user.type(screen.getByLabelText(/Phone/i), '+62812345678');
    await user.type(screen.getByLabelText(/Email/i), 'hello@bookabook.id');

    // Choose PDF and Process
    const fileInput = screen.getByLabelText('Choose Book PDF');
    fireEvent.change(fileInput, { target: { files: [createTestPdfFile()] } });

    const processBtn = await screen.findByRole('button', { name: /Process PDF/i });
    await user.click(processBtn);

    await waitFor(() => {
      expect(screen.getByText(/Cropped JPG Outputs/i)).toBeInTheDocument();
    });

    // Content Pages auto-populated
    expect((screen.getByLabelText(/Content Pages/i) as HTMLInputElement).value).toBe('4');

    // Cropped files and action buttons shown inline on same page
    expect(screen.getAllByText('COVER.jpg').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('PAGE-01.jpg').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('BACKCOVER.jpg').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('button', { name: /Save All Images \(ZIP\)/i }).length).toBeGreaterThanOrEqual(1);

    // Save Book persists metadata & shows showcase link
    await user.click(screen.getByRole('button', { name: /Save Book/i }));

    await waitFor(() => {
      expect(screen.getByText(/Book Saved & Published to Showcase/i)).toBeInTheDocument();
    });

    expect(vi.mocked(booksApi.saveBook)).toHaveBeenCalledWith(
      expect.objectContaining({
        job_id: 'job_123456789abc',
        title: 'COFA Comic Vol. 1',
        author: 'Alleric Tansil',
        sponsor: 'COFA Studio',
        content_pages: 4,
      })
    );
    expect(screen.getByRole('link', { name: /View Book in Showcase/i })).toHaveAttribute(
      'href',
      '/books/book_9876543210aa'
    );
  });

  it('displays structured compression failure details when min quality cannot satisfy size limit', async () => {
    const user = userEvent.setup();
    vi.mocked(booksApi.processPdf).mockRejectedValue(
      new ApiClientError('COVER.jpg compressed to 620,000 bytes at q=55, exceeding 512,000 bytes.', {
        statusCode: 422,
        compressionStatus: 'FAILED',
        compressionFailures: [
          {
            filename: 'COVER.jpg',
            page_key: 'COVER',
            page_kind: 'COVER',
            actual_size_bytes: 620_000,
            max_allowed_bytes: 512_000,
            min_quality_threshold: 55,
            quality_attempted: 55,
            reason: 'Exceeds 512,000 bytes (500 KB) even at minimum quality q=55.',
          },
        ],
      })
    );

    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/books/new']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    const fileInput = screen.getByLabelText('Choose Book PDF');
    fireEvent.change(fileInput, { target: { files: [createTestPdfFile()] } });
    const processBtn = await screen.findByRole('button', { name: /Process PDF/i });
    await user.click(processBtn);

    await waitFor(() => {
      expect(screen.getByText('JPEG Compression Limit Exceeded')).toBeInTheDocument();
    });
    expect(screen.getByText(/Compression Quality Protection Triggered/i)).toBeInTheDocument();
    expect(screen.getByText('COVER.jpg')).toBeInTheDocument();
    expect(screen.getAllByText(/620,000 bytes/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/512,000 bytes/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/605\.47 KB/i)).toBeInTheDocument();
    expect(screen.getByText(/500\.00 KB/i)).toBeInTheDocument();
  });
});

