import React from 'react';
import { Menu, RefreshCw, ShieldCheck } from 'lucide-react';
import { HealthResponse } from '@/types/api';

interface TopBarProps {
  title: string;
  health: HealthResponse | null;
  healthError: string | null;
  healthLoading: boolean;
  onRefreshHealth: () => void;
  onOpenMobileMenu: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  title,
  health,
  healthError,
  healthLoading,
  onRefreshHealth,
  onOpenMobileMenu,
}) => {
  const isHealthy = Boolean(health && health.status === 'ok' && health.database_connected);

  return (
    <header className="h-12 bg-white border-b border-slate-200/90 px-4 lg:px-6 flex items-center justify-between gap-4 shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <button
          type="button"
          onClick={onOpenMobileMenu}
          className="lg:hidden p-1.5 -ml-1.5 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          aria-label="Open navigation menu"
        >
          <Menu className="w-4 h-4" />
        </button>
        <h1 className="text-[14px] font-semibold text-slate-900 truncate">{title}</h1>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <div
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-medium ${
            healthError
              ? 'bg-rose-50 text-rose-700 border-rose-200'
              : isHealthy
                ? 'bg-slate-50 text-slate-700 border-slate-200'
                : 'bg-amber-50 text-amber-800 border-amber-200'
          }`}
          title={healthError || `${health?.app_name ?? 'Bookabook API'} • SQLite persistence`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              healthError
                ? 'bg-rose-500'
                : isHealthy
                  ? 'bg-emerald-500'
                  : 'bg-amber-500 animate-pulse'
            }`}
          />
          <span className="hidden sm:inline">
            {healthError
              ? 'API Disconnected'
              : isHealthy
                ? 'API Online • SQLite'
                : 'Connecting...'}
          </span>
        </div>

        <button
          type="button"
          onClick={onRefreshHealth}
          disabled={healthLoading}
          className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 disabled:opacity-50 transition-colors"
          aria-label="Refresh backend health"
          title="Refresh backend health"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${healthLoading ? 'animate-spin' : ''}`} />
        </button>

        <div className="hidden md:inline-flex items-center gap-1.5 pl-2 ml-1 border-l border-slate-200 text-xs text-slate-600">
          <div className="w-6 h-6 rounded-full bg-bookabook-tealSoft text-bookabook-teal flex items-center justify-center">
            <ShieldCheck className="w-3.5 h-3.5" />
          </div>
          <span className="font-medium text-slate-700">Operator</span>
        </div>
      </div>
    </header>
  );
};
