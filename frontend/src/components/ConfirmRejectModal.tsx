import React, { useEffect, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface ConfirmRejectModalProps {
  isOpen: boolean;
  pageNumber: number;
  layoutType: string | null;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: (reason: string, notes: string) => void;
}

export const ConfirmRejectModal: React.FC<ConfirmRejectModalProps> = ({
  isOpen,
  pageNumber,
  layoutType,
  submitting,
  onCancel,
  onConfirm,
}) => {
  const [reason, setReason] = useState('');
  const [notes, setNotes] = useState('');

  useEffect(() => {
    if (isOpen) {
      setReason('');
      setNotes('');
    }
  }, [isOpen, pageNumber]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConfirm(reason.trim(), notes.trim());
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="reject-modal-title"
    >
      <div className="bg-white border border-slate-200 rounded-xl shadow-xl w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 bg-rose-50/70">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-5 h-5 text-rose-600" />
            <h3 id="reject-modal-title" className="text-sm font-semibold text-slate-900">
              Confirm Page Rejection — Sheet {pageNumber}
            </h3>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="text-slate-400 hover:text-slate-600 p-1 rounded"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-md p-3 leading-relaxed">
            Rejecting <strong>Sheet {pageNumber}</strong>{' '}
            {layoutType ? `(${layoutType})` : '(Unknown Layout)'} marks the document review as{' '}
            <strong>REVIEW_REJECTED</strong> and blocks direct transition to{' '}
            <strong>APPROVED</strong> until transitioned to <strong>NEEDS_REVISION</strong> first.
          </div>

          <div>
            <label
              htmlFor="reject-reason"
              className="block text-xs font-medium text-slate-700 mb-1"
            >
              Rejection Reason (recorded in audit history)
            </label>
            <input
              id="reject-reason"
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g., Crop marks misaligned with bleed margin"
              className="w-full px-3 py-2 text-xs bg-bookabook-field border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-rose-500/30 focus:border-rose-500 focus:bg-white"
              disabled={submitting}
            />
          </div>

          <div>
            <label
              htmlFor="reject-notes"
              className="block text-xs font-medium text-slate-700 mb-1"
            >
              Additional Operator Notes (optional)
            </label>
            <textarea
              id="reject-notes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional detailed instructions for pre-press team..."
              className="w-full px-3 py-2 text-xs bg-bookabook-field border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-rose-500/30 focus:border-rose-500 focus:bg-white"
              disabled={submitting}
            />
          </div>

          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onCancel}
              disabled={submitting}
              className="px-3.5 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-xs font-semibold text-white bg-rose-600 rounded-md hover:bg-rose-700 disabled:opacity-50"
            >
              {submitting ? 'Submitting...' : 'Confirm Reject Page'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

