import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  HelpCircle,
  RotateCcw,
  ShieldAlert,
  XCircle,
} from 'lucide-react';

interface BadgeStyle {
  label: string;
  classes: string;
  Icon: React.ComponentType<{ className?: string }>;
}

const BADGE_CONFIG: Record<string, BadgeStyle> = {
  // Crop Readiness & Document Preview Statuses
  CROP_READY: {
    label: 'Crop Ready',
    classes: 'bg-emerald-50 text-emerald-800 border-emerald-300',
    Icon: CheckCircle2,
  },
  AUTO_READY_FOR_PREVIEW: {
    label: 'Auto Ready for Preview',
    classes: 'bg-emerald-50 text-emerald-800 border-emerald-300',
    Icon: CheckCircle2,
  },
  MANUAL_REVIEW_REQUIRED: {
    label: 'Manual Review Required',
    classes: 'bg-amber-50 text-amber-900 border-amber-300 border-dashed',
    Icon: AlertTriangle,
  },
  NOT_APPLICABLE: {
    label: 'Not Applicable',
    classes: 'bg-rose-50 text-rose-800 border-rose-300 border-dotted',
    Icon: ShieldAlert,
  },
  UNKNOWN_LAYOUT: {
    label: 'Unknown Layout (Blocked)',
    classes: 'bg-rose-50 text-rose-800 border-rose-300',
    Icon: ShieldAlert,
  },
  REJECTED_UNKNOWN_LAYOUT: {
    label: 'Rejected: Unknown Layout',
    classes: 'bg-rose-50 text-rose-800 border-rose-300',
    Icon: XCircle,
  },

  // Review Decision States
  PENDING: {
    label: 'Pending Review',
    classes: 'bg-slate-100 text-slate-700 border-slate-300',
    Icon: Clock,
  },
  APPROVED: {
    label: 'Approved',
    classes: 'bg-emerald-50 text-emerald-800 border-emerald-300',
    Icon: CheckCircle2,
  },
  REJECTED: {
    label: 'Rejected',
    classes: 'bg-rose-50 text-rose-800 border-rose-300',
    Icon: XCircle,
  },
  NEEDS_REVISION: {
    label: 'Needs Revision',
    classes: 'bg-amber-50 text-amber-900 border-amber-300',
    Icon: RotateCcw,
  },

  // Document-Level Review Statuses
  PENDING_REVIEW: {
    label: 'Pending Review',
    classes: 'bg-slate-100 text-slate-700 border-slate-300',
    Icon: Clock,
  },
  PARTIALLY_REVIEWED: {
    label: 'Under Review',
    classes: 'bg-sky-50 text-sky-800 border-sky-300',
    Icon: Clock,
  },
  REVIEW_COMPLETED: {
    label: 'Review Completed',
    classes: 'bg-emerald-50 text-emerald-800 border-emerald-300',
    Icon: CheckCircle2,
  },
  REVIEW_REJECTED: {
    label: 'Review Rejected',
    classes: 'bg-rose-50 text-rose-800 border-rose-300',
    Icon: XCircle,
  },
  REVIEW_BLOCKED: {
    label: 'Review Blocked',
    classes: 'bg-rose-50 text-rose-800 border-rose-300',
    Icon: ShieldAlert,
  },

  // Layout Types
  COVER_SPREAD: {
    label: 'Cover Spread',
    classes: 'bg-indigo-50 text-indigo-800 border-indigo-200',
    Icon: FileText,
  },
  IMPOSITION_4UP: {
    label: '4-Up Imposition',
    classes: 'bg-slate-100 text-slate-800 border-slate-300',
    Icon: FileText,
  },
  SINGLE_PAGE: {
    label: 'Single Page',
    classes: 'bg-cyan-50 text-cyan-800 border-cyan-200',
    Icon: FileText,
  },

  // Document Upload Status
  uploaded: {
    label: 'Uploaded',
    classes: 'bg-sky-50 text-sky-800 border-sky-200',
    Icon: CheckCircle2,
  },
};

interface StatusBadgeProps {
  status: string | null | undefined;
  customLabel?: string;
  size?: 'sm' | 'md';
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  customLabel,
  size = 'sm',
  className = '',
}) => {
  const key = status || 'UNKNOWN_LAYOUT';
  const cfg = BADGE_CONFIG[key] || {
    label: status || 'Unknown',
    classes: 'bg-slate-100 text-slate-700 border-slate-300',
    Icon: HelpCircle,
  };
  const { Icon } = cfg;

  const sizeClasses =
    size === 'md'
      ? 'px-2.5 py-1 text-xs gap-1.5'
      : 'px-2 py-0.5 text-[11px] gap-1';

  return (
    <span
      className={`inline-flex items-center font-medium rounded border whitespace-nowrap ${sizeClasses} ${cfg.classes} ${className}`}
      title={customLabel || cfg.label}
    >
      <Icon className={size === 'md' ? 'w-3.5 h-3.5 shrink-0' : 'w-3 h-3 shrink-0'} />
      <span>{customLabel || cfg.label}</span>
    </span>
  );
};

