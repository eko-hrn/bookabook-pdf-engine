import React, { useEffect, useRef } from 'react';
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  ImageOff,
  Loader2,
  ShieldAlert,
} from 'lucide-react';
import { PreviewImageEntry } from '@/hooks/usePreviewImages';
import { BookThumbnailItem } from '@/utils/bookSpreads';

interface ThumbnailStripProps {
  thumbnails: BookThumbnailItem[];
  activeSpreadIndex: number;
  activeSheetPageNumber?: number;
  viewMode: 'spread' | 'sheet';
  getImageEntry: (itemKey: string, withOverlay?: boolean) => PreviewImageEntry | undefined;
  onSelectThumbnail: (thumb: BookThumbnailItem) => void;
  onRetryThumbnail: (thumb: BookThumbnailItem) => void;
}

export const ThumbnailStrip: React.FC<ThumbnailStripProps> = ({
  thumbnails,
  activeSpreadIndex,
  activeSheetPageNumber,
  viewMode,
  getImageEntry,
  onSelectThumbnail,
  onRetryThumbnail,
}) => {
  const trackRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  // Scroll active thumbnail gently into horizontal view
  useEffect(() => {
    const activeThumb = thumbnails.find((t) =>
      viewMode === 'sheet'
        ? t.sheetPageNumber === activeSheetPageNumber
        : t.spreadIndex === activeSpreadIndex
    );
    if (!activeThumb) return;
    const el = itemRefs.current[activeThumb.id];
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
    }
  }, [activeSpreadIndex, activeSheetPageNumber, viewMode, thumbnails]);

  const scrollTrack = (delta: number) => {
    const track = trackRef.current;
    if (!track) return;
    if (typeof track.scrollBy === 'function') {
      track.scrollBy({ left: delta, behavior: 'smooth' });
    } else {
      track.scrollLeft += delta;
    }
  };

  if (thumbnails.length === 0) return null;

  return (
    <div className="pt-2 border-t border-slate-200/80">
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => scrollTrack(-240)}
          aria-label="Scroll thumbnails left"
          className="h-16 px-1 rounded border border-slate-200 bg-white text-slate-500 hover:text-slate-800 hover:bg-slate-50 transition-colors shrink-0 flex items-center justify-center"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
        </button>

        <div
          ref={trackRef}
          className="flex-1 flex items-end gap-2.5 overflow-x-auto py-1.5 px-1 thumb-scrollbar"
          role="list"
          aria-label="Book page thumbnails"
        >
          {thumbnails.map((thumb) => {
            const isSelected =
              viewMode === 'sheet'
                ? thumb.sheetPageNumber === activeSheetPageNumber
                : thumb.spreadIndex === activeSpreadIndex;
            const entry = getImageEntry(thumb.imageKey, false);

            return (
              <button
                key={thumb.id}
                ref={(el) => {
                  itemRefs.current[thumb.id] = el;
                }}
                type="button"
                role="listitem"
                onClick={() => onSelectThumbnail(thumb)}
                aria-current={isSelected ? 'true' : undefined}
                title={`${thumb.label} (${thumb.subLabel})`}
                className="group flex flex-col items-center shrink-0 focus:outline-none"
              >
                <div
                  style={{ aspectRatio: `${thumb.widthPt} / ${thumb.heightPt}` }}
                  className={`relative h-16 rounded border overflow-hidden flex items-center justify-center bg-white transition-all ${
                    isSelected
                      ? 'border-bookabook-teal ring-2 ring-bookabook-teal/40 shadow-sm'
                      : 'border-slate-200 group-hover:border-slate-400'
                  }`}
                >
                  {entry?.objectUrl ? (
                    <img
                      src={entry.objectUrl}
                      alt={`Thumbnail ${thumb.label}`}
                      className="w-full h-full object-contain"
                    />
                  ) : entry?.error ? (
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        onRetryThumbnail(thumb);
                      }}
                      className="flex items-center justify-center w-full h-full bg-rose-50 text-rose-500"
                      title="Failed to load thumbnail — click to retry"
                    >
                      <ImageOff className="w-3.5 h-3.5" />
                    </span>
                  ) : (
                    <Loader2 className="w-3.5 h-3.5 text-slate-400 animate-spin" />
                  )}

                  {thumb.cropReadiness === 'MANUAL_REVIEW_REQUIRED' && (
                    <span
                      className="absolute top-1 right-1 w-3.5 h-3.5 rounded-full bg-amber-100 border border-amber-400 text-amber-700 flex items-center justify-center"
                      title="Manual Review Required"
                    >
                      <AlertTriangle className="w-2 h-2" />
                    </span>
                  )}
                  {thumb.cropReadiness === 'NOT_APPLICABLE' && (
                    <span
                      className="absolute top-1 right-1 w-3.5 h-3.5 rounded-full bg-rose-100 border border-rose-400 text-rose-700 flex items-center justify-center"
                      title="Unknown Layout — Auto-crop blocked"
                    >
                      <ShieldAlert className="w-2 h-2" />
                    </span>
                  )}
                </div>

                <span
                  className={`mt-1 text-[10px] tracking-tight whitespace-nowrap ${
                    isSelected
                      ? 'font-semibold text-bookabook-teal'
                      : 'font-medium text-slate-500 group-hover:text-slate-800'
                  }`}
                >
                  {thumb.label}
                </span>
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={() => scrollTrack(240)}
          aria-label="Scroll thumbnails right"
          className="h-16 px-1 rounded border border-slate-200 bg-white text-slate-500 hover:text-slate-800 hover:bg-slate-50 transition-colors shrink-0 flex items-center justify-center"
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};

