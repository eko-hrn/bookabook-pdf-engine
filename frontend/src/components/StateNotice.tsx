import React from 'react';
import { AlertCircle, Database, Inbox, Loader2 } from 'lucide-react';

export const LoadingState: React.FC<{ label?: string; className?: string }> = ({
  label = 'Loading data from backend...',
  className = '',
}) => (
  <div
    className={`flex flex-col items-center justify-center py-12 px-4 text-center ${className}`}
    role="status"
    aria-live="polite"
  >
    <Loader2 className="w-7 h-7 text-slate-600 animate-spin mb-3" />
    <p className="text-sm font-medium text-slate-700">{label}</p>
  </div>
);

export const EmptyState: React.FC<{
  title: string;
  description: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}> = ({ title, description, action, icon }) => (
  <div className="flex flex-col items-center justify-center py-10 px-6 text-center bg-white border border-slate-200 rounded-lg">
    <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center mb-3">
      {icon || <Inbox className="w-5 h-5" />}
    </div>
    <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
    <p className="text-sm text-slate-500 max-w-md mt-1">{description}</p>
    {action && <div className="mt-4">{action}</div>}
  </div>
);

export const ErrorAlert: React.FC<{
  title?: string;
  message: string;
  statusCode?: number;
  onRetry?: () => void;
  onDismiss?: () => void;
  className?: string;
}> = ({
  title = 'Request Error',
  message,
  statusCode,
  onRetry,
  onDismiss,
  className = '',
}) => (
  <div
    role="alert"
    className={`bg-rose-50 border border-rose-200 rounded-lg p-4 text-rose-900 ${className}`}
  >
    <div className="flex items-start gap-3">
      <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h4 className="text-sm font-semibold text-rose-900">{title}</h4>
          {statusCode !== undefined && (
            <span className="px-1.5 py-0.5 text-[11px] font-mono bg-rose-100 text-rose-800 rounded border border-rose-200">
              HTTP {statusCode}
            </span>
          )}
        </div>
        <p className="text-sm text-rose-800 mt-1 break-words">{message}</p>
        {(onRetry || onDismiss) && (
          <div className="flex items-center gap-3 mt-3">
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="px-3 py-1.5 text-xs font-medium bg-white border border-rose-300 text-rose-800 rounded hover:bg-rose-100 transition-colors"
              >
                Retry Request
              </button>
            )}
            {onDismiss && (
              <button
                type="button"
                onClick={onDismiss}
                className="text-xs font-medium text-rose-700 hover:underline"
              >
                Dismiss
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  </div>
);

export const UnavailableEndpointBanner: React.FC<{
  title: string;
  reason: string;
}> = ({ title, reason }) => (
  <div className="flex items-start gap-3 p-4 bg-slate-50 border border-slate-200 border-dashed rounded-lg">
    <Database className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
    <div className="text-xs text-slate-600 leading-relaxed">
      <span className="font-semibold text-slate-800">{title}: </span>
      {reason}
    </div>
  </div>
);

