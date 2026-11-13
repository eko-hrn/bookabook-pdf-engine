import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  MessageSquarePlus,
  RotateCcw,
  ShieldAlert,
  UserCheck,
  XCircle,
} from 'lucide-react';
import { StatusBadge } from '@/components/StatusBadge';
import { PageReviewRecord, ReviewDecisionState } from '@/types/api';
import { formatLayoutLabel, formatTimestamp } from '@/utils/formatters';

interface ReviewActionPanelProps {
  pageRecord: PageReviewRecord;
  reviewerId: string;
  onChangeReviewerId: (id: string) => void;
  submitting: boolean;
  onRecordDecision: (
    decision: ReviewDecisionState,
    notes: string,
    reason: string
  ) => Promise<void>;
  onUpdateNotes: (notes: string) => Promise<void>;
  onRequestRejectModal: () => void;
}

export const ReviewActionPanel: React.FC<ReviewActionPanelProps> = ({
  pageRecord,
  reviewerId,
  onChangeReviewerId,
  submitting,
  onRecordDecision,
  onUpdateNotes,
  onRequestRejectModal,
}) => {
  const [decisionNotes, setDecisionNotes] = useState('');
  const [standaloneNotes, setStandaloneNotes] = useState(pageRecord.notes || '');

  useEffect(() => {
    setStandaloneNotes(pageRecord.notes || '');
    setDecisionNotes('');
  }, [pageRecord.pdf_page_number, pageRecord.notes]);

  const isUnknownLayout =
    pageRecord.classification_status === 'UNKNOWN_LAYOUT' ||
    pageRecord.layout_type === null;
  const isRejected = pageRecord.review_decision === 'REJECTED';
  const isApproveBlocked = isUnknownLayout || isRejected;
  const trimmedReviewer = reviewerId.trim();

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-100">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">
            Sheet {pageRecord.pdf_page_number} — Operator Evaluation
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Layout: {formatLayoutLabel(pageRecord.layout_type)} • Readiness:{' '}
            <span className="font-mono">{pageRecord.crop_readiness}</span>
          </p>
        </div>
        <StatusBadge status={pageRecord.review_decision} size="md" />
      </div>

      {/* Reviewer Identity */}
      <div>
        <label
          htmlFor="operator-reviewer-id"
          className="flex items-center gap-1.5 text-xs font-medium text-slate-700 mb-1"
        >
          <UserCheck className="w-3.5 h-3.5 text-slate-500" />
          <span>Operator / Reviewer ID</span>
        </label>
        <input
          id="operator-reviewer-id"
          type="text"
          value={reviewerId}
          onChange={(e) => onChangeReviewerId(e.target.value)}
          placeholder="operator_1"
          className="w-full px-3 py-1.5 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-slate-900"
          disabled={submitting}
        />
        {!trimmedReviewer && (
          <p className="text-xs text-rose-600 mt-1">
            Reviewer ID is required to submit decisions or notes.
          </p>
        )}
      </div>

      {/* Safety Guardrails Callouts */}
      {isUnknownLayout && (
        <div
          role="alert"
          className="flex items-start gap-2.5 p-3 bg-rose-50 border border-rose-200 rounded-md text-xs text-rose-900"
        >
          <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <div>
            <strong>Approval Blocked (UNKNOWN_LAYOUT):</strong> Pages with unclassified layout
            cannot be approved. Request revision or reject the sheet.
          </div>
        </div>
      )}

      {isRejected && (
        <div className="flex items-start gap-2.5 p-3 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-900">
          <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
          <div>
            <strong>Direct Approval Blocked:</strong> This sheet is currently{' '}
            <span className="font-semibold">REJECTED</span>. Transition it to{' '}
            <span className="font-semibold">NEEDS_REVISION</span> before it can be approved.
          </div>
        </div>
      )}

      {pageRecord.is_cover && (
        <div className="flex items-start gap-2.5 p-3 bg-indigo-50 border border-indigo-200 rounded-md text-xs text-indigo-900">
          <AlertTriangle className="w-4 h-4 text-indigo-700 shrink-0 mt-0.5" />
          <div>
            <strong>Cover Spread Manual Review Policy:</strong> Automatic cropping is strictly
            disabled for Cover Spreads. Operator inspection of spine exclusion and outer cover
            bounds is required.
          </div>
        </div>
      )}

      {pageRecord.is_non_nominal && (
        <div className="flex items-start gap-2.5 p-3 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-900">
          <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
          <div>
            <strong>Non-Nominal Single Page Dimensions:</strong> Held under specification
            normalization policy pending explicit manual review.
          </div>
        </div>
      )}

      {/* Decision Notes Input */}
      <div>
        <label
          htmlFor="decision-notes-input"
          className="block text-xs font-medium text-slate-700 mb-1"
        >
          Decision Remark / Reason (optional for Approve / Revision)
        </label>
        <input
          id="decision-notes-input"
          type="text"
          value={decisionNotes}
          onChange={(e) => setDecisionNotes(e.target.value)}
          placeholder="Optional note or revision guidance..."
          className="w-full px-3 py-1.5 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-slate-900"
          disabled={submitting}
        />
      </div>

      {/* Decision Action Buttons */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <button
          type="button"
          onClick={() =>
            void onRecordDecision(
              'APPROVED',
              decisionNotes.trim(),
              decisionNotes.trim() || 'OPERATOR_APPROVED'
            )
          }
          disabled={submitting || isApproveBlocked || !trimmedReviewer}
          title={
            isUnknownLayout
              ? 'UNKNOWN_LAYOUT cannot be approved'
              : isRejected
                ? 'REJECTED pages must be set to NEEDS_REVISION before approving'
                : 'Approve this sheet'
          }
          className="inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-md bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>{submitting ? 'Saving...' : 'Approve'}</span>
        </button>

        <button
          type="button"
          onClick={() =>
            void onRecordDecision(
              'NEEDS_REVISION',
              decisionNotes.trim(),
              decisionNotes.trim() || 'REVISION_REQUESTED'
            )
          }
          disabled={submitting || !trimmedReviewer}
          className="inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-md bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Request Revision</span>
        </button>

        <button
          type="button"
          onClick={onRequestRejectModal}
          disabled={submitting || !trimmedReviewer}
          className="inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-md bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <XCircle className="w-3.5 h-3.5" />
          <span>Reject</span>
        </button>
      </div>

      {/* Standalone Notes Editor (PATCH /notes) */}
      <div className="pt-3 border-t border-slate-200 space-y-2">
        <label
          htmlFor="page-notes-textarea"
          className="flex items-center gap-1.5 text-xs font-semibold text-slate-800"
        >
          <MessageSquarePlus className="w-3.5 h-3.5 text-slate-500" />
          <span>Sheet Notes (does not change decision state)</span>
        </label>
        <textarea
          id="page-notes-textarea"
          rows={3}
          value={standaloneNotes}
          onChange={(e) => setStandaloneNotes(e.target.value)}
          placeholder="Add persistent inspection notes for this sheet..."
          className="w-full px-3 py-2 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-slate-900"
          disabled={submitting}
        />
        <div className="flex items-center justify-between gap-2">
          <div className="text-[11px] text-slate-500">
            {pageRecord.reviewer_id
              ? `Last reviewed by ${pageRecord.reviewer_id} (${formatTimestamp(pageRecord.reviewed_at)})`
              : 'Not yet evaluated'}
          </div>
          <button
            type="button"
            onClick={() => void onUpdateNotes(standaloneNotes.trim())}
            disabled={submitting || !standaloneNotes.trim() || !trimmedReviewer}
            className="px-3 py-1.5 text-xs font-medium bg-slate-900 text-white rounded-md hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Save Notes
          </button>
        </div>
      </div>

      {/* Page Warnings & Unresolved Discrepancies */}
      {(pageRecord.warnings.length > 0 || pageRecord.unresolved_discrepancies.length > 0) && (
        <div className="pt-3 border-t border-slate-200 space-y-2">
          <div className="text-xs font-semibold text-slate-800">Sheet Flags &amp; Warnings</div>
          {pageRecord.warnings.length > 0 && (
            <ul className="list-disc pl-4 text-xs text-slate-700 space-y-1">
              {pageRecord.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
          {pageRecord.unresolved_discrepancies.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {pageRecord.unresolved_discrepancies.map((d, i) => (
                <span
                  key={i}
                  className="text-[11px] font-mono bg-amber-50 border border-amber-200 text-amber-900 px-2 py-0.5 rounded"
                >
                  {d}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

