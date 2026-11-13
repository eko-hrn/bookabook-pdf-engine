import React, { useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  Archive,
  BookOpen,
  CheckCircle2,
  Download,
  FileText,
  FileUp,
  Image as ImageIcon,
  Loader2,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { ApiClientError, booksApi, extractErrorMessage } from '@/api';
import { ErrorAlert } from '@/components/StateNotice';
import {
  BookDetailResponse,
  ProcessedPageItem,
  ProcessPdfResponse,
} from '@/types/api';
import { formatBytes, validatePdfFile } from '@/utils/formatters';

interface MetadataFormState {
  title: string;
  author: string;
  authors_all: string;
  description: string;
  year: string;
  age_group: string;
  sponsor: string;
  content_pages: string;
  phone: string;
  email: string;
}

const INITIAL_FORM: MetadataFormState = {
  title: '',
  author: '',
  authors_all: '',
  description: '',
  year: String(new Date().getFullYear()),
  age_group: '',
  sponsor: '',
  content_pages: '',
  phone: '',
  email: '',
};

function triggerBrowserDownload(href: string, filename: string): void {
  const link = document.createElement('a');
  link.href = href;
  link.download = filename;
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export const CreateBookPage: React.FC = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [form, setForm] = useState<MetadataFormState>(INITIAL_FORM);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const [validatingFile, setValidatingFile] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

  const [processing, setProcessing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processError, setProcessError] = useState<ApiClientError | null>(null);
  const [processed, setProcessed] = useState<ProcessPdfResponse | null>(null);
  const [selectedPageKey, setSelectedPageKey] = useState<string>('COVER');

  const [savingBook, setSavingBook] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedBook, setSavedBook] = useState<BookDetailResponse | null>(null);

  const updateField = (key: keyof MetadataFormState, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSaveError(null);
  };

  const handleFileCandidate = async (file: File | null) => {
    setFileError(null);
    setProcessError(null);
    setSavedBook(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }

    setValidatingFile(true);
    const result = await validatePdfFile(file);
    setValidatingFile(false);

    if (!result.valid) {
      setSelectedFile(null);
      setFileError(result.error || 'Selected file is not a valid PDF.');
      return;
    }

    setSelectedFile(file);
    setProcessed(null);
    if (!form.title.trim()) {
      const cleanTitle = file.name.replace(/\.pdf$/i, '').replace(/[_-]+/g, ' ').trim();
      setForm((prev) => ({ ...prev, title: prev.title || cleanTitle }));
    }
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);
    const dropped = event.dataTransfer.files?.[0] ?? null;
    void handleFileCandidate(dropped);
  };

  const handleProcessPdf = async () => {
    if (!selectedFile) return;
    setProcessing(true);
    setUploadProgress(0);
    setProcessError(null);
    setSaveError(null);
    setSavedBook(null);

    try {
      const response = await booksApi.processPdf(selectedFile, (pct) => {
        setUploadProgress(pct);
      });
      setProcessed(response);
      setForm((prev) => ({
        ...prev,
        content_pages: String(response.content_pages_count),
      }));
      if (response.pages.length > 0) {
        setSelectedPageKey(response.pages[0].page_key);
      }
    } catch (err) {
      setProcessError(extractErrorMessage(err));
    } finally {
      setProcessing(false);
    }
  };

  const handleSaveBook = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!processed) {
      setSaveError('Please click Process PDF before saving the book.');
      return;
    }
    if (!form.title.trim()) {
      setSaveError('Title is required before saving to the public catalog.');
      return;
    }

    const parsedYear = form.year.trim() ? Number.parseInt(form.year.trim(), 10) : null;
    if (form.year.trim() && (Number.isNaN(parsedYear) || (parsedYear ?? 0) < 1900)) {
      setSaveError('Year must be a valid 4-digit year (e.g. 2026).');
      return;
    }

    const parsedContentPages = form.content_pages.trim()
      ? Number.parseInt(form.content_pages.trim(), 10)
      : processed.content_pages_count;

    setSavingBook(true);
    setSaveError(null);
    try {
      const created = await booksApi.saveBook({
        job_id: processed.job_id,
        title: form.title.trim(),
        author: form.author.trim(),
        authors_all: form.authors_all.trim(),
        description: form.description.trim(),
        year: parsedYear,
        age_group: form.age_group.trim(),
        sponsor: form.sponsor.trim(),
        content_pages: Number.isNaN(parsedContentPages)
          ? processed.content_pages_count
          : parsedContentPages,
        phone: form.phone.trim(),
        email: form.email.trim(),
      });
      setSavedBook(created);
    } catch (err) {
      setSaveError(extractErrorMessage(err).message);
    } finally {
      setSavingBook(false);
    }
  };

  const activePage: ProcessedPageItem | null = useMemo(() => {
    if (!processed || processed.pages.length === 0) return null;
    return (
      processed.pages.find((p) => p.page_key === selectedPageKey) ?? processed.pages[0]
    );
  }, [processed, selectedPageKey]);

  const clearPdf = () => {
    setSelectedFile(null);
    setProcessed(null);
    setFileError(null);
    setProcessError(null);
    setSavedBook(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="max-w-6xl space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Create Book</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Enter book metadata, upload the book PDF, inspect 300 DPI cropped JPG pages inline, and publish when ready.
          </p>
        </div>
        <Link
          to="/books"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 text-slate-700 rounded-md hover:bg-slate-50"
        >
          <BookOpen className="w-3.5 h-3.5 text-bookabook-teal" />
          Browse Books Showcase
        </Link>
      </div>

      {/* Saved Confirmation Banner */}
      {savedBook && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-md p-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
            <div>
              <div className="text-xs font-semibold text-emerald-900">
                Book Saved & Published to Showcase
              </div>
              <div className="text-[11px] text-emerald-800 mt-0.5">
                <span className="font-medium">{savedBook.title}</span> ({savedBook.total_exported_pages} JPGs @ 300 DPI) stored via{' '}
                <span className="font-mono">{savedBook.storage_backend}</span> storage.
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to={`/books/${encodeURIComponent(savedBook.book_id)}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-700 text-white rounded-md hover:bg-emerald-800"
            >
              View Book in Showcase
            </Link>
            <Link
              to="/books"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-emerald-300 text-emerald-800 rounded-md hover:bg-emerald-100"
            >
              All Books
            </Link>
          </div>
        </div>
      )}

      {/* Main Single-Page Form */}
      <form
        onSubmit={handleSaveBook}
        className="bg-white border border-slate-200 rounded-md p-5 space-y-5"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <label htmlFor="book-title" className="block text-xs font-medium text-slate-700 mb-1">
              Title <span className="text-rose-500">*</span>
            </label>
            <input
              id="book-title"
              type="text"
              required
              value={form.title}
              onChange={(e) => updateField('title', e.target.value)}
              placeholder="e.g. The COFA Comic Collection Vol. 1"
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal"
            />
          </div>

          <div>
            <label htmlFor="book-year" className="block text-xs font-medium text-slate-700 mb-1">
              Year
            </label>
            <input
              id="book-year"
              type="number"
              min={1900}
              max={2100}
              value={form.year}
              onChange={(e) => updateField('year', e.target.value)}
              placeholder="2026"
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal"
            />
          </div>

          <div>
            <label htmlFor="book-author" className="block text-xs font-medium text-slate-700 mb-1">
              Author
            </label>
            <input
              id="book-author"
              type="text"
              value={form.author}
              onChange={(e) => updateField('author', e.target.value)}
              placeholder="Lead author"
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal"
            />
          </div>

          <div className="lg:col-span-2">
            <label htmlFor="book-authors-all" className="block text-xs font-medium text-slate-700 mb-1">
              Authors All
            </label>
            <input
              id="book-authors-all"
              type="text"
              value={form.authors_all}
              onChange={(e) => updateField('authors_all', e.target.value)}
              placeholder="Comma-separated list of all contributors"
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal"
            />
          </div>

          <div className="md:col-span-2 lg:col-span-3">
            <label htmlFor="book-description" className="block text-xs font-medium text-slate-700 mb-1">
              Description
            </label>
            <textarea
              id="book-description"
              rows={2}
              value={form.description}
              onChange={(e) => updateField('description', e.target.value)}
              placeholder="Short book synopsis or edition notes"
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal"
            />
          </div>

          <div>
            <label htmlFor="book-age-group" className="block text-xs font-medium text-slate-700 mb-1">
              Age Group
            </label>
            <input
              id="book-age-group"
              type="text"
              value={form.age_group}
              onChange={(e) => updateField('age_group', e.target.value)}
              placeholder="e.g. 7-12"
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal"
            />
          </div>

          <div>
            <label htmlFor="book-sponsor" className="block text-xs font-medium text-slate-700 mb-1">
              Sponsor
            </label>
            <input
              id="book-sponsor"
              type="text"
              value={form.sponsor}
              onChange={(e) => updateField('sponsor', e.target.value)}
              placeholder="Publisher or studio sponsor"
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal"
            />
          </div>

          <div>
            <label htmlFor="book-content-pages" className="block text-xs font-medium text-slate-700 mb-1">
              Content Pages{' '}
              <span className="text-[10px] font-normal text-bookabook-teal">(Auto)</span>
            </label>
            <input
              id="book-content-pages"
              type="number"
              min={0}
              value={form.content_pages}
              onChange={(e) => updateField('content_pages', e.target.value)}
              placeholder="Auto-counted after Process PDF"
              className="w-full px-3 py-2 text-xs bg-slate-100 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal"
            />
          </div>

          <div>
            <label htmlFor="book-phone" className="block text-xs font-medium text-slate-700 mb-1">
              Phone
            </label>
            <input
              id="book-phone"
              type="text"
              value={form.phone}
              onChange={(e) => updateField('phone', e.target.value)}
              placeholder="+62..."
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal"
            />
          </div>

          <div className="lg:col-span-2">
            <label htmlFor="book-email" className="block text-xs font-medium text-slate-700 mb-1">
              Email
            </label>
            <input
              id="book-email"
              type="email"
              value={form.email}
              onChange={(e) => updateField('email', e.target.value)}
              placeholder="contact@bookabook.id"
              className="w-full px-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal"
            />
          </div>
        </div>

        {/* PDF Upload Dropzone */}
        <div className="pt-2 border-t border-slate-100 space-y-3">
          <label className="block text-xs font-medium text-slate-700">
            Book PDF File <span className="text-rose-500">*</span>{' '}
            <span className="text-[11px] font-normal text-slate-400">
              (Deterministic 300 DPI crop: COVER.jpg, PAGE-01..N.jpg, BACKCOVER.jpg — spine excluded)
            </span>
          </label>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
              if (!processing) setDragActive(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setDragActive(false);
            }}
            onDrop={handleDrop}
            className={`border border-dashed rounded-md px-5 py-6 text-center transition-colors ${
              dragActive
                ? 'border-bookabook-teal bg-bookabook-tealSoft/30'
                : 'border-slate-300 bg-slate-50/70 hover:border-slate-400'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              aria-label="Choose Book PDF"
              disabled={processing}
              onChange={(e) => {
                const file = e.target.files?.[0] ?? null;
                void handleFileCandidate(file);
              }}
              className="hidden"
            />
            <div className="w-8 h-8 rounded-full bg-white border border-slate-200 flex items-center justify-center mx-auto mb-2 text-bookabook-teal">
              <FileUp className="w-4 h-4" />
            </div>
            <p className="text-xs font-medium text-slate-800">
              Drag and drop the production PDF here, or select from computer
            </p>
            <button
              type="button"
              disabled={processing}
              onClick={() => fileInputRef.current?.click()}
              className="mt-2.5 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 text-slate-700 rounded-md hover:bg-slate-50"
            >
              Browse PDF
            </button>
          </div>

          {validatingFile && (
            <div className="flex items-center gap-2 text-xs text-slate-600">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-bookabook-teal" />
              Checking PDF header and size...
            </div>
          )}

          {fileError && (
            <ErrorAlert
              title="Invalid PDF File"
              message={fileError}
              onDismiss={() => setFileError(null)}
            />
          )}

          {processError && (
            <div className="space-y-2">
              <ErrorAlert
                title={
                  processError.compressionStatus === 'FAILED'
                    ? 'JPEG Compression Limit Exceeded'
                    : 'PDF Processing Failed'
                }
                message={processError.message}
                statusCode={processError.statusCode}
                onDismiss={() => setProcessError(null)}
              />
              {processError.compressionFailures && processError.compressionFailures.length > 0 && (
                <div className="bg-rose-50 border border-rose-200 rounded-md p-3 space-y-1.5 text-xs text-rose-900">
                  <div className="font-semibold">
                    Compression Quality Protection Triggered ({processError.compressionFailures.length} file
                    {processError.compressionFailures.length === 1 ? '' : 's'})
                  </div>
                  <ul className="space-y-1">
                    {processError.compressionFailures.map((fail) => (
                      <li key={fail.filename} className="text-[11px] bg-white/80 border border-rose-200 rounded px-2.5 py-1.5">
                        <span className="font-semibold">{fail.filename}</span> — Actual:{' '}
                        <span className="font-mono">{fail.actual_size_bytes.toLocaleString('en-US')} bytes</span>{' '}
                        ({formatBytes(fail.actual_size_bytes)}), Max allowed:{' '}
                        <span className="font-mono">{fail.max_allowed_bytes.toLocaleString('en-US')} bytes</span>{' '}
                        ({formatBytes(fail.max_allowed_bytes)}). {fail.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {selectedFile && (
            <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 border border-slate-200 rounded-md px-3.5 py-2.5">
              <div className="flex items-center gap-2.5 min-w-0">
                <FileText className="w-4 h-4 text-bookabook-teal shrink-0" />
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-slate-900 truncate">
                    {selectedFile.name}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    {formatBytes(selectedFile.size)} • Ready for deterministic 300 DPI crop
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {!processing && (
                  <button
                    type="button"
                    onClick={clearPdf}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs text-slate-600 bg-white border border-slate-200 rounded-md hover:bg-slate-100"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Clear
                  </button>
                )}

                <button
                  type="button"
                  disabled={processing || !selectedFile}
                  onClick={() => void handleProcessPdf()}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium bg-bookabook-teal text-white rounded-md hover:bg-bookabook-tealHover disabled:opacity-60"
                >
                  {processing ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      {uploadProgress < 100
                        ? `Uploading (${uploadProgress}%)...`
                        : 'Rendering 300 DPI pages & optimizing JPEG...'}
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      Process PDF
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {saveError && (
          <div className="bg-rose-50 border border-rose-200 rounded-md p-3 flex items-center gap-2 text-xs text-rose-800">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{saveError}</span>
          </div>
        )}

        {/* Action Footer for Save Book */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100">
          <span className="text-[11px] text-slate-500">
            {processed
              ? `Auto-validated ${processed.total_exported_files} JPG files (${processed.content_pages_count} content pages). Review results below, then click Save Book.`
              : 'Process a PDF first to preview cropped JPG outputs and enable Save Book.'}
          </span>

          <div className="flex items-center gap-2">
            {processed && (
              <button
                type="button"
                onClick={() =>
                  triggerBrowserDownload(
                    booksApi.getDownloadHref(processed.zip_download_url),
                    `${processed.job_id}.zip`
                  )
                }
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 text-slate-700 rounded-md hover:bg-slate-50"
              >
                <Archive className="w-3.5 h-3.5 text-bookabook-teal" />
                Save All Images (ZIP)
              </button>
            )}

            <button
              type="submit"
              disabled={!processed || savingBook}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium bg-bookabook-teal text-white rounded-md hover:bg-bookabook-tealHover disabled:opacity-50"
            >
              {savingBook ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Saving Book...
                </>
              ) : (
                <>
                  <Save className="w-3.5 h-3.5" />
                  Save Book
                </>
              )}
            </button>
          </div>
        </div>
      </form>

      {/* Inline Cropped Outputs Preview (Same Page — No Redirect to Review) */}
      {processed && (
        <section className="bg-white border border-slate-200 rounded-md p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Cropped JPG Outputs ({processed.total_exported_files} files • {processed.target_dpi} DPI RGB)
              </h2>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Auto-Validation:{' '}
                <span className="text-emerald-700 font-medium">
                  {processed.validation.is_valid ? 'PASSED' : 'FAILED'}
                </span>{' '}
                • COVER &amp; Inside ≤400 KB:{' '}
                {processed.validation.files_within_400kb ??
                  processed.pages.filter((p) => p.file_size_bytes <= 409_600).length}{' '}
                files • BACKCOVER ≤1 MB:{' '}
                {processed.validation.files_over_400kb_within_1mb ??
                  processed.pages.filter(
                    (p) => p.file_size_bytes > 409_600 && p.file_size_bytes <= 1_048_576
                  ).length}{' '}
                • Over limit: {processed.validation.files_over_policy_limit ?? 0}
              </p>
            </div>

            <div className="flex items-center gap-2">
              {activePage && (
                <button
                  type="button"
                  onClick={() =>
                    triggerBrowserDownload(
                      booksApi.getDownloadHref(activePage.download_url),
                      activePage.filename
                    )
                  }
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 text-slate-700 rounded-md hover:bg-slate-50"
                >
                  <Download className="w-3.5 h-3.5 text-bookabook-teal" />
                  Save Image ({activePage.filename})
                </button>
              )}
              <button
                type="button"
                onClick={() =>
                  triggerBrowserDownload(
                    booksApi.getDownloadHref(processed.zip_download_url),
                    `${processed.job_id}.zip`
                  )
                }
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-bookabook-teal text-white rounded-md hover:bg-bookabook-tealHover"
              >
                <Archive className="w-3.5 h-3.5" />
                Save All Images (ZIP)
              </button>
            </div>
          </div>

          {/* Focused Preview Panel */}
          {activePage && (
            <div className="bg-slate-50 border border-slate-200 rounded-md p-4 flex flex-col lg:flex-row gap-4 items-center">
              <div className="w-full lg:w-1/2 flex justify-center bg-white border border-slate-200 rounded p-2">
                <img
                  src={booksApi.getDownloadHref(activePage.preview_url)}
                  alt={`${activePage.filename} preview`}
                  style={{
                    aspectRatio: `${activePage.width_px} / ${activePage.height_px}`,
                  }}
                  className="max-h-[420px] w-auto object-contain rounded-sm"
                />
              </div>
              <div className="w-full lg:w-1/2 space-y-2 text-xs">
                <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-bookabook-tealSoft text-bookabook-teal font-semibold text-[11px]">
                  <ImageIcon className="w-3.5 h-3.5" />
                  {activePage.page_kind} • {activePage.filename}
                </div>
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <div className="bg-white border border-slate-200 rounded p-2.5">
                    <div className="text-[11px] text-slate-500">Resolution</div>
                    <div className="font-semibold text-slate-900">
                      {activePage.width_px} × {activePage.height_px} px
                    </div>
                  </div>
                  <div className="bg-white border border-slate-200 rounded p-2.5">
                    <div className="text-[11px] text-slate-500">JPEG Size</div>
                    <div className="font-semibold text-slate-900">
                      {formatBytes(activePage.file_size_bytes)}
                    </div>
                  </div>
                  <div className="bg-white border border-slate-200 rounded p-2.5">
                    <div className="text-[11px] text-slate-500">DPI / Color</div>
                    <div className="font-semibold text-slate-900">
                      {activePage.dpi} DPI • RGB
                    </div>
                  </div>
                  <div className="bg-white border border-slate-200 rounded p-2.5">
                    <div className="text-[11px] text-slate-500">Compression</div>
                    <div className="font-semibold text-slate-900">
                      q={activePage.quality_used} ({activePage.subsampling_used})
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Thumbnail Grid of All Output Pages */}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {processed.pages.map((page) => {
              const isSelected = activePage?.page_key === page.page_key;
              return (
                <div
                  key={page.page_key}
                  className={`border rounded-md p-2 flex flex-col justify-between transition-colors ${
                    isSelected
                      ? 'border-bookabook-teal bg-bookabook-tealSoft/20'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setSelectedPageKey(page.page_key)}
                    className="text-left space-y-1.5"
                  >
                    <div className="w-full aspect-[3/4] bg-slate-100 rounded overflow-hidden flex items-center justify-center">
                      <img
                        src={booksApi.getDownloadHref(page.preview_url)}
                        alt={page.filename}
                        loading="lazy"
                        className="max-h-full max-w-full object-contain"
                      />
                    </div>
                    <div className="flex items-center justify-between gap-1 text-[11px] font-semibold text-slate-800">
                      <span className="truncate">{page.filename}</span>
                    </div>
                    <div className="text-[10px] text-slate-500">
                      {formatBytes(page.file_size_bytes)} • q{page.quality_used}
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      triggerBrowserDownload(
                        booksApi.getDownloadHref(page.download_url),
                        page.filename
                      )
                    }
                    className="mt-2 w-full inline-flex items-center justify-center gap-1 px-2 py-1 text-[10px] font-medium bg-slate-50 border border-slate-200 text-slate-700 rounded hover:bg-slate-100"
                  >
                    <Download className="w-3 h-3" />
                    Save Image
                  </button>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
};

