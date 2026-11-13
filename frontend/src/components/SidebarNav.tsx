import React from 'react';
import {
  BookOpen,
  FilePlus2,
  LayoutGrid,
  Library,
  X,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';

interface SidebarNavProps {
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

export const SidebarNav: React.FC<SidebarNavProps> = ({
  mobileOpen,
  onCloseMobile,
}) => {
  const navItems = [
    {
      label: 'Dashboard',
      to: '/',
      icon: LayoutGrid,
      end: true,
    },
    {
      label: 'Create Book',
      to: '/books/new',
      icon: FilePlus2,
      end: false,
    },
    {
      label: 'Books',
      to: '/books',
      icon: Library,
      end: true,
    },
  ];

  const navContent = (
    <div className="flex flex-col h-full bg-white border-r border-slate-200/90 text-slate-700 w-48 select-none">
      {/* Compact Brand Header */}
      <div className="h-12 flex items-center justify-between px-4 border-b border-slate-200/80 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-bookabook-teal flex items-center justify-center shrink-0">
            <BookOpen className="w-3.5 h-3.5 text-white" strokeWidth={2.2} />
          </div>
          <span className="text-[15px] font-semibold tracking-tight text-slate-900">
            Bookabook
          </span>
        </div>
        <button
          type="button"
          onClick={onCloseMobile}
          className="lg:hidden p-1 text-slate-400 hover:text-slate-700 rounded"
          aria-label="Close navigation menu"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Menu Section */}
      <div className="flex-1 overflow-y-auto px-2.5 pt-4 pb-3 space-y-5">
        <div>
          <div className="px-2.5 mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Menu
          </div>
          <nav className="space-y-1" aria-label="Primary Sidebar Navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.label}
                  to={item.to}
                  end={item.end}
                  onClick={onCloseMobile}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-2.5 py-2 rounded-md text-[13px] font-medium transition-colors ${
                      isActive
                        ? 'bg-bookabook-teal text-white shadow-xs'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon
                        className={`w-4 h-4 shrink-0 ${
                          isActive ? 'text-white' : 'text-slate-400'
                        }`}
                        strokeWidth={1.85}
                      />
                      <span className="truncate">{item.label}</span>
                    </>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Subtle Admin Footer */}
      <div className="px-4 py-3 border-t border-slate-200/80 text-[11px] text-slate-400 shrink-0">
        Bookabook Admin • PDF Engine
      </div>
    </div>
  );

  return (
    <>
      <aside className="hidden lg:block shrink-0">{navContent}</aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-slate-900/35"
            onClick={onCloseMobile}
            aria-hidden="true"
          />
          <aside className="relative z-10 h-full">{navContent}</aside>
        </div>
      )}
    </>
  );
};
