import React from 'react';
import { Clock, FilePlus2, History, MessageSquare } from 'lucide-react';
import { StatusBadge } from '@/components/StatusBadge';
import { ReviewHistoryEntry } from '@/types/api';
import { formatUtcIsoShort } from '@/utils/formatters';

interface ReviewHistoryTimelineProps {
  entries: ReviewHistoryEntry[];
  filterPageNumber: number | null;
  activePageNumber: number;
  onChangeFilterPage: (pageNumber: number | null) => void;
  loading?: boolean;
}

export const ReviewHistoryTimeline: React.FC<ReviewHistoryTimelineProps> = ({
  entries,
  filterPageNumber,
  activePageNumber,
  onChangeFilterPage,
  loading = false,
}) => {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-slate-500" />
          <h3 className="text-sm font-semibold text-slate-900">
            Audit History ({entries.length})
          </h3>
        </div>

        <div className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5 text-xs">
          <button
            type="button"
            onClick={() => onChangeFilterPage(null)}
            className={`px-2.5 py-1 rounded font-medium transition-colors ${
              filterPageNumber === null
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            All Events
          </button>
          <button
            type="button"
            onClick={() => onChangeFilterPage(activePageNumber)}
            className={`px-2.5 py-1 rounded font-medium transition-colors ${
              filterPageNumber === activePageNumber
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Sheet {activePageNumber} Only
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-6 text-center text-xs text-slate-500">Loading audit history...</div>
      ) : entries.length === 0 ? (
        <div className="py-6 text-center text-xs text-slate-500">
          No audit events recorded for this filter.
        </div>
      ) : (
        <ol className="space-y-2.5 max-h-80 overflow-y-auto pr-1">
          {entries.map((entry) => {
            const Icon =
              entry.event_type === 'SESSION_CREATED'
                ? FilePlus2
                : entry.event_type === 'NOTES_UPDATED'
                  ? MessageSquare
                  : Clock;

            return (
              <li
                key={entry.entry_id}
                className="flex items-start gap-3 p-2.5 rounded-md border border-slate-100 bg-slate-50/60 text-xs"
              >
                <div className="w-6 h-6 rounded-full bg-white border border-slate-200 flex items-center justify-center shrink-0 mt-0.5 text-slate-600">
                  <Icon className="w-3.5 h-3.5" />
                </div>

                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="font-semibold text-slate-900">{entry.event_type}</span>
                      {entry.pdf_page_number !== null && (
                        <span className="px-1.5 py-0.5 bg-slate-200/70 text-slate-800 rounded text-[11px] font-medium">
                          Sheet {entry.pdf_page_number}
                        </span>
                      )}
                      <span className="text-slate-500">by {entry.reviewer_id}</span>
                    </div>
                    <span className="font-mono text-[11px] text-slate-500">
                      {formatUtcIsoShort(entry.timestamp)}
                    </span>
                  </div>

                  {entry.event_type === 'DECISION_RECORDED' &&
                    (entry.previous_decision || entry.new_decision) && (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {entry.previous_decision && (
                          <StatusBadge status={entry.previous_decision} />
                        )}
                        <span className="text-slate-400">→</span>
                        {entry.new_decision && <StatusBadge status={entry.new_decision} />}
                      </div>
                    )}

                  {entry.reason && (
                    <div className="text-slate-600">
                      <span className="font-medium">Reason:</span> {entry.reason}
                    </div>
                  )}
                  {entry.notes && (
                    <div className="text-slate-700 bg-white border border-slate-200 rounded px-2 py-1">
                      {entry.notes}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
};

