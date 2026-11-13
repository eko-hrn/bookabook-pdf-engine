import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileSearch,
  FileText,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import { Link, useOutletContext } from 'react-router-dom';
import { documentsApi, previewsApi, reviewsApi } from '@/api';
import { DocumentLookupBar } from '@/components/DocumentLookupBar';
import { EmptyState, ErrorAlert, UnavailableEndpointBanner } from '@/components/StateNotice';
import { StatusBadge } from '@/components/StatusBadge';
import { useWorkspaceContext } from '@/hooks/useWorkspaceContext';
import {
  DocumentMetadataResponse,
  DocumentReviewSummary,
  HealthResponse,
  ReviewHistoryEntry,
} from '@/types/api';
import { formatBytes, formatTimestamp, formatUtcIsoShort } from '@/utils/formatters';

interface LayoutOutletContext {
  health: HealthResponse | null;
  healthError: string | null;
  refreshHealth: () => Promise<void>;
}

interface LiveDocEntry {
  document_id: string;
  filename: string;
  metadata?: DocumentMetadataResponse;
  previewStatus?: string;
  unavailableReason?: string;
}

interface LiveSessionEntry {
  session_id: string;
  document_id?: string;
  source_filename: string;
  summary?: DocumentReviewSummary;
  recentEvents?: ReviewHistoryEntry[];
  unavailableReason?: string;
}

export const DashboardPage: React.FC = () => {
  const { health, healthError, refreshHealth } = useOutletContext<LayoutOutletContext>();
  const {
    documents,
    sessions,
    getSessionIdForDocument,
    resetWorkspaceHistory,
  } = useWorkspaceContext();

  const [liveDocs, setLiveDocs] = useState<LiveDocEntry[]>([]);
  const [liveSessions, setLiveSessions] = useState<LiveSessionEntry[]>([]);
  const [recentActivity, setRecentActivity] = useState<
    Array<ReviewHistoryEntry & { session_id: string; source_filename: string }>
  >([]);
  const [syncingWorkspace, setSyncingWorkspace] = useState(false);

  const syncTrackedWorkspace = useCallback(async () => {
    if (documents.length === 0 && sessions.length === 0) {
      setLiveDocs([]);
      setLiveSessions([]);
      setRecentActivity([]);
      return;
    }

    setSyncingWorkspace(true);

    const docResults = await Promise.all(
      documents.slice(0, 6).map(async (doc): Promise<LiveDocEntry> => {
        try {
          const [metaRes, previewRes] = await Promise.allSettled([
            documentsApi.getDocument(doc.document_id),
            previewsApi.getDocumentPreview(doc.document_id),
          ]);
          if (metaRes.status === 'rejected') {
            return {
              document_id: doc.document_id,
              filename: doc.filename,
              unavailableReason:
                metaRes.reason instanceof Error
                  ? metaRes.reason.message
                  : 'Document could not be retrieved from backend.',
            };
          }
          return {
            document_id: doc.document_id,
            filename: metaRes.value.filename,
            metadata: metaRes.value,
            previewStatus:
              previewRes.status === 'fulfilled'
                ? previewRes.value.document_status
                : undefined,
          };
        } catch (err) {
          return {
            document_id: doc.document_id,
            filename: doc.filename,
            unavailableReason:
              err instanceof Error ? err.message : 'Unable to reach document endpoint.',
          };
        }
      })
    );

    const sessionResults = await Promise.all(
      sessions.slice(0, 6).map(async (sess): Promise<LiveSessionEntry> => {
        try {
          const [summary, history] = await Promise.all([
            reviewsApi.getSummary(sess.session_id),
            reviewsApi.getHistory(sess.session_id),
          ]);
          return {
            session_id: sess.session_id,
            document_id: sess.document_id,
            source_filename: summary.source_filename || sess.source_filename,
            summary,
            recentEvents: history,
          };
        } catch (err) {
          return {
            session_id: sess.session_id,
            document_id: sess.document_id,
            source_filename: sess.source_filename,
            unavailableReason:
              err instanceof Error ? err.message : 'Review session not found on backend.',
          };
        }
      })
    );

    const flattenedActivity = sessionResults
      .flatMap((s) =>
        (s.recentEvents ?? []).map((ev) => ({
          ...ev,
          session_id: s.session_id,
          source_filename: s.source_filename,
        }))
      )
      .sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1))
      .slice(0, 10);

    setLiveDocs(docResults);
    setLiveSessions(sessionResults);
    setRecentActivity(flattenedActivity);
    setSyncingWorkspace(false);
  }, [documents, sessions]);

  useEffect(() => {
    void syncTrackedWorkspace();
  }, [syncTrackedWorkspace]);

  return (
    <div className="max-w-6xl ml-0 mr-auto space-y-4">
      {/* Compact Header Action Strip */}
      <div className="bg-white border border-slate-200/90 rounded-lg shadow-card px-5 py-3.5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-semibold text-slate-900">
            Book Management &amp; Inspection Console
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Upload PDFs, inspect Cover &amp; 4-Up book spreads, toggle backend crop overlays, and
            record SQLite-backed approvals.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Link
            to="/upload"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium rounded-md bg-bookabook-teal text-white hover:bg-bookabook-tealHover transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            New Book
          </Link>
          <Link
            to="/review"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors"
          >
            <ClipboardCheck className="w-3.5 h-3.5" />
            Review Queue
          </Link>
        </div>
      </div>

      {/* Live Backend Connectivity Bar */}
      {healthError ? (
        <ErrorAlert
          title="Backend API Unreachable"
          message={healthError}
          onRetry={() => void refreshHealth()}
        />
      ) : (
        <div className="bg-white border border-slate-200/90 rounded-lg shadow-card px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-700">
              <Activity className="w-3.5 h-3.5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-900">
                  {health ? health.app_name : 'Checking Backend Connectivity...'}
                </span>
                {health && (
                  <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                    {health.status.toUpperCase()} v{health.version}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-500">
                {health
                  ? `SQLite Persistence: ${health.database_connected ? 'Connected' : 'Disconnected'} • Checked ${formatTimestamp(health.timestamp)}`
                  : 'Polling /api/health...'}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => {
              void refreshHealth();
              void syncTrackedWorkspace();
            }}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-600 bg-bookabook-field border border-slate-200 rounded-md hover:bg-slate-200/70 transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${syncingWorkspace ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      )}

      {/* Direct Identifier Lookups */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200/90 rounded-lg shadow-card p-4 space-y-2.5">
          <div className="flex items-center gap-2">
            <FileSearch className="w-4 h-4 text-bookabook-teal" />
            <h3 className="text-xs font-semibold text-slate-900">Open Book by Document ID</h3>
          </div>
          <p className="text-[11px] text-slate-500">
            Fetch geometry &amp; spreads via{' '}
            <code className="font-mono bg-bookabook-field px-1 py-0.5 rounded">
              /api/documents/{'{document_id}'}
            </code>
          </p>
          <DocumentLookupBar
            mode="document"
            placeholder="e.g., doc_861c55342a0e"
            buttonLabel="Load Book"
          />
        </div>

        <div className="bg-white border border-slate-200/90 rounded-lg shadow-card p-4 space-y-2.5">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="w-4 h-4 text-bookabook-teal" />
            <h3 className="text-xs font-semibold text-slate-900">
              Resume Persisted Review Session
            </h3>
          </div>
          <p className="text-[11px] text-slate-500">
            Load SQLite review session via{' '}
            <code className="font-mono bg-bookabook-field px-1 py-0.5 rounded">
              /api/reviews/sessions/{'{session_id}'}
            </code>
          </p>
          <DocumentLookupBar
            mode="session"
            placeholder="e.g., rev_20261111_..."
            buttonLabel="Open Session"
          />
        </div>
      </section>

      {/* Tracked Workspace Books & Session Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="bg-white border border-slate-200/90 rounded-lg shadow-card overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-slate-200/80 flex items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold text-slate-900">
                Recent Workspace Documents
              </h3>
              <p className="text-[11px] text-slate-500">
                Verified live via <code className="font-mono">/api/documents/{'{id}'}</code>
              </p>
            </div>
            {(documents.length > 0 || sessions.length > 0) && (
              <button
                type="button"
                onClick={resetWorkspaceHistory}
                className="inline-flex items-center gap-1 text-[11px] text-slate-500 hover:text-rose-600 transition-colors"
                title="Clear local recent IDs"
              >
                <Trash2 className="w-3 h-3" />
                Clear local
              </button>
            )}
          </div>

          <div className="p-4 flex-1">
            {documents.length === 0 ? (
              <EmptyState
                title="No documents opened in this workspace yet"
                description="Upload a PDF file or look up a Document ID above to inspect real metadata, book spreads, crop overlays, and start a review session."
                icon={<FileText className="w-5 h-5" />}
                action={
                  <Link
                    to="/upload"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-bookabook-teal text-white hover:bg-bookabook-tealHover"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    New Book
                  </Link>
                }
              />
            ) : (
              <div className="divide-y divide-slate-100">
                {liveDocs.map((entry) => {
                  const mappedSession = getSessionIdForDocument(entry.document_id);
                  return (
                    <div
                      key={entry.document_id}
                      className="py-2.5 first:pt-0 last:pb-0 flex items-start justify-between gap-3"
                    >
                      <div className="min-w-0">
                        <Link
                          to={`/documents/${encodeURIComponent(entry.document_id)}`}
                          className="text-xs font-semibold text-slate-900 hover:text-bookabook-teal hover:underline block truncate"
                        >
                          {entry.filename}
                        </Link>
                        <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                          {entry.document_id}
                        </div>
                        {entry.metadata ? (
                          <div className="flex flex-wrap items-center gap-2 mt-1 text-[11px] text-slate-600">
                            <span>{entry.metadata.page_count} sheets</span>
                            <span>•</span>
                            <span>{formatBytes(entry.metadata.file_size_bytes)}</span>
                            {entry.previewStatus && (
                              <StatusBadge status={entry.previewStatus} size="sm" />
                            )}
                          </div>
                        ) : (
                          <p className="text-[11px] text-amber-700 mt-1">
                            {entry.unavailableReason || 'Verifying...'}
                          </p>
                        )}
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <Link
                          to={`/documents/${encodeURIComponent(entry.document_id)}/preview`}
                          className="px-2.5 py-1 text-[11px] font-medium rounded border border-slate-200 text-slate-700 hover:bg-slate-50"
                        >
                          Preview
                        </Link>
                        <Link
                          to={
                            mappedSession
                              ? `/reviews/${encodeURIComponent(mappedSession)}`
                              : `/documents/${encodeURIComponent(entry.document_id)}/review`
                          }
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded bg-bookabook-teal text-white hover:bg-bookabook-tealHover"
                        >
                          Review
                          <ArrowRight className="w-3 h-3" />
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        {/* Persisted Session & Audit Activity */}
        <section className="bg-white border border-slate-200/90 rounded-lg shadow-card overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-slate-200/80">
            <h3 className="text-xs font-semibold text-slate-900">
              Recent Session &amp; Audit Activity
            </h3>
            <p className="text-[11px] text-slate-500">
              Fetched live from SQLite via{' '}
              <code className="font-mono">/api/reviews/sessions/{'{id}'}/history</code>
            </p>
          </div>

          <div className="p-4 flex-1 space-y-3">
            {sessions.length === 0 ? (
              <EmptyState
                title="No active review sessions tracked"
                description="Open a book document and create a review session to persist page decisions in SQLite."
                icon={<CheckCircle2 className="w-5 h-5" />}
              />
            ) : (
              <>
                {liveSessions.length > 0 && (
                  <div className="space-y-2">
                    {liveSessions.map((sess) => (
                      <div
                        key={sess.session_id}
                        className="p-2.5 rounded-md border border-slate-200/80 bg-bookabook-field/60 flex items-center justify-between gap-3"
                      >
                        <div className="min-w-0">
                          <Link
                            to={`/reviews/${encodeURIComponent(sess.session_id)}`}
                            className="text-xs font-semibold text-slate-900 hover:text-bookabook-teal hover:underline block truncate"
                          >
                            {sess.source_filename}
                          </Link>
                          <div className="text-[11px] font-mono text-slate-500 truncate mt-0.5">
                            {sess.session_id}
                          </div>
                          {sess.summary ? (
                            <div className="flex flex-wrap items-center gap-2 mt-1">
                              <StatusBadge status={sess.summary.status} size="sm" />
                              <span className="text-[11px] text-slate-600">
                                {sess.summary.approved_pages_count}/{sess.summary.total_pages}{' '}
                                approved
                              </span>
                            </div>
                          ) : (
                            <div className="text-[11px] text-amber-700 mt-1">
                              {sess.unavailableReason}
                            </div>
                          )}
                        </div>
                        <Link
                          to={`/reviews/${encodeURIComponent(sess.session_id)}`}
                          className="px-2.5 py-1 text-[11px] font-medium rounded border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 shrink-0"
                        >
                          Open
                        </Link>
                      </div>
                    ))}
                  </div>
                )}

                {recentActivity.length > 0 && (
                  <div className="border-t border-slate-100 pt-2.5 space-y-1.5">
                    <h4 className="text-[11px] font-semibold text-slate-700">
                      Latest Recorded Audit Events
                    </h4>
                    <div className="space-y-1.5">
                      {recentActivity.slice(0, 5).map((ev) => (
                        <div
                          key={ev.entry_id}
                          className="text-[11px] flex items-start justify-between gap-2 py-1 border-b border-slate-100 last:border-b-0"
                        >
                          <div className="min-w-0">
                            <span className="font-medium text-slate-800">{ev.event_type}</span>
                            {ev.pdf_page_number !== null && (
                              <span className="text-slate-600"> • Sheet {ev.pdf_page_number}</span>
                            )}
                            {ev.new_decision && (
                              <span className="ml-1.5">
                                <StatusBadge status={ev.new_decision} size="sm" />
                              </span>
                            )}
                            <div className="text-[10px] text-slate-500 truncate mt-0.5">
                              {ev.source_filename} • by {ev.reviewer_id}
                            </div>
                          </div>
                          <span className="text-[10px] font-mono text-slate-400 shrink-0">
                            {formatUtcIsoShort(ev.timestamp)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </section>
      </div>

      {/* Honest Backend Aggregation Scope (Compact Footer Grid) */}
      <section aria-labelledby="global-metrics-heading" className="space-y-2.5 pt-1">
        <div className="flex items-center justify-between">
          <h3 id="global-metrics-heading" className="text-xs font-semibold text-slate-700">
            Repository-Wide Statistics
          </h3>
          <span className="text-[11px] text-slate-400">Single-resource backend scope</span>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: 'Total Uploaded Documents', endpoint: 'GET /api/documents' },
            { label: 'Documents Awaiting Review', endpoint: 'GET /api/dashboard/stats' },
            { label: 'Documents Under Review', endpoint: 'GET /api/reviews/sessions' },
            {
              label: 'Completed Review Sessions',
              endpoint: 'GET /api/reviews/sessions?status=completed',
            },
          ].map((metric) => (
            <div
              key={metric.label}
              className="bg-white border border-slate-200/80 rounded-lg px-3.5 py-2.5 flex flex-col justify-between"
            >
              <div className="flex items-center justify-between gap-1.5">
                <span className="text-[11px] font-medium text-slate-500 truncate">
                  {metric.label}
                </span>
                <Database className="w-3 h-3 text-slate-400 shrink-0" />
              </div>
              <div className="mt-1.5 flex items-baseline justify-between gap-2">
                <span className="text-xs font-semibold text-slate-400">Unavailable</span>
                <span className="text-[10px] font-mono text-slate-400 truncate">
                  {metric.endpoint}
                </span>
              </div>
            </div>
          ))}
        </div>

        <UnavailableEndpointBanner
          title="Global listing and aggregate metric endpoints unavailable"
          reason="The current FastAPI backend exposes single-resource endpoints (/api/documents/{document_id} and /api/reviews/sessions/{session_id}) without repository-wide list or dashboard count routes. Rather than fabricating statistics, counts remain marked Unavailable while workspace records above reflect live backend responses."
        />
      </section>
    </div>
  );
};
