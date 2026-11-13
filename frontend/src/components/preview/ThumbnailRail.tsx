import React from 'react';
import { AlertTriangle, CheckCircle2, ImageOff, Loader2, ShieldAlert } from 'lucide-react';
import { PreviewImageEntry } from '@/hooks/usePreviewImages';
import { PagePreviewInfo } from '@/types/api';
import { formatLayoutLabel } from '@/utils/formatters';

interface ThumbnailRailProps {
  pages: PagePreviewInfo[];
  currentPageNumber: number;
  images: Record<number, PreviewImageEntry>;
  onSelectPage: (pageNumber: number) => void;
}

export const ThumbnailRail: React.FC<ThumbnailRailProps> = ({
  pages,
  currentPageNumber,
  images,
  onSelectPage,
}) => {
  return (
    <div className="bg-white border border-slate-200 rounded-lg flex flex-col overflow-hidden lg:w-52 shrink-0">
      <div className="px-3 py-2.5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-800 uppercase tracking-wide">
          Sheets ({pages.length})
        </span>
      </div>

      <div className="flex lg:flex-col gap-2 p-2.5 overflow-x-auto lg:overflow-x-hidden lg:overflow-y-auto lg:max-h-[calc(100vh-14rem)]">
        {pages.map((page) => {
          const isSelected = page.page_number === currentPageNumber;
          const imgState = images[page.page_number];

          return (
            <button
              key={page.page_number}
              type="button"
              onClick={() => onSelectPage(page.page_number)}
              className={`group flex flex-col text-left rounded-md border p-2 transition-colors shrink-0 w-36 lg:w-full ${
                isSelected
                  ? 'border-slate-900 bg-slate-900 text-white ring-1 ring-slate-900'
                  : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 text-slate-800'
              }`}
            >
              <div className="flex items-center justify-between gap-1.5 mb-1.5">
                <span className="text-xs font-semibold">Sheet {page.page_number}</span>
                {page.crop_readiness === 'CROP_READY' ? (
                  <CheckCircle2
                    className={`w-3.5 h-3.5 shrink-0 ${
                      isSelected ? 'text-emerald-400' : 'text-emerald-600'
                    }`}
                  />
                ) : page.crop_readiness === 'MANUAL_REVIEW_REQUIRED' ? (
                  <AlertTriangle
                    className={`w-3.5 h-3.5 shrink-0 ${
                      isSelected ? 'text-amber-300' : 'text-amber-600'
                    }`}
                  />
                ) : (
                  <ShieldAlert
                    className={`w-3.5 h-3.5 shrink-0 ${
                      isSelected ? 'text-rose-300' : 'text-rose-600'
                    }`}
                  />
                )}
              </div>

              <div
                className={`w-full h-24 rounded border overflow-hidden flex items-center justify-center mb-1.5 ${
                  isSelected
                    ? 'bg-slate-800 border-slate-700'
                    : 'bg-slate-100 border-slate-200'
                }`}
              >
                {imgState?.objectUrl ? (
                  <img
                    src={imgState.objectUrl}
                    alt={`Sheet ${page.page_number} thumbnail`}
                    className="max-w-full max-h-full object-contain"
                  />
                ) : imgState?.error ? (
                  <ImageOff className="w-4 h-4 text-rose-400" />
                ) : (
                  <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
                )}
              </div>

              <div className="flex items-center justify-between gap-1 text-[11px]">
                <span
                  className={`truncate ${
                    isSelected ? 'text-slate-200' : 'text-slate-600'
                  }`}
                >
                  {formatLayoutLabel(page.layout_type)}
                </span>
                <span
                  className={`font-mono shrink-0 ${
                    isSelected ? 'text-slate-300' : 'text-slate-400'
                  }`}
                >
                  {page.expected_page_yield}p
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

