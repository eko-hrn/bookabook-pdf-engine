import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Archive,
  ArrowLeft,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Columns2,
  Download,
  Mail,
  Phone,
  Square,
} from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { booksApi, extractErrorMessage } from '@/api';
import { ErrorAlert, LoadingState } from '@/components/StateNotice';
import { BookDetailResponse, BookPageDetail } from '@/types/api';
import { formatBytes } from '@/utils/formatters';

interface ReaderFrame {
  id: string;
  title: string;
  subtitle: string;
  left?: BookPageDetail;
  right?: BookPageDetail;
  single?: BookPageDetail;
}

function buildShowcaseFrames(pages: BookPageDetail[], spreadMode: boolean): ReaderFrame[] {
  if (!spreadMode) {
    return pages.map((page) => ({
      id: page.page_key,
      title: page.page_key,
      subtitle: `${page.width_px}×${page.height_px} px • ${formatBytes(page.file_size_bytes)}`,
      single: page,
    }));
  }

  const frames: ReaderFrame[] = [];
  const cover = pages.find((p) => p.page_kind === 'COVER');
  const backcover = pages.find((p) => p.page_kind === 'BACKCOVER');
  const interiors = pages.filter((p) => p.page_kind === 'CONTENT');

  if (cover) {
    frames.push({
      id: 'COVER',
      title: 'Front Cover',
      subtitle: `${cover.filename} • ${cover.width_px}×${cover.height_px} px`,
      single: cover,
    });
  }

  for (let i = 0; i < interiors.length; i += 2) {
    const left = interiors[i];
    const right = interiors[i + 1];
    frames.push({
      id: right ? `${left.page_key}-${right.page_key}` : left.page_key,
      title: right ? `${left.page_key} + ${right.page_key}` : left.page_key,
      subtitle: right
        ? `${left.filename} & ${right.filename}`
        : left.filename,
      left: right ? left : undefined,
      right,
      single: right ? undefined : left,
    });
  }

  if (backcover) {
    frames.push({
      id: 'BACKCOVER',
      title: 'Back Cover',
      subtitle: `${backcover.filename} • ${backcover.width_px}×${backcover.height_px} px`,
      single: backcover,
    });
  }

  return frames;
}

function triggerFileDownload(href: string, filename: string): void {
  const link = document.createElement('a');
  link.href = href;
  link.download = filename;
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export const BookViewerPage: React.FC = () => {
  const { bookId } = useParams<{ bookId: string }>();
  const [book, setBook] = useState<BookDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [spreadMode, setSpreadMode] = useState(true);
  const [frameIndex, setFrameIndex] = useState(0);

  const loadBook = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    setFrameIndex(0);
    try {
      const detail = await booksApi.getBook(id);
      setBook(detail);
    } catch (err) {
      setError(extractErrorMessage(err).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!bookId) return;
    void loadBook(bookId);
  }, [bookId, loadBook]);

  const frames = useMemo(() => {
    if (!book) return [];
    return buildShowcaseFrames(book.pages, spreadMode);
  }, [book, spreadMode]);

  const activeFrame = frames[Math.min(frameIndex, Math.max(frames.length - 1, 0))] ?? null;
  const currentPrimaryPage: BookPageDetail | null =
    activeFrame?.single ?? activeFrame?.left ?? activeFrame?.right ?? null;

  const jumpToPage = (pageKey: string) => {
    const idx = frames.findIndex(
      (f) =>
        f.single?.page_key === pageKey ||
        f.left?.page_key === pageKey ||
        f.right?.page_key === pageKey
    );
    if (idx >= 0) setFrameIndex(idx);
  };

  if (loading) return <LoadingState label="Opening Bookabook viewer..." />;

  if (error || !book) {
    return (
      <div className="max-w-4xl space-y-4">
        <Link
          to="/books"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-bookabook-teal hover:underline"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Books Showcase
        </Link>
        <ErrorAlert
          title="Book Not Available"
          message={error || 'Requested book could not be found.'}
        />
      </div>
    );
  }

  return (
    <div className="max-w-6xl space-y-4">
      {/* Top Breadcrumb + Action Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            to="/books"
            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium bg-white border border-slate-200 text-slate-700 rounded-md hover:bg-slate-50 shrink-0"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Books
          </Link>
          <div className="min-w-0">
            <h1 className="text-base font-semibold text-slate-900 truncate">{book.title}</h1>
            <p className="text-[11px] text-slate-500 truncate">
              {book.author || book.authors_all || 'Bookabook Edition'}
              {book.year ? ` • ${book.year}` : ''}
              {book.age_group ? ` • Ages ${book.age_group}` : ''}
              {book.sponsor ? ` • Sponsor: ${book.sponsor}` : ''}
              {` • ${book.content_pages} content pages`}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setSpreadMode((prev) => !prev);
              setFrameIndex(0);
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 text-slate-700 rounded-md hover:bg-slate-50"
          >
            {spreadMode ? (
              <>
                <Square className="w-3.5 h-3.5 text-bookabook-teal" />
                Single Page View
              </>
            ) : (
              <>
                <Columns2 className="w-3.5 h-3.5 text-bookabook-teal" />
                Spread View
              </>
            )}
          </button>

          {currentPrimaryPage && (
            <button
              type="button"
              onClick={() =>
                triggerFileDownload(
                  booksApi.getDownloadHref(currentPrimaryPage.download_url),
                  currentPrimaryPage.filename
                )
              }
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 text-slate-700 rounded-md hover:bg-slate-50"
            >
              <Download className="w-3.5 h-3.5 text-bookabook-teal" />
              Save Current Page
            </button>
          )}

          <button
            type="button"
            onClick={() =>
              triggerFileDownload(
                booksApi.getDownloadHref(book.zip_download_url),
                `${book.book_id}.zip`
              )
            }
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium bg-bookabook-teal text-white rounded-md hover:bg-bookabook-tealHover"
          >
            <Archive className="w-3.5 h-3.5" />
            Download Book (ZIP)
          </button>
        </div>
      </div>

      {/* Main Reader Stage */}
      <div className="bg-slate-100 border border-slate-200 rounded-md p-4 sm:p-6 space-y-4">
        <div className="flex items-center justify-between text-xs text-slate-600">
          <div className="font-medium text-slate-800">
            {activeFrame?.title ?? 'Reader'} —{' '}
            <span className="text-slate-500 font-normal">{activeFrame?.subtitle}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={frameIndex <= 0}
              onClick={() => setFrameIndex((i) => Math.max(0, i - 1))}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-white border border-slate-200 rounded text-slate-700 hover:bg-slate-50 disabled:opacity-40"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              Previous
            </button>
            <span className="text-[11px] font-medium px-1.5">
              {frameIndex + 1} / {Math.max(frames.length, 1)}
            </span>
            <button
              type="button"
              disabled={frameIndex >= frames.length - 1}
              onClick={() => setFrameIndex((i) => Math.min(frames.length - 1, i + 1))}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-white border border-slate-200 rounded text-slate-700 hover:bg-slate-50 disabled:opacity-40"
            >
              Next
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Artwork Container (Preserves Exact Aspect Ratios) */}
        <div className="min-h-[420px] flex items-center justify-center">
          {activeFrame?.left && activeFrame?.right ? (
            <div className="grid grid-cols-2 gap-1 sm:gap-2 max-w-4xl w-full bg-white p-2 sm:p-3 rounded shadow-sm border border-slate-200">
              <div className="flex justify-end items-center bg-slate-50">
                <img
                  src={booksApi.getDownloadHref(activeFrame.left.preview_url)}
                  alt={activeFrame.left.filename}
                  style={{
                    aspectRatio: `${activeFrame.left.width_px} / ${activeFrame.left.height_px}`,
                  }}
                  className="max-h-[540px] w-auto object-contain"
                />
              </div>
              <div className="flex justify-start items-center bg-slate-50">
                <img
                  src={booksApi.getDownloadHref(activeFrame.right.preview_url)}
                  alt={activeFrame.right.filename}
                  style={{
                    aspectRatio: `${activeFrame.right.width_px} / ${activeFrame.right.height_px}`,
                  }}
                  className="max-h-[540px] w-auto object-contain"
                />
              </div>
            </div>
          ) : activeFrame?.single ? (
            <div className="bg-white p-2 sm:p-3 rounded shadow-sm border border-slate-200 inline-flex justify-center">
              <img
                src={booksApi.getDownloadHref(activeFrame.single.preview_url)}
                alt={activeFrame.single.filename}
                style={{
                  aspectRatio: `${activeFrame.single.width_px} / ${activeFrame.single.height_px}`,
                }}
                className="max-h-[540px] w-auto object-contain"
              />
            </div>
          ) : null}
        </div>

        {/* Bottom Horizontal Thumbnail Navigation */}
        <div className="pt-2 border-t border-slate-200/80 overflow-x-auto">
          <div className="flex items-center gap-2 pb-1">
            {book.pages.map((page) => {
              const isActive =
                activeFrame?.single?.page_key === page.page_key ||
                activeFrame?.left?.page_key === page.page_key ||
                activeFrame?.right?.page_key === page.page_key;
              return (
                <button
                  key={page.page_key}
                  type="button"
                  onClick={() => jumpToPage(page.page_key)}
                  className={`shrink-0 w-16 p-1 rounded border text-center transition-colors ${
                    isActive
                      ? 'border-bookabook-teal bg-white ring-1 ring-bookabook-teal'
                      : 'border-slate-200 bg-white/80 hover:border-slate-300'
                  }`}
                >
                  <div className="h-20 flex items-center justify-center bg-slate-50 rounded-sm overflow-hidden">
                    <img
                      src={booksApi.getDownloadHref(page.preview_url)}
                      alt={page.page_key}
                      loading="lazy"
                      className="max-h-full max-w-full object-contain"
                    />
                  </div>
                  <div className="mt-1 text-[10px] font-medium text-slate-700 truncate">
                    {page.page_key}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Book Metadata Panel */}
      <div className="bg-white border border-slate-200 rounded-md p-4 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        <div className="md:col-span-2 space-y-1.5">
          <div className="font-semibold text-slate-800 flex items-center gap-1.5">
            <BookOpen className="w-3.5 h-3.5 text-bookabook-teal" />
            Book Details
          </div>
          <p className="text-slate-600 leading-relaxed">
            {book.description || 'No synopsis provided for this book edition.'}
          </p>
          {book.authors_all && (
            <p className="text-[11px] text-slate-500">
              <span className="font-medium text-slate-700">Contributors:</span> {book.authors_all}
            </p>
          )}
        </div>
        <div className="space-y-1.5 text-[11px] text-slate-600 border-t md:border-t-0 md:border-l border-slate-100 pt-3 md:pt-0 md:pl-4">
          <div className="font-semibold text-slate-800">Publisher & Contact</div>
          {book.sponsor && (
            <div>
              <span className="text-slate-500">Sponsor:</span> {book.sponsor}
            </div>
          )}
          {book.phone && (
            <div className="flex items-center gap-1.5">
              <Phone className="w-3 h-3 text-slate-400" />
              {book.phone}
            </div>
          )}
          {book.email && (
            <div className="flex items-center gap-1.5">
              <Mail className="w-3 h-3 text-slate-400" />
              {book.email}
            </div>
          )}
          <div className="text-slate-400 pt-1">
            {book.total_exported_pages} JPG pages @ 300 DPI ({book.storage_backend})
          </div>
        </div>
      </div>
    </div>
  );
};

