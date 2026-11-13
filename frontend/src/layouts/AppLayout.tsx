import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { SidebarNav } from '@/components/SidebarNav';
import { TopBar } from '@/components/TopBar';
import { useHealthCheck } from '@/hooks/useHealthCheck';

function getPageTitle(pathname: string): string {
  if (pathname === '/') return 'Dashboard';
  if (pathname.startsWith('/upload')) return 'Books / New Book';
  if (pathname.includes('/preview')) return 'Books / Preview';
  if (pathname.includes('/review')) return 'Books / Review';
  if (pathname.startsWith('/documents')) return 'Books';
  return 'Books';
}

export const AppLayout: React.FC = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { health, error, loading, refresh } = useHealthCheck(30_000);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-bookabook-surface">
      <SidebarNav
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <TopBar
          title={getPageTitle(location.pathname)}
          health={health}
          healthError={error}
          healthLoading={loading}
          onRefreshHealth={() => void refresh()}
          onOpenMobileMenu={() => setMobileOpen(true)}
        />

        <main className="flex-1 overflow-y-auto overflow-x-hidden p-4 lg:p-6 admin-scrollbar">
          <Outlet context={{ health, healthError: error, refreshHealth: refresh }} />
        </main>
      </div>
    </div>
  );
};
