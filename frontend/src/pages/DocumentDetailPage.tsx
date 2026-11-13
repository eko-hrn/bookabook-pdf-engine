import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ClipboardCheck,
  Eye,
  FileText,
  FileUp,
  Layers,
  Loader2,
} from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ApiClientError, documentsApi, previewsApi } from '@/api';
import { DocumentLookupBar } from '@/components/DocumentLookupBar';
import { BookSpreadViewer } from '@/components/preview/BookSpreadViewer';
import { EmptyState, ErrorAlert, LoadingState } from '@/components/StateNotice';
import { StatusBadge } from '@/components/StatusBadge';
import { usePreviewImages } from '@/hooks/usePreviewImages';
import { useWorkspaceContext } from '@/hooks/useWorkspaceContext';
import { DocumentMetadataResponse, DocumentPreviewResponse } from '@/types/api';
import { buildBookSpreads } from '@/utils/bookSpreads';
import {
  formatBytes,
  formatLayoutLabel,
  formatTimestamp,
  validatePdfFile,
} from '@/utils/formatters';

export const DocumentDetailPage: React.FC = () => {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();
  const quickUploadRef = useRef<HTMLInputElement>(null);

  const {
    documents,
    activeDocumentId,
    registerDocument,
    setActiveDocumentId,
    getSessionIdForDocument,
  } = useWorkspaceContext();

  const [metadata, setMetadata] = useState<DocumentMetadataResponse | null>(null);
  const [preview, setPreview] = useState<DocumentPreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; statusCode?: number } | null>(null);

  // Embedded Book Spread Preview state
  const [activeSpreadIndex, setActiveSpreadIndex] = useState(0);
  const [viewMode, setViewMode] = useState<'spread' | 'sheet'>('spread');
  const [showOverlay, setShowOverlay] = useState(true);

  // Inline quick PDF upload inside Book Management card
  const [inlineUploading, setInlineUploading] = useState(false);
  const [inlineUploadError, setInlineUploadError] = useState<string | null>(null);

  const loadDocument = useCallback(
    async (docId: string) => {
      setLoading(true);
      setError(null);
      setPreviewError(null);
      setMetadata(null);
      setPreview(null);
      setActiveSpreadIndex(0);

      try {
        const meta = await documentsApi.getDocument(docId);
        setMetadata(meta);
        setActiveDocumentId(docId);
        registerDocument({
          document_id: meta.document_id,
          filename: meta.filename,
          page_count: meta.page_count,
        });

        try {
          const prev = await previewsApi.getDocumentPreview(docId);
          setPreview(prev);
        } catch (prevErr) {
          setPreviewError(
            prevErr instanceof Error
              ? prevErr.message
              : 'Crop preview calculation could not be loaded.'
          );
        }
      } catch (err) {
        if (err instanceof ApiClientError) {
          setError({ message: err.message, statusCode: err.statusCode });
        } else {
          setError({
            message: err instanceof Error ? err.message : 'Failed to load document metadata.',
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
      setMetadata(null);
      setPreview(null);
      setError(null);
      return;
    }
    void loadDocument(documentId);
  }, [documentId, loadDocument]);

  const previewPages = useMemo(() => preview?.pages ?? [], [preview]);
  const { spreads, thumbnails } = useMemo(
    () => buildBookSpreads(previewPages),
    [previewPages]
  );

  const { getImageEntry, loadImage, reloadImage } = usePreviewImages(
    documentId,
    previewPages,
    showOverlay,
    thumbnails
  );

  const handleInlinePdfUpload = async (file: File | null) => {
    if (!file || inlineUploading) return;
    setInlineUploadError(null);
    const check = await validatePdfFile(file);
    if (!check.valid) {
      setInlineUploadError(check.error || 'Selected file is not a valid PDF.');
      return;
    }

    setInlineUploading(true);
    try {
      const res = await documentsApi.uploadDocument(file);
      registerDocument({
        document_id: res.document_id,
        filename: res.filename,
        page_count: res.page_count,
      });
      navigate(`/documents/${encodeURIComponent(res.document_id)}`);
    } catch (err) {
      setInlineUploadError(
        err instanceof Error ? err.message : 'Failed to upload PDF document.'
      );
    } finally {
      setInlineUploading(false);
      if (quickUploadRef.current) {
        quickUploadRef.current.value = '';
      }
    }
  };

  // Landing view at /documents without an :documentId
  if (!documentId) {
    return (
      <div className="max-w-4xl ml-0 mr-auto space-y-4">
        <div className="bg-white border border-slate-200/90 rounded-lg shadow-card p-5 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h2 className="text-[15px] font-semibold text-slate-900">Books</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Look up an uploaded Document ID or pick a recently opened book below.
              </p>
            </div>
            <Link
              to="/upload"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-bookabook-teal text-white hover:bg-bookabook-tealHover"
            >
              <FileUp className="w-3.5 h-3.5" />
              New Book
            </Link>
          </div>
          <DocumentLookupBar mode="document" buttonLabel="Open Book" />
        </div>

        {documents.length > 0 ? (
          <div className="bg-white border border-slate-200/90 rounded-lg shadow-card overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-200/80">
              <h3 className="text-xs font-semibold text-slate-900">
                Recent Workspace Documents ({documents.length})
              </h3>
            </div>
            <div className="divide-y divide-slate-100 px-5">
              {documents.map((doc) => (
                <div key={doc.document_id} className="py-3 flex items-center justify-between gap-3">
                  <div>
                    <Link
                      to={`/documents/${encodeURIComponent(doc.document_id)}`}
                      className="text-xs font-semibold text-slate-900 hover:text-bookabook-teal hover:underline"
                    >
                      {doc.filename}
                    </Link>
                    <div className="text-[11px] font-mono text-slate-500 mt-0.5">
                      {doc.document_id}
                      {activeDocumentId === doc.document_id && ' (Active)'}
                    </div>
                  </div>
                  <Link
                    to={`/documents/${encodeURIComponent(doc.document_id)}`}
                    className="px-3 py-1 text-xs font-medium rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
                  >
                    Manage Book
                  </Link>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <EmptyState
            title="No Document Selected"
            description="Upload a PDF or enter an existing Document ID above to view metadata, book spreads, and crop regions."
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
    return <LoadingState label={`Loading book ${documentId}...`} />;
  }

  if (error || !metadata) {
    return (
      <div className="max-w-3xl ml-0 mr-auto space-y-4">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Books
        </Link>
        <ErrorAlert
          title="Unable to Load Document"
          message={error?.message || `Document ${documentId} not found.`}
          statusCode={error?.statusCode}
          onRetry={() => void loadDocument(documentId)}
        />
      </div>
    );
  }

  const mappedSessionId = getSessionIdForDocument(metadata.document_id);

  return (
    <div className="max-w-6xl ml-0 mr-auto space-y-4">
      {/* Unified Book Management Card Matching 01-edit-book.png & 02-book-preview.png */}
      <div className="bg-white border border-slate-200/90 rounded-lg shadow-card overflow-hidden">
        {/* Card Header Bar */}
        <div className="px-5 py-3.5 border-b border-slate-200/80 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <Link
              to="/"
              className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-900 shrink-0"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Books
            </Link>
            <span className="text-slate-300">|</span>
            <h2 className="text-[15px] font-semibold text-slate-900 truncate">
              {metadata.filename}
            </h2>
            <StatusBadge status={metadata.status} size="sm" />
            {preview && <StatusBadge status={preview.document_status} size="sm" />}
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <Link
              to={`/documents/${encodeURIComponent(metadata.document_id)}/preview`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <Eye className="w-3.5 h-3.5" />
              Full Preview Workspace
            </Link>
            <Link
              to={
                mappedSessionId
                  ? `/reviews/${encodeURIComponent(mappedSessionId)}`
                  : `/documents/${encodeURIComponent(metadata.document_id)}/review`
              }
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium rounded-md bg-bookabook-teal text-white hover:bg-bookabook-tealHover transition-colors"
            >
              <ClipboardCheck className="w-3.5 h-3.5" />
              {mappedSessionId ? 'Resume Review Session' : 'Open Review Workspace'}
            </Link>
          </div>
        </div>

        <div className="p-5 space-y-5">
          {/* Two-Column Filled Field Grid (01-edit-book.png) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
            <div>
              <div className="text-[11px] font-medium text-slate-500 mb-1">Filename*</div>
              <div className="px-3 py-2 text-xs font-medium text-slate-900 bg-bookabook-field border border-slate-200/70 rounded-md flex items-center gap-2 min-w-0">
                <FileText className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <span className="truncate">{metadata.filename}</span>
              </div>
            </div>

            <div>
              <div className="text-[11px] font-medium text-slate-500 mb-1">Document ID</div>
              <div className="px-3 py-2 text-xs font-mono text-slate-800 bg-bookabook-field border border-slate-200/70 rounded-md truncate">
                {metadata.document_id}
              </div>
            </div>

            <div>
              <div className="text-[11px] font-medium text-slate-500 mb-1">Content Pages / Size</div>
              <div className="px-3 py-2 text-xs text-slate-800 bg-bookabook-field border border-slate-200/70 rounded-md">
                {metadata.page_count} PDF sheets • {formatBytes(metadata.file_size_bytes)}
              </div>
            </div>

            <div>
              <div className="text-[11px] font-medium text-slate-500 mb-1">Created At</div>
              <div className="px-3 py-2 text-xs text-slate-800 bg-bookabook-field border border-slate-200/70 rounded-md">
                {formatTimestamp(metadata.created_at)}
              </div>
            </div>

            {preview && (
              <>
                <div>
                  <div className="text-[11px] font-medium text-slate-500 mb-1">
                    Preview Availability
                  </div>
                  <div className="px-3 py-2 text-xs font-semibold text-emerald-700 bg-bookabook-field border border-slate-200/70 rounded-md flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                    {preview.pages.length} Sheets Ready
                  </div>
                </div>

                <div>
                  <div className="text-[11px] font-medium text-slate-500 mb-1">
                    Expected Book Yield &amp; Validation
                  </div>
                  <div className="px-3 py-2 text-xs text-slate-800 bg-bookabook-field border border-slate-200/70 rounded-md flex items-center justify-between gap-2">
                    <span className="font-semibold text-slate-900">
                      {preview.expected_book_pages} pages
                    </span>
                    <span className="text-[11px] text-slate-500">
                      {preview.validation_summary.valid_regions_count}/
                      {preview.validation_summary.total_regions} valid
                    </span>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Inline PDF Upload Section ("Book images" parallel from 01-edit-book.png) */}
          <div className="space-y-1.5">
            <div className="text-[11px] font-medium text-slate-500">Book PDF Source</div>
            <div className="border border-dashed border-slate-300 rounded-md px-4 py-3 bg-bookabook-surface flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs text-slate-600">
                Upload another local PDF document to classify layouts and generate crop previews.
              </div>
              <div className="flex items-center gap-2">
                <input
                  ref={quickUploadRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  aria-label="Upload new PDF document"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0] ?? null;
                    void handleInlinePdfUpload(f);
                  }}
                />
                <button
                  type="button"
                  disabled={inlineUploading}
                  onClick={() => quickUploadRef.current?.click()}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 text-slate-700 rounded-md hover:bg-slate-50 disabled:opacity-50"
                >
                  {inlineUploading ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-bookabook-teal" />
                  ) : (
                    <FileUp className="w-3.5 h-3.5 text-bookabook-teal" />
                  )}
                  {inlineUploading ? 'Uploading PDF...' : 'Upload PDF'}
                </button>
              </div>
            </div>
            {inlineUploadError && (
              <p className="text-xs text-rose-600">{inlineUploadError}</p>
            )}
          </div>

          {/* Validation Alerts / Warnings */}
          {previewError ? (
            <ErrorAlert
              title="Preview Payload Unavailable"
              message={previewError}
              onRetry={() => void loadDocument(metadata.document_id)}
            />
          ) : (
            preview &&
            (preview.validation_summary.warnings.length > 0 ||
              preview.validation_summary.errors.length > 0) && (
              <div className="space-y-2 text-xs">
                {preview.validation_summary.errors.map((errMsg, idx) => (
                  <div
                    key={idx}
                    className="px-3 py-2 rounded-md bg-rose-50 border border-rose-200 text-rose-800"
                  >
                    {errMsg}
                  </div>
                ))}
                {preview.validation_summary.warnings.map((warnMsg, idx) => (
                  <div
                    key={idx}
                    className="px-3 py-2 rounded-md bg-amber-50 border border-amber-200 text-amber-800 flex items-start gap-2"
                  >
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    <span>{warnMsg}</span>
                  </div>
                ))}
              </div>
            )
          )}

          {/* Embedded Book Spread Preview + Bottom Thumbnail Strip (02-book-preview.png) */}
          {spreads.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-900">
                  <Layers className="w-3.5 h-3.5 text-bookabook-teal" />
                  <span>Book Preview</span>
                </div>
                <span className="text-[11px] text-slate-500">
                  Cover Spread standalone • Q1+Q2 &amp; Q3+Q4 interior spreads
                </span>
              </div>

              <BookSpreadViewer
                spreads={spreads}
                thumbnails={thumbnails}
                pages={previewPages}
                activeSpreadIndex={activeSpreadIndex}
                onSelectSpreadIndex={setActiveSpreadIndex}
                viewMode={viewMode}
                onChangeViewMode={setViewMode}
                showOverlay={showOverlay}
                onToggleOverlay={setShowOverlay}
                getImageEntry={getImageEntry}
                onEnsureImage={loadImage}
                onReloadImage={reloadImage}
                compact
              />
            </div>
          )}

          {/* Footer Action Strip Matching 02-book-preview.png */}
          <div className="pt-3 border-t border-slate-200/80 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Link
                to="/"
                className="px-3.5 py-1.5 text-xs font-medium rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </Link>
              <Link
                to={
                  mappedSessionId
                    ? `/reviews/${encodeURIComponent(mappedSessionId)}`
                    : `/documents/${encodeURIComponent(metadata.document_id)}/review`
                }
                className="px-3.5 py-1.5 text-xs font-medium rounded-md bg-bookabook-teal text-white hover:bg-bookabook-tealHover transition-colors"
              >
                {mappedSessionId ? 'Continue Review' : 'Start Review Session'}
              </Link>
            </div>

            <Link
              to={`/documents/${encodeURIComponent(metadata.document_id)}/preview`}
              className="text-xs font-medium text-bookabook-teal hover:underline"
            >
              Open Full Inspection Workspace →
            </Link>
          </div>
        </div>
      </div>

      {/* Per-Sheet Geometry & Layout Classification Table */}
      <div className="bg-white border border-slate-200/90 rounded-lg shadow-card overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-200/80 flex items-center justify-between">
          <h3 className="text-xs font-semibold text-slate-900">
            Sheet Geometry &amp; Layout Classification ({metadata.pages.length})
          </h3>
          <span className="text-[11px] text-slate-400">PDF point dimensions (72 pt/in)</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200/80 bg-bookabook-surface text-slate-500 uppercase tracking-wider text-[10px]">
                <th className="py-2 px-4 font-semibold">Sheet</th>
                <th className="py-2 px-4 font-semibold">Dimensions (pt)</th>
                <th className="py-2 px-4 font-semibold">Orientation</th>
                <th className="py-2 px-4 font-semibold">Detected Layout</th>
                <th className="py-2 px-4 font-semibold">Crop Readiness</th>
                <th className="py-2 px-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {metadata.pages.map((page) => {
                const previewInfo = preview?.pages.find(
                  (p) => p.page_number === page.page_number
                );
                return (
                  <tr key={page.page_number} className="hover:bg-slate-50/70">
                    <td className="py-2.5 px-4 font-semibold text-slate-900">
                      Sheet {page.page_number}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-slate-700">
                      {page.width_pt.toFixed(1)} × {page.height_pt.toFixed(1)} pt
                    </td>
                    <td className="py-2.5 px-4 text-slate-600">{page.orientation}</td>
                    <td className="py-2.5 px-4">
                      <span className="font-medium text-slate-900">
                        {formatLayoutLabel(page.detected_layout)}
                      </span>
                    </td>
                    <td className="py-2.5 px-4">
                      {previewInfo ? (
                        <StatusBadge status={previewInfo.crop_readiness} size="sm" />
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="py-2.5 px-4 text-right">
                      <Link
                        to={`/documents/${encodeURIComponent(metadata.document_id)}/preview?page=${page.page_number}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded border border-slate-200 text-slate-700 hover:bg-slate-50"
                      >
                        <Eye className="w-3 h-3 text-bookabook-teal" />
                        Inspect
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
