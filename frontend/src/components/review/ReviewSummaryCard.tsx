import React from 'react';
import { ShieldCheck } from 'lucide-react';
import { StatusBadge } from '@/components/StatusBadge';
import { DocumentReviewSummary } from '@/types/api';
import { formatTimestamp } from '@/utils/formatters';

interface ReviewSummaryCardProps {
  summary: DocumentReviewSummary;
}

export const ReviewSummaryCard: React.FC<ReviewSummaryCardProps> = ({ summary }) => {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-100">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">
            Document Review Summary
          </h3>
          <p className="text-xs text-slate-500 font-mono mt-0.5">
            Session: {summary.session_id}
          </p>
        </div>
        <StatusBadge status={summary.status} size="md" />
      </div>

      {/* Breakdown Counters */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
        <div className="bg-slate-50 border border-slate-200 rounded-md p-2.5">
          <div className="text-[11px] text-slate-500">Total Sheets</div>
          <div className="text-lg font-semibold text-slate-900">{summary.total_pages}</div>
        </div>
        <div className="bg-emerald-50/60 border border-emerald-200 rounded-md p-2.5">
          <div className="text-[11px] text-emerald-700">Approved</div>
          <div className="text-lg font-semibold text-emerald-900">
            {summary.approved_pages_count}
          </div>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-md p-2.5">
          <div className="text-[11px] text-slate-600">Pending</div>
          <div className="text-lg font-semibold text-slate-900">
            {summary.pending_pages_count}
          </div>
        </div>
        <div className="bg-amber-50/60 border border-amber-200 rounded-md p-2.5">
          <div className="text-[11px] text-amber-800">Needs Revision</div>
          <div className="text-lg font-semibold text-amber-900">
            {summary.needs_revision_pages_count}
          </div>
        </div>
        <div className="bg-rose-50/60 border border-rose-200 rounded-md p-2.5">
          <div className="text-[11px] text-rose-700">Rejected</div>
          <div className="text-lg font-semibold text-rose-900">
            {summary.rejected_pages_count}
          </div>
        </div>
      </div>

      {summary.summary_message && (
        <p className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded p-2.5">
          {summary.summary_message}
        </p>
      )}

      {/* Strict Production Separation Guardrail Notice */}
      <div className="flex items-start gap-2.5 p-3 bg-slate-50 border border-slate-300 rounded-md text-xs text-slate-700">
        <ShieldCheck className="w-4 h-4 text-slate-700 shrink-0 mt-0.5" />
        <div>
          <strong>Production Authorization Guardrail:</strong>{' '}
          {summary.requires_production_authorization
            ? 'Completing this review workflow records operator approval only and does NOT trigger or authorize production 300 DPI JPG cropping/export.'
            : 'Review sign-off recorded.'}
        </div>
      </div>

      {summary.reviewed_at && (
        <div className="text-[11px] text-slate-500">
          Review completion timestamp: {formatTimestamp(summary.reviewed_at)}
        </div>
      )}
    </div>
  );
};

