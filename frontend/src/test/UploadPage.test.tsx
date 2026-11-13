import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiClientError, documentsApi, healthApi } from '@/api';
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

function createTestPdfFile(name = 'sample_book.pdf', content = '%PDF-1.7\n1 0 obj\n'): File {
  const file = new File([content], name, { type: 'application/pdf' });
  Object.defineProperty(file, 'arrayBuffer', {
    value: async () => new TextEncoder().encode(content).buffer,
  });
  return file;
}

describe('UploadPage', () => {
  beforeEach(() => {
    vi.mocked(healthApi.getHealth).mockResolvedValue({
      status: 'ok',
      app_name: 'Bookabook API',
      version: '1.0.0',
      database_connected: true,
      timestamp: '2026-11-11T10:00:00Z',
    });
  });

  it('rejects non-PDF files client-side before sending any upload request', async () => {
    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/upload']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    const input = screen.getByLabelText('Choose PDF file');
    const badFile = new File(['not a pdf'], 'document.txt', { type: 'text/plain' });

    fireEvent.change(input, { target: { files: [badFile] } });

    await waitFor(() => {
      expect(screen.getByText('Client PDF Validation Failed')).toBeInTheDocument();
    });
    expect(vi.mocked(documentsApi.uploadDocument)).not.toHaveBeenCalled();
  });

  it('uploads valid PDF with progress indicator and renders returned metadata + actions', async () => {
    const user = userEvent.setup();
    vi.mocked(documentsApi.uploadDocument).mockImplementation(async (_file, onProgress) => {
      onProgress?.(55);
      onProgress?.(100);
      return {
        document_id: 'doc_abc123',
        filename: 'sample_book.pdf',
        file_size_bytes: 2_450_000,
        page_count: 6,
        created_at: '2026-11-11T10:15:00Z',
        status: 'UPLOADED',
      };
    });

    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/upload']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    const input = screen.getByLabelText('Choose PDF file');
    const pdfFile = createTestPdfFile('sample_book.pdf');
    fireEvent.change(input, { target: { files: [pdfFile] } });

    await waitFor(() => {
      expect(screen.getByText('PDF header verified')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /Upload & Analyze PDF/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/PDF Uploaded & Registered Successfully/i)
      ).toBeInTheDocument();
    });

    expect(screen.getAllByText('doc_abc123').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/6 sheets.*2\.34 MB/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open Document Detail/i })).toHaveAttribute(
      'href',
      '/documents/doc_abc123'
    );
    expect(screen.getByRole('link', { name: /Open Preview Workspace/i })).toHaveAttribute(
      'href',
      '/documents/doc_abc123/preview'
    );
  });

  it('displays normalized backend HTTP error when upload fails on server', async () => {
    const user = userEvent.setup();
    vi.mocked(documentsApi.uploadDocument).mockRejectedValue(
      new ApiClientError('Uploaded file is malformed or corrupted PDF.', {
        statusCode: 400,
      })
    );

    render(
      <WorkspaceProvider>
        <MemoryRouter initialEntries={['/upload']}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    );

    const input = screen.getByLabelText('Choose PDF file');
    fireEvent.change(input, { target: { files: [createTestPdfFile()] } });

    await waitFor(() => {
      expect(screen.getByText('PDF header verified')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /Upload & Analyze PDF/i }));

    await waitFor(() => {
      expect(screen.getByText('Upload Rejected by Backend')).toBeInTheDocument();
    });
    expect(screen.getByText('HTTP 400')).toBeInTheDocument();
    expect(
      screen.getByText('Uploaded file is malformed or corrupted PDF.')
    ).toBeInTheDocument();
  });
});

