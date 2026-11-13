import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Eye,
  FilePlus2,
  ImageOff,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ApiClientError, documentsApi, previewsApi, reviewsApi } from '@/api';
import { ConfirmRejectModal } from '@/components/ConfirmRejectModal';
import { DocumentLookupBar } from '@/components/DocumentLookupBar';
import { BookSpreadViewer } from '@/components/preview/BookSpreadViewer';
import { ReviewActionPanel } from '@/components/review/ReviewActionPanel';
import { ReviewHistoryTimeline } from '@/components/review/ReviewHistoryTimeline';
import { ReviewSummaryCard } from '@/components/review/ReviewSummaryCard';
import { EmptyState, ErrorAlert, LoadingState } from '@/components/StateNotice';
import { StatusBadge } from '@/components/StatusBadge';
import { usePreviewImages } from '@/hooks/usePreviewImages';
import { useWorkspaceContext } from '@/hooks/useWorkspaceContext';
import {
  DocumentMetadataResponse,
  DocumentPreviewResponse,
  PageReviewRecord,
  ReviewDecisionState,
  ReviewHistoryEntry,
  ReviewSession,
} from '@/types/api';
import { buildBookSpreads, findSpreadIndexForSheet } from '@/utils/bookSpreads';
import { formatLayoutLabel } from '@/utils/formatters';

export const ReviewWorkspacePage: React.FC = () => {
  const { documentId: routeDocumentId, sessionId: routeSessionId } = useParams<{
    documentId?: string;
    sessionId?: string;
  }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const {
    documents,
    sessions,
    reviewerId,
    setReviewerId,
    setActiveDocumentId,
    setActiveSessionId,
    registerDocument,
    registerSession,
    getSessionIdForDocument,
  } = useWorkspaceContext();

  const [session, setSession] = useState<ReviewSession | null>(null);
  const [historyEntries, setHistoryEntries] = useState<ReviewHistoryEntry[]>([]);
  const [historyFilterPage, setHistoryFilterPage] = useState<number | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [docMeta, setDocMeta] = useState<DocumentMetadataResponse | null>(null);
  const [previewMeta, setPreviewMeta] = useState<DocumentPreviewResponse | null>(null);

  const [customSessionIdInput, setCustomSessionIdInput] = useState('');
  const [creatingSession, setCreatingSession] = useState(false);
  const [loading, setLoading] = useState(false);
  const [submittingAction, setSubmittingAction] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [error, setError] = useState<{ message: string; statusCode?: number } | null>(null);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  // Spread + overlay controls inside Review inspection panel
  const [viewMode, setViewMode] = useState<'spread' | 'sheet'>('spread');
  const [showOverlay, setShowOverlay] = useState(true);
  const [activeSpreadIndex, setActiveSpreadIndex] = useState(0);

  const mappedDocSessionId = routeDocumentId
    ? getSessionIdForDocument(routeDocumentId)
    : undefined;
  const effectiveSessionId =
    routeSessionId || searchParams.get('sessionId') || mappedDocSessionId;

  const resolvedDocumentId = useMemo(() => {
    const metaDocId =
      session?.metadata && typeof session.metadata.document_id === 'string'
        ? session.metadata.document_id
        : undefined;
    return routeDocumentId || metaDocId;
  }, [routeDocumentId, session]);

  const loadHistory = useCallback(async (sid: string, pageNum: number | null) => {
    setHistoryLoading(true);
    try {
      const entries = await reviewsApi.getHistory(sid, pageNum ?? undefined);
      setHistoryEntries(entries);
    } catch {
      // Keep previous entries if history poll fails transiently
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const fetchSessionBundle = useCallback(
    async (sid: string) => {
      setLoading(true);
      setError(null);
      try {
        const loadedSession = await reviewsApi.getSession(sid);
        setSession(loadedSession);
        setHistoryEntries(loadedSession.history?.entries ?? []);
        setActiveSessionId(loadedSession.session_id);

        const metaDocId =
          loadedSession.metadata && typeof loadedSession.metadata.document_id === 'string'
            ? loadedSession.metadata.document_id
            : routeDocumentId;

        registerSession({
          session_id: loadedSession.session_id,
          document_id: metaDocId,
          source_filename: loadedSession.source_filename,
        });

        if (metaDocId) {
          setActiveDocumentId(metaDocId);
          try {
            const prev = await previewsApi.getDocumentPreview(metaDocId);
            setPreviewMeta(prev);
            registerDocument({
              document_id: prev.document_id,
              filename: prev.source_filename,
              page_count: prev.total_pages,
            });
          } catch {
            // Preview failure should not block reviewing session records
          }
        }
      } catch (err) {
        setSession(null);
        if (err instanceof ApiClientError) {
          setError({ message: err.message, statusCode: err.statusCode });
        } else {
          setError({
            message: err instanceof Error ? err.message : 'Failed to load review session.',
          });
        }
      } finally {
        setLoading(false);
      }
    },
    [
      registerDocument,
      registerSession,
      routeDocumentId,
      setActiveDocumentId,
      setActiveSessionId,
    ]
  );

  // Load either existing session OR document prompt to create a new session
  useEffect(() => {
    setActionFeedback(null);
    setError(null);

    if (effectiveSessionId) {
      void fetchSessionBundle(effectiveSessionId);
      return;
    }

    setSession(null);
    setHistoryEntries([]);
    setPreviewMeta(null);

    if (routeDocumentId) {
      setLoading(true);
      Promise.allSettled([
        documentsApi.getDocument(routeDocumentId),
        previewsApi.getDocumentPreview(routeDocumentId),
      ])
        .then(([docRes, prevRes]) => {
          if (docRes.status === 'fulfilled') {
            setDocMeta(docRes.value);
            setActiveDocumentId(docRes.value.document_id);
            registerDocument({
              document_id: docRes.value.document_id,
              filename: docRes.value.filename,
              page_count: docRes.value.page_count,
            });
          } else {
            const reason = docRes.reason;
            setError({
              message:
                reason instanceof Error ? reason.message : `Document ${routeDocumentId} not found.`,
              statusCode: reason instanceof ApiClientError ? reason.statusCode : undefined,
            });
          }

          if (prevRes.status === 'fulfilled') {
            setPreviewMeta(prevRes.value);
          }
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [
    effectiveSessionId,
    fetchSessionBundle,
    registerDocument,
    routeDocumentId,
    setActiveDocumentId,
  ]);

  // Refetch filtered history when filter toggles while session exists
  useEffect(() => {
    if (session?.session_id) {
      void loadHistory(session.session_id, historyFilterPage);
    }
  }, [session?.session_id, historyFilterPage, loadHistory]);

  const previewPages = useMemo(() => previewMeta?.pages ?? [], [previewMeta]);
  const { spreads, thumbnails } = useMemo(
    () => buildBookSpreads(previewPages),
    [previewPages]
  );

  const {
    images,
    getImageEntry,
    loadImage,
    reloadImage,
    loadPageImage,
    reloadPageImage,
  } = usePreviewImages(resolvedDocumentId, previewPages, showOverlay, thumbnails);

  const pageRecords: PageReviewRecord[] = useMemo(
    () => session?.page_records ?? [],
    [session]
  );

  const rawPage = Number(searchParams.get('page') || '1');
  const activePageNumber =
    pageRecords.length > 0
      ? Math.min(Math.max(Number.isFinite(rawPage) ? rawPage : 1, 1), pageRecords.length)
      : 1;

  const activeRecord = useMemo(
    () =>
      pageRecords.find((r) => r.pdf_page_number === activePageNumber) ?? pageRecords[0],
    [pageRecords, activePageNumber]
  );

  const activePreviewInfo = useMemo(
    () => previewPages.find((p) => p.page_number === activePageNumber),
    [previewPages, activePageNumber]
  );

  // Sync spread viewer when active review sheet changes via Sheet Queue
  useEffect(() => {
    if (spreads.length === 0) return;
    const currentSpread = spreads[activeSpreadIndex];
    if (!currentSpread || currentSpread.sheetPageNumber !== activePageNumber) {
      setActiveSpreadIndex(findSpreadIndexForSheet(spreads, activePageNumber));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePageNumber, spreads]);

  // Ensure sheet PNG is fetched cleanly when no rich preview spread exists for this sheet
  useEffect(() => {
    if (resolvedDocumentId && activePageNumber && !activePreviewInfo) {
      void loadPageImage(activePageNumber);
    }
  }, [resolvedDocumentId, activePageNumber, activePreviewInfo, loadPageImage]);

  const selectPage = useCallback(
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
      if (sheetNum && sheetNum !== activePageNumber) {
        selectPage(sheetNum);
      }
    },
    [spreads, activePageNumber, selectPage]
  );

  const handleCreateSession = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!routeDocumentId || creatingSession) return;

    setCreatingSession(true);
    setError(null);
    setActionFeedback(null);

    try {
      const created = await reviewsApi.createSession({
        document_id: routeDocumentId,
        session_id: customSessionIdInput.trim() || undefined,
      });
      registerSession({
        session_id: created.session_id,
        document_id: routeDocumentId,
        source_filename: created.source_filename,
      });
      setSession(created);
      setHistoryEntries(created.history?.entries ?? []);
      setActiveSessionId(created.session_id);
      navigate(`/reviews/${encodeURIComponent(created.session_id)}`, { replace: true });
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ message: err.message, statusCode: err.statusCode });
      } else {
        setError({
          message: err instanceof Error ? err.message : 'Failed to create review session.',
        });
      }
    } finally {
      setCreatingSession(false);
    }
  };

  const refreshAfterMutation = async (sid: string, feedbackText: string) => {
    const [freshSession, freshHistory] = await Promise.all([
      reviewsApi.getSession(sid),
      reviewsApi.getHistory(sid, historyFilterPage ?? undefined),
    ]);
    setSession(freshSession);
    setHistoryEntries(freshHistory);
    setActionFeedback(feedbackText);
  };

  const handleRecordDecision = async (
    decision: ReviewDecisionState,
    notes: string,
    reason: string
  ) => {
    if (!session || !activeRecord) return;
    setSubmittingAction(true);
    setError(null);
    setActionFeedback(null);
    try {
      await reviewsApi.recordDecision(session.session_id, activeRecord.pdf_page_number, {
        decision,
        reviewer_id: reviewerId.trim() || 'operator_1',
        notes: notes.trim() || undefined,
        reason: reason.trim() || undefined,
      });
      await refreshAfterMutation(
        session.session_id,
        `Recorded ${decision} for Sheet ${activeRecord.pdf_page_number}.`
      );
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ message: err.message, statusCode: err.statusCode });
      } else {
        setError({
          message: err instanceof Error ? err.message : 'Failed to record review decision.',
        });
      }
    } finally {
      setSubmittingAction(false);
    }
  };

  const handleConfirmReject = async (reason: string, notes: string) => {
    await handleRecordDecision('REJECTED', notes, reason);
    setRejectModalOpen(false);
  };

  const handleUpdateNotes = async (notes: string) => {
    if (!session || !activeRecord) return;
    setSubmittingAction(true);
    setError(null);
    setActionFeedback(null);
    try {
      await reviewsApi.updateNotes(session.session_id, activeRecord.pdf_page_number, {
        reviewer_id: reviewerId.trim() || 'operator_1',
        notes,
      });
      await refreshAfterMutation(
        session.session_id,
        `Updated operator notes for Sheet ${activeRecord.pdf_page_number}.`
      );
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ message: err.message, statusCode: err.statusCode });
      } else {
        setError({
          message: err instanceof Error ? err.message : 'Failed to save operator notes.',
        });
      }
    } finally {
      setSubmittingAction(false);
    }
  };

  // 1. Landing View at /review without sessionId or documentId
  if (!routeDocumentId && !effectiveSessionId) {
    return (
      <div className="max-w-5xl ml-0 mr-auto space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white border border-slate-200/90 rounded-lg shadow-card p-5 space-y-2.5">
            <h2 className="text-sm font-semibold text-slate-900">
              Start Review from Document ID
            </h2>
            <p className="text-xs text-slate-500">
              Open or create a review session linked to an uploaded PDF document.
            </p>
            <DocumentLookupBar
              mode="review"
              placeholder="Enter Document ID (e.g., doc_861c55342a0e)"
              buttonLabel="Open Document"
            />
          </div>

          <div className="bg-white border border-slate-200/90 rounded-lg shadow-card p-5 space-y-2.5">
            <h2 className="text-sm font-semibold text-slate-900">
              Open Existing Review Session
            </h2>
            <p className="text-xs text-slate-500">
              Load a persisted SQLite review session directly by Session ID.
            </p>
            <DocumentLookupBar
              mode="session"
              placeholder="Enter Session ID"
              buttonLabel="Load Session"
            />
          </div>
        </div>

        {sessions.length > 0 || documents.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {sessions.length > 0 && (
              <div className="bg-white border border-slate-200/90 rounded-lg shadow-card p-4 space-y-2.5">
                <h3 className="text-xs font-semibold text-slate-900">Recent Review Sessions</h3>
                <div className="divide-y divide-slate-100">
                  {sessions.map((s) => (
                    <div
                      key={s.session_id}
                      className="py-2.5 flex items-center justify-between gap-2"
                    >
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-slate-900 truncate">
                          {s.source_filename}
                        </div>
                        <div className="text-[11px] font-mono text-slate-500 truncate">
                          {s.session_id}
                        </div>
                      </div>
                      <Link
                        to={`/reviews/${encodeURIComponent(s.session_id)}`}
                        className="px-2.5 py-1 text-xs font-medium rounded-md bg-bookabook-teal text-white hover:bg-bookabook-tealHover shrink-0"
                      >
                        Resume
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {documents.length > 0 && (
              <div className="bg-white border border-slate-200/90 rounded-lg shadow-card p-4 space-y-2.5">
                <h3 className="text-xs font-semibold text-slate-900">
                  Workspace Documents Ready for Review
                </h3>
                <div className="divide-y divide-slate-100">
                  {documents.map((d) => {
                    const existingSid = getSessionIdForDocument(d.document_id);
                    return (
                      <div
                        key={d.document_id}
                        className="py-2.5 flex items-center justify-between gap-2"
                      >
                        <div className="min-w-0">
                          <div className="text-xs font-semibold text-slate-900 truncate">
                            {d.filename}
                          </div>
                          <div className="text-[11px] font-mono text-slate-500 truncate">
                            {d.document_id}
                          </div>
                        </div>
                        <Link
                          to={
                            existingSid
                              ? `/reviews/${encodeURIComponent(existingSid)}`
                              : `/documents/${encodeURIComponent(d.document_id)}/review`
                          }
                          className="px-2.5 py-1 text-xs font-medium rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50 shrink-0"
                        >
                          {existingSid ? 'Open Session' : 'Create Session'}
                        </Link>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ) : (
          <EmptyState
            title="No Active Review Sessions"
            description="Upload a PDF or look up a Document ID or Session ID above to begin inspecting spreads and recording human review decisions."
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
    return <LoadingState label="Loading review session from backend..." />;
  }

  // 2. Document Context Without Session Yet -> Create Review Session Prompt
  if (!session && routeDocumentId) {
    return (
      <div className="max-w-3xl ml-0 mr-auto space-y-4">
        <Link
          to={`/documents/${encodeURIComponent(routeDocumentId)}`}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Document Detail
        </Link>

        {error && (
          <ErrorAlert
            title="Review Session Notice"
            message={error.message}
            statusCode={error.statusCode}
            onDismiss={() => setError(null)}
          />
        )}

        <div className="bg-white border border-slate-200/90 rounded-lg shadow-card p-5 space-y-4">
          <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3.5">
            <div>
              <div className="flex items-center gap-2">
                <ClipboardCheck className="w-4 h-4 text-bookabook-teal" />
                <h2 className="text-[15px] font-semibold text-slate-900">
                  Initialize Operator Review Session
                </h2>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Document:{' '}
                <span className="font-medium text-slate-800">
                  {docMeta?.filename || previewMeta?.source_filename || routeDocumentId}
                </span>{' '}
                (<code className="font-mono">{routeDocumentId}</code>)
              </p>
            </div>
            {previewMeta && <StatusBadge status={previewMeta.document_status} size="sm" />}
          </div>

          <form onSubmit={(e) => void handleCreateSession(e)} className="space-y-4">
            <div>
              <label
                htmlFor="custom-session-id"
                className="block text-[11px] font-medium text-slate-500 mb-1"
              >
                Custom Session ID (Optional)
              </label>
              <input
                id="custom-session-id"
                type="text"
                value={customSessionIdInput}
                onChange={(e) => setCustomSessionIdInput(e.target.value)}
                placeholder="Leave blank to let backend auto-generate session ID"
                className="w-full px-3 py-2 text-xs bg-bookabook-field border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal focus:bg-white"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              <button
                type="submit"
                disabled={creatingSession}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-md bg-bookabook-teal text-white hover:bg-bookabook-tealHover disabled:opacity-50 transition-colors"
              >
                {creatingSession ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <FilePlus2 className="w-3.5 h-3.5" />
                )}
                {creatingSession ? 'Creating Session...' : 'Create Review Session'}
              </button>

              <Link
                to={`/documents/${encodeURIComponent(routeDocumentId)}/preview`}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
              >
                <Eye className="w-3.5 h-3.5" />
                Inspect Preview First
              </Link>
            </div>
          </form>

          <div className="border-t border-slate-100 pt-3.5 space-y-2">
            <div className="text-xs font-medium text-slate-700">
              Already have a persisted Session ID for this PDF?
            </div>
            <DocumentLookupBar
              mode="session"
              placeholder="Paste existing Session ID"
              buttonLabel="Load Existing Session"
            />
          </div>
        </div>
      </div>
    );
  }

  // 3. Error fetching requested sessionId
  if (!session) {
    return (
      <div className="max-w-3xl ml-0 mr-auto space-y-4">
        <Link
          to="/review"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Review Lookup
        </Link>
        <ErrorAlert
          title="Unable to Load Review Session"
          message={error?.message || `Review session ${effectiveSessionId} could not be loaded.`}
          statusCode={error?.statusCode}
          onRetry={
            effectiveSessionId ? () => void fetchSessionBundle(effectiveSessionId) : undefined
          }
        />
      </div>
    );
  }

  const activeImage = activeRecord ? images[activeRecord.pdf_page_number] : undefined;
  const hasRichSpreadPreview = Boolean(
    resolvedDocumentId && activePreviewInfo && spreads.length > 0
  );

  return (
    <div className="max-w-[1520px] ml-0 mr-auto space-y-4">
      {/* Top Session Navigation Strip */}
      <div className="bg-white border border-slate-200/90 rounded-lg shadow-card px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3 min-w-0">
          <Link
            to={
              resolvedDocumentId
                ? `/documents/${encodeURIComponent(resolvedDocumentId)}`
                : '/review'
            }
            className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-900"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            {resolvedDocumentId ? 'Book' : 'Review Lookup'}
          </Link>
          <span className="text-slate-300">|</span>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-xs font-semibold text-slate-900 truncate">
                {session.source_filename}
              </h2>
              <StatusBadge status={session.document_summary.status} size="sm" />
            </div>
            <div className="text-[11px] font-mono text-slate-500 mt-0.5 truncate">
              Session: {session.session_id}
              {resolvedDocumentId && ` • Doc: ${resolvedDocumentId}`}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {resolvedDocumentId && (
            <Link
              to={`/documents/${encodeURIComponent(resolvedDocumentId)}/preview?page=${activePageNumber}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
            >
              <Eye className="w-3.5 h-3.5 text-bookabook-teal" />
              Full Preview
            </Link>
          )}
          <button
            type="button"
            onClick={() => void fetchSessionBundle(session.session_id)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <ErrorAlert
          title="Review Action Error"
          message={error.message}
          statusCode={error.statusCode}
          onDismiss={() => setError(null)}
        />
      )}

      {actionFeedback && (
        <div
          role="status"
          className="px-4 py-2 text-xs font-medium rounded-md bg-emerald-50 border border-emerald-200 text-emerald-900"
        >
          {actionFeedback}
        </div>
      )}

      {/* Document Summary Card */}
      <ReviewSummaryCard summary={session.document_summary} />

      {/* Main Review Workspace Grid */}
      {activeRecord && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
          {/* Left Column: Sheet Queue */}
          <div className="lg:col-span-3 bg-white border border-slate-200/90 rounded-lg shadow-card overflow-hidden">
            <div className="px-3.5 py-2.5 border-b border-slate-200/80 bg-bookabook-surface flex items-center justify-between">
              <span className="text-[11px] font-semibold text-slate-700 uppercase tracking-wider">
                Sheet Queue ({pageRecords.length})
              </span>
            </div>
            <div className="divide-y divide-slate-100 max-h-[600px] overflow-y-auto admin-scrollbar">
              {pageRecords.map((rec) => {
                const selected = rec.pdf_page_number === activeRecord.pdf_page_number;
                return (
                  <button
                    key={rec.pdf_page_number}
                    type="button"
                    onClick={() => selectPage(rec.pdf_page_number)}
                    className={`w-full text-left px-3.5 py-2.5 transition-colors flex flex-wrap items-start justify-between gap-2 ${
                      selected
                        ? 'bg-bookabook-teal text-white'
                        : 'hover:bg-slate-50 text-slate-800'
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-semibold">
                          Sheet {rec.pdf_page_number}
                        </span>
                        {rec.is_cover && (
                          <span
                            className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                              selected
                                ? 'bg-white/20 text-white'
                                : 'bg-bookabook-tealSoft text-bookabook-teal'
                            }`}
                          >
                            Cover
                          </span>
                        )}
                      </div>
                      <div
                        className={`text-[11px] mt-0.5 truncate ${
                          selected ? 'text-white/85' : 'text-slate-500'
                        }`}
                      >
                        {formatLayoutLabel(rec.layout_type)}
                      </div>
                    </div>
                    <div className="shrink-0">
                      <StatusBadge status={rec.review_decision} size="sm" />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Center Column: Book Spread / Sheet Preview + Audit History */}
          <div className="lg:col-span-5 space-y-4">
            {hasRichSpreadPreview ? (
              <BookSpreadViewer
                spreads={spreads}
                thumbnails={thumbnails}
                pages={previewPages}
                activeSpreadIndex={activeSpreadIndex}
                onSelectSpreadIndex={handleSelectSpreadIndex}
                viewMode={viewMode}
                onChangeViewMode={setViewMode}
                showOverlay={showOverlay}
                onToggleOverlay={setShowOverlay}
                getImageEntry={getImageEntry}
                onEnsureImage={loadImage}
                onReloadImage={reloadImage}
                onSelectSheetPage={selectPage}
                compact
              />
            ) : (
              <div className="bg-white border border-slate-200/90 rounded-lg shadow-card overflow-hidden">
                <div className="px-4 py-2.5 border-b border-slate-200/80 bg-bookabook-surface flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-slate-900">
                    Sheet {activeRecord.pdf_page_number} Preview Overlay
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      disabled={activePageNumber <= 1}
                      onClick={() => selectPage(activePageNumber - 1)}
                      aria-label="Previous sheet"
                      className="p-1 rounded border border-slate-200 bg-white text-slate-700 disabled:opacity-40 hover:bg-slate-50"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />
                    </button>
                    <span className="px-2 text-xs text-slate-600">
                      {activePageNumber} / {pageRecords.length}
                    </span>
                    <button
                      type="button"
                      disabled={activePageNumber >= pageRecords.length}
                      onClick={() => selectPage(activePageNumber + 1)}
                      aria-label="Next sheet"
                      className="p-1 rounded border border-slate-200 bg-white text-slate-700 disabled:opacity-40 hover:bg-slate-50"
                    >
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <div className="bg-bookabook-field/60 min-h-[300px] flex items-center justify-center p-4">
                  {!resolvedDocumentId ? (
                    <div className="text-center max-w-xs space-y-2 text-xs text-slate-500">
                      <ImageOff className="w-7 h-7 mx-auto text-slate-400" />
                      <p>
                        This standalone review session has no{' '}
                        <code className="font-mono">document_id</code> metadata attached, so visual
                        PNG previews cannot be resolved automatically.
                      </p>
                    </div>
                  ) : activeImage?.loading ? (
                    <LoadingState label={`Rendering Sheet ${activePageNumber} PNG...`} />
                  ) : activeImage?.error ? (
                    <div className="w-full">
                      <ErrorAlert
                        title="Preview Image Failed"
                        message={activeImage.error}
                        onRetry={() =>
                          void reloadPageImage(
                            activeRecord.pdf_page_number,
                            activePreviewInfo?.preview_image_url
                          )
                        }
                      />
                    </div>
                  ) : activeImage?.objectUrl ? (
                    <img
                      src={activeImage.objectUrl}
                      alt={`Composited crop preview for Sheet ${activeRecord.pdf_page_number}`}
                      className="max-w-full max-h-[420px] object-contain rounded shadow border border-slate-200 bg-white"
                    />
                  ) : (
                    <div className="text-xs text-slate-500 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-600" />
                      Waiting for preview PNG...
                    </div>
                  )}
                </div>
              </div>
            )}

            <ReviewHistoryTimeline
              entries={historyEntries}
              filterPageNumber={historyFilterPage}
              activePageNumber={activeRecord.pdf_page_number}
              onChangeFilterPage={setHistoryFilterPage}
              loading={historyLoading}
            />
          </div>

          {/* Right Column: Decision & Notes Panel */}
          <div className="lg:col-span-4">
            <ReviewActionPanel
              pageRecord={activeRecord}
              reviewerId={reviewerId}
              onChangeReviewerId={setReviewerId}
              submitting={submittingAction}
              onRecordDecision={handleRecordDecision}
              onUpdateNotes={handleUpdateNotes}
              onRequestRejectModal={() => setRejectModalOpen(true)}
            />
          </div>
        </div>
      )}

      {/* Confirmation Modal Before Submitting REJECTED */}
      <ConfirmRejectModal
        isOpen={rejectModalOpen}
        pageNumber={activeRecord?.pdf_page_number ?? activePageNumber}
        layoutType={activeRecord?.layout_type ?? null}
        submitting={submittingAction}
        onCancel={() => setRejectModalOpen(false)}
        onConfirm={(reason, notes) => void handleConfirmReject(reason, notes)}
      />
    </div>
  );
};
