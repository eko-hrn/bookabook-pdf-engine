import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowLeft, ClipboardCheck, Eye, FileText } from 'lucide-react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ApiClientError, previewsApi } from '@/api';
import { DocumentLookupBar } from '@/components/DocumentLookupBar';
import { BookSpreadViewer } from '@/components/preview/BookSpreadViewer';
import { PreviewInspector } from '@/components/preview/PreviewInspector';
import { EmptyState, ErrorAlert, LoadingState } from '@/components/StateNotice';
import { StatusBadge } from '@/components/StatusBadge';
import { usePreviewImages } from '@/hooks/usePreviewImages';
import { useWorkspaceContext } from '@/hooks/useWorkspaceContext';
import { DocumentPreviewResponse } from '@/types/api';
import { buildBookSpreads, findSpreadIndexForSheet } from '@/utils/bookSpreads';

export const PreviewWorkspacePage: React.FC = () => {
  const { documentId } = useParams<{ documentId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const {
    documents,
    activeDocumentId,
    setActiveDocumentId,
    registerDocument,
    getSessionIdForDocument,
  } = useWorkspaceContext();

  const [preview, setPreview] = useState<DocumentPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; statusCode?: number } | null>(null);
  const [viewMode, setViewMode] = useState<'spread' | 'sheet'>('spread');
  const [showOverlay, setShowOverlay] = useState(true);
  const [activeSpreadIndex, setActiveSpreadIndex] = useState(0);

  const loadPreview = useCallback(
    async (docId: string) => {
      setLoading(true);
      setError(null);
      setPreview(null);
      try {
        const data = await previewsApi.getDocumentPreview(docId);
        setPreview(data);
        setActiveDocumentId(docId);
        registerDocument({
          document_id: data.document_id,
          filename: data.source_filename,
          page_count: data.total_pages,
        });
      } catch (err) {
        if (err instanceof ApiClientError) {
          setError({ message: err.message, statusCode: err.statusCode });
        } else {
          setError({
            message: err instanceof Error ? err.message : 'Failed to load PDF crop preview.',
          });
        }
      } finally {
        setLoading(false);
      }
    },
    [registerDocument, setActiveDocumentId]
  );

  useEffect(() => {
    if (!documentId) {
      setPreview(null);
      setError(null);
      return;
    }
    void loadPreview(documentId);
  }, [documentId, loadPreview]);

  const pages = useMemo(() => preview?.pages ?? [], [preview]);
  const { spreads, thumbnails } = useMemo(() => buildBookSpreads(pages), [pages]);

  const rawPageParam = Number(searchParams.get('page') || '1');
  const currentPageNumber =
    pages.length > 0
      ? Math.min(Math.max(Number.isFinite(rawPageParam) ? rawPageParam : 1, 1), pages.length)
      : 1;

  // Keep spread index aligned when URL ?page= changes directly (e.g. from Detail link)
  useEffect(() => {
    if (spreads.length === 0) return;
    const activeSpread = spreads[activeSpreadIndex];
    if (!activeSpread || activeSpread.sheetPageNumber !== currentPageNumber) {
      setActiveSpreadIndex(findSpreadIndexForSheet(spreads, currentPageNumber));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPageNumber, spreads]);

  const { getImageEntry, loadImage, reloadImage } = usePreviewImages(
    documentId,
    pages,
    showOverlay,
    thumbnails
  );

  const selectSheet = useCallback(
    (pageNumber: number) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set('page', String(pageNumber));
          return next;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  const handleSelectSpreadIndex = useCallback(
    (nextIndex: number) => {
      if (spreads.length === 0) return;
      const clamped = Math.min(Math.max(nextIndex, 0), spreads.length - 1);
      setActiveSpreadIndex(clamped);
      const sheetNum = spreads[clamped]?.sheetPageNumber;
      if (sheetNum && sheetNum !== currentPageNumber) {
        selectSheet(sheetNum);
      }
    },
    [spreads, currentPageNumber, selectSheet]
  );

  const activePage = useMemo(() => {
    const spreadPage = spreads[activeSpreadIndex]?.sheetPage;
    return spreadPage ?? pages.find((p) => p.page_number === currentPageNumber) ?? pages[0];
  }, [spreads, activeSpreadIndex, pages, currentPageNumber]);

  // Keyboard navigation (Left / Right arrow keys) across book spreads
  useEffect(() => {
    if (!spreads.length) return;
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT')
      ) {
        return;
      }
      if (e.key === 'ArrowLeft' && activeSpreadIndex > 0) {
        e.preventDefault();
        handleSelectSpreadIndex(activeSpreadIndex - 1);
      } else if (e.key === 'ArrowRight' && activeSpreadIndex < spreads.length - 1) {
        e.preventDefault();
        handleSelectSpreadIndex(activeSpreadIndex + 1);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [activeSpreadIndex, spreads.length, handleSelectSpreadIndex]);

  // Landing view when /preview is visited directly without documentId
  if (!documentId) {
    return (
      <div className="max-w-4xl ml-0 mr-auto space-y-4">
        <div className="bg-white border border-slate-200/90 rounded-lg shadow-card p-5 space-y-3">
          <h2 className="text-[15px] font-semibold text-slate-900">Book Preview Workspace</h2>
          <p className="text-xs text-slate-500">
            Enter a Document ID to inspect backend-rendered Cover &amp; 4-Up Book Spreads, toggle
            crop overlays, and examine full PDF sheet geometry.
          </p>
          <DocumentLookupBar mode="preview" buttonLabel="Open Preview" />
        </div>

        {documents.length > 0 ? (
          <div className="bg-white border border-slate-200/90 rounded-lg shadow-card overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-200/80">
              <h3 className="text-xs font-semibold text-slate-900">Recent Workspace Documents</h3>
            </div>
            <div className="divide-y divide-slate-100 px-5">
              {documents.map((doc) => (
                <div key={doc.document_id} className="py-3 flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs font-semibold text-slate-900">{doc.filename}</div>
                    <div className="text-[11px] font-mono text-slate-500 mt-0.5">
                      {doc.document_id}
                      {activeDocumentId === doc.document_id && ' (Active)'}
                    </div>
                  </div>
                  <Link
                    to={`/documents/${encodeURIComponent(doc.document_id)}/preview`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-bookabook-teal text-white hover:bg-bookabook-tealHover"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    Inspect Preview
                  </Link>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <EmptyState
            title="No Document Loaded for Preview"
            description="Upload a PDF or open an existing Document ID above to view Book Spreads and visual crop overlays."
            action={
              <Link
                to="/upload"
                className="px-3.5 py-1.5 text-xs font-medium rounded-md bg-bookabook-teal text-white hover:bg-bookabook-tealHover"
              >
                New Book
              </Link>
            }
          />
        )}
      </div>
    );
  }

  if (loading) {
    return <LoadingState label={`Calculating and preparing crop preview for ${documentId}...`} />;
  }

  if (error || !preview || !activePage) {
    return (
      <div className="max-w-3xl ml-0 mr-auto space-y-4">
        <Link
          to={documentId ? `/documents/${encodeURIComponent(documentId)}` : '/'}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Document Detail
        </Link>
        <ErrorAlert
          title="Unable to Load Preview Workspace"
          message={error?.message || 'No preview pages were returned by the backend.'}
          statusCode={error?.statusCode}
          onRetry={() => void loadPreview(documentId)}
        />
      </div>
    );
  }

  const mappedSessionId = getSessionIdForDocument(preview.document_id);

  return (
    <div className="max-w-[1520px] ml-0 mr-auto space-y-4">
      {/* Compact Top Book Strip */}
      <div className="bg-white border border-slate-200/90 rounded-lg shadow-card px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3 min-w-0">
          <Link
            to={`/documents/${encodeURIComponent(preview.document_id)}`}
            className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-900"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Manage Book
          </Link>
          <span className="text-slate-300">|</span>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <FileText className="w-3.5 h-3.5 text-bookabook-teal shrink-0" />
              <h2 className="text-xs font-semibold text-slate-900 truncate max-w-md">
                {preview.source_filename}
              </h2>
              <StatusBadge status={preview.document_status} size="sm" />
            </div>
            <div className="text-[11px] font-mono text-slate-500 mt-0.5">
              {preview.document_id} • {preview.total_pages} sheets • {preview.expected_book_pages}{' '}
              expected book pages
            </div>
          </div>
        </div>

        <Link
          to={
            mappedSessionId
              ? `/reviews/${encodeURIComponent(mappedSessionId)}`
              : `/documents/${encodeURIComponent(preview.document_id)}/review`
          }
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium rounded-md bg-bookabook-teal text-white hover:bg-bookabook-tealHover transition-colors shrink-0"
        >
          <ClipboardCheck className="w-3.5 h-3.5" />
          {mappedSessionId ? 'Open Review Session' : 'Start Review Session'}
        </Link>
      </div>

      {/* Book Spread Viewer + Right-Hand Crop Metadata Inspector */}
      <div className="flex flex-col xl:flex-row gap-4 items-stretch xl:items-start">
        <div className="flex-1 min-w-0">
          <BookSpreadViewer
            spreads={spreads}
            thumbnails={thumbnails}
            pages={pages}
            activeSpreadIndex={activeSpreadIndex}
            onSelectSpreadIndex={handleSelectSpreadIndex}
            viewMode={viewMode}
            onChangeViewMode={setViewMode}
            showOverlay={showOverlay}
            onToggleOverlay={setShowOverlay}
            getImageEntry={getImageEntry}
            onEnsureImage={loadImage}
            onReloadImage={reloadImage}
            onSelectSheetPage={selectSheet}
          />
        </div>

        <PreviewInspector
          documentId={preview.document_id}
          preview={preview}
          page={activePage}
        />
      </div>
    </div>
  );
};
