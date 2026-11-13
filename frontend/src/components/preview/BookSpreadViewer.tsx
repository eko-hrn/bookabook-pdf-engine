import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Columns2,
  FileImage,
  ImageOff,
  Layers,
  Loader2,
  Maximize2,
  RefreshCw,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { StatusBadge } from '@/components/StatusBadge';
import { ThumbnailStrip } from '@/components/preview/ThumbnailStrip';
import { PreviewImageEntry } from '@/hooks/usePreviewImages';
import { PagePreviewInfo } from '@/types/api';
import {
  BookSpreadItem,
  BookThumbnailItem,
  SpreadSlot,
  findSpreadIndexForSheet,
  getSheetImageKey,
} from '@/utils/bookSpreads';

const ZOOM_PRESETS = [75, 100, 125, 150, 200] as const;

export interface BookSpreadViewerProps {
  spreads: BookSpreadItem[];
  thumbnails: BookThumbnailItem[];
  pages: PagePreviewInfo[];
  activeSpreadIndex: number;
  onSelectSpreadIndex: (index: number) => void;
  viewMode: 'spread' | 'sheet';
  onChangeViewMode: (mode: 'spread' | 'sheet') => void;
  showOverlay: boolean;
  onToggleOverlay: (overlay: boolean) => void;
  getImageEntry: (itemKey: string, withOverlay?: boolean) => PreviewImageEntry | undefined;
  onEnsureImage: (
    itemKey: string,
    apiPath: string,
    withOverlay?: boolean,
    fallbackSheetPage?: number
  ) => void;
  onReloadImage: (
    itemKey: string,
    apiPath: string,
    withOverlay?: boolean,
    fallbackSheetPage?: number
  ) => void;
  onSelectSheetPage?: (pageNumber: number) => void;
  compact?: boolean;
}

export const BookSpreadViewer: React.FC<BookSpreadViewerProps> = ({
  spreads,
  thumbnails,
  pages,
  activeSpreadIndex,
  onSelectSpreadIndex,
  viewMode,
  onChangeViewMode,
  showOverlay,
  onToggleOverlay,
  getImageEntry,
  onEnsureImage,
  onReloadImage,
  onSelectSheetPage,
  compact = false,
}) => {
  const [zoomMode, setZoomMode] = useState<'fit' | number>('fit');

  const safeIndex =
    spreads.length > 0 ? Math.min(Math.max(activeSpreadIndex, 0), spreads.length - 1) : 0;
  const activeSpread = spreads[safeIndex];
  const activePage = activeSpread?.sheetPage ?? pages[0];
  const sheetCount = pages.length;
  const sheetPageNumber = activePage?.page_number ?? 1;

  // Ensure active images are requested immediately on view change
  useEffect(() => {
    if (!activeSpread || !activePage) return;

    if (viewMode === 'sheet') {
      onEnsureImage(
        getSheetImageKey(activePage.page_number),
        activePage.preview_image_url,
        showOverlay,
        activePage.page_number
      );
      return;
    }

    if (activeSpread.kind === 'BOOK_SPREAD') {
      if (activeSpread.leftSlot) {
        onEnsureImage(
          activeSpread.leftSlot.imageKey,
          activeSpread.leftSlot.apiPath,
          showOverlay
        );
      }
      if (activeSpread.rightSlot) {
        onEnsureImage(
          activeSpread.rightSlot.imageKey,
          activeSpread.rightSlot.apiPath,
          showOverlay
        );
      }
    } else if (activeSpread.singleSlot) {
      onEnsureImage(
        activeSpread.singleSlot.imageKey,
        activeSpread.singleSlot.apiPath,
        showOverlay,
        activePage.page_number
      );
    }
  }, [activeSpread, activePage, viewMode, showOverlay, onEnsureImage]);

  if (!activeSpread || !activePage) {
    return null;
  }

  const zoomPercentLabel = zoomMode === 'fit' ? 'Fit' : `${zoomMode}%`;

  const stepZoom = (dir: 1 | -1) => {
    if (zoomMode === 'fit') {
      setZoomMode(dir > 0 ? 125 : 75);
      return;
    }
    const idx = ZOOM_PRESETS.indexOf(zoomMode as (typeof ZOOM_PRESETS)[number]);
    if (idx === -1) {
      setZoomMode(100);
      return;
    }
    const nextIdx = Math.min(Math.max(idx + dir, 0), ZOOM_PRESETS.length - 1);
    setZoomMode(ZOOM_PRESETS[nextIdx]);
  };

  const handleStepSheet = (delta: 1 | -1) => {
    const nextSheet = Math.min(Math.max(sheetPageNumber + delta, 1), sheetCount);
    if (nextSheet === sheetPageNumber) return;
    const targetIdx = findSpreadIndexForSheet(spreads, nextSheet);
    onSelectSpreadIndex(targetIdx);
    onSelectSheetPage?.(nextSheet);
  };

  const handleSelectSpread = (index: number) => {
    const clamped = Math.min(Math.max(index, 0), spreads.length - 1);
    onSelectSpreadIndex(clamped);
    const targetSheet = spreads[clamped]?.sheetPageNumber;
    if (targetSheet !== undefined) {
      onSelectSheetPage?.(targetSheet);
    }
  };

  const renderSlotContent = (
    slot: SpreadSlot,
    altText: string,
    fallbackPage?: number,
    imgStyle?: React.CSSProperties,
    imgClassName = 'w-full h-full object-contain select-none'
  ) => {
    const entry = getImageEntry(slot.imageKey, showOverlay);

    if (entry?.loading || (!entry?.objectUrl && !entry?.error)) {
      return (
        <div
          style={{ aspectRatio: `${slot.widthPt} / ${slot.heightPt}`, minHeight: '220px' }}
          className="w-full h-full flex flex-col items-center justify-center bg-white text-slate-400 gap-2 p-4"
        >
          <Loader2 className="w-5 h-5 animate-spin text-bookabook-teal" />
          <span className="text-[11px] text-slate-500">Rendering {slot.label}...</span>
        </div>
      );
    }

    if (entry?.error) {
      return (
        <div
          style={{ aspectRatio: `${slot.widthPt} / ${slot.heightPt}`, minHeight: '220px' }}
          className="w-full h-full flex flex-col items-center justify-center bg-rose-50/60 text-rose-700 gap-2 p-4 text-center"
        >
          <ImageOff className="w-5 h-5 text-rose-500" />
          <span className="text-[11px]">{entry.error}</span>
          <button
            type="button"
            onClick={() =>
              onReloadImage(slot.imageKey, slot.apiPath, showOverlay, fallbackPage)
            }
            className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium bg-white border border-rose-200 rounded hover:bg-rose-50"
          >
            <RefreshCw className="w-3 h-3" />
            Retry
          </button>
        </div>
      );
    }

    return (
      <img
        src={entry.objectUrl}
        alt={altText}
        style={imgStyle}
        className={imgClassName}
      />
    );
  };

  const activeSingleSlot: SpreadSlot =
    viewMode === 'sheet'
      ? {
          id: `full-sheet-${activePage.page_number}`,
          label: `Sheet ${activePage.page_number}`,
          imageKey: getSheetImageKey(activePage.page_number),
          apiPath: activePage.preview_image_url,
          widthPt: activePage.width_pt,
          heightPt: activePage.height_pt,
        }
      : activeSpread.singleSlot ?? {
          id: `full-sheet-${activePage.page_number}`,
          label: activeSpread.title,
          imageKey: getSheetImageKey(activePage.page_number),
          apiPath: activePage.preview_image_url,
          widthPt: activePage.width_pt,
          heightPt: activePage.height_pt,
        };

  const singleAltText =
    activePage.layout_type === 'COVER_SPREAD'
      ? showOverlay
        ? `Preview of Sheet ${activePage.page_number} (Cover Spread) with backend crop boundaries`
        : `Clean preview of Sheet ${activePage.page_number} (Cover Spread)`
      : `Preview of Sheet ${activePage.page_number} (${activePage.layout_type || 'Unknown'})`;

  const maxStageHeight = compact ? 340 : 480;
  const baseSpreadWidthPx = compact ? 520 : 660;
  const spreadContainerStyle: React.CSSProperties =
    zoomMode === 'fit'
      ? { width: '100%', maxWidth: `${baseSpreadWidthPx}px` }
      : {
          width: `${Math.round(baseSpreadWidthPx * (zoomMode / 100))}px`,
          maxWidth: 'none',
        };

  return (
    <div className="bg-white border border-slate-200/90 rounded-lg shadow-card overflow-hidden flex flex-col">
      {/* Compact Production Toolbar */}
      <div className="px-4 py-2.5 border-b border-slate-200/80 bg-white flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          <h3 className="text-xs font-semibold text-slate-900">
            {viewMode === 'sheet'
              ? `Sheet ${activePage.page_number} Full Inspection`
              : activeSpread.title}
          </h3>
          <StatusBadge status={activePage.crop_readiness} size="sm" />
          <span className="text-[11px] text-slate-500 hidden sm:inline">
            {viewMode === 'sheet' ? activeSpread.subtitle.split('•')[0] : activeSpread.subtitle}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {/* Sheet step control */}
          <div className="flex items-center gap-0.5 mr-1 border border-slate-200 rounded-md bg-bookabook-field px-1 py-0.5">
            <button
              type="button"
              onClick={() => handleStepSheet(-1)}
              disabled={sheetPageNumber <= 1}
              aria-label="Previous sheet"
              className="p-0.5 rounded text-slate-600 hover:text-slate-900 disabled:opacity-35"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span className="px-1.5 text-[11px] font-medium text-slate-700 whitespace-nowrap">
              {`Sheet ${sheetPageNumber} of ${sheetCount}`}
            </span>
            <button
              type="button"
              onClick={() => handleStepSheet(1)}
              disabled={sheetPageNumber >= sheetCount}
              aria-label="Next sheet"
              className="p-0.5 rounded text-slate-600 hover:text-slate-900 disabled:opacity-35"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Book Spread vs Full Sheet Toggle */}
          <div
            className="inline-flex rounded-md border border-slate-200 bg-bookabook-field p-0.5 text-[11px]"
            role="group"
            aria-label="Inspection view mode"
          >
            <button
              type="button"
              onClick={() => onChangeViewMode('spread')}
              aria-pressed={viewMode === 'spread'}
              className={`inline-flex items-center gap-1 px-2 py-1 rounded font-medium transition-colors ${
                viewMode === 'spread'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Columns2 className="w-3 h-3" />
              Book Spread
            </button>
            <button
              type="button"
              onClick={() => onChangeViewMode('sheet')}
              aria-pressed={viewMode === 'sheet'}
              className={`inline-flex items-center gap-1 px-2 py-1 rounded font-medium transition-colors ${
                viewMode === 'sheet'
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <FileImage className="w-3 h-3" />
              Full Sheet
            </button>
          </div>

          {/* Crop Overlay Toggle (?overlay=true|false) */}
          <button
            type="button"
            onClick={() => onToggleOverlay(!showOverlay)}
            aria-pressed={showOverlay}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md border text-[11px] font-medium transition-colors ${
              showOverlay
                ? 'bg-bookabook-tealSoft border-bookabook-teal/40 text-bookabook-teal'
                : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Layers className="w-3 h-3" />
            Overlays {showOverlay ? 'On' : 'Off'}
          </button>

          {/* Compact Zoom Controls */}
          <div className="flex items-center gap-0.5 border border-slate-200 rounded-md bg-white px-1 py-0.5">
            <button
              type="button"
              onClick={() => stepZoom(-1)}
              disabled={zoomMode === ZOOM_PRESETS[0]}
              aria-label="Zoom out"
              className="p-1 rounded text-slate-600 hover:bg-slate-100 disabled:opacity-40"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="px-1.5 text-[11px] font-mono text-slate-700 min-w-[2.4rem] text-center">
              {zoomPercentLabel}
            </span>
            <button
              type="button"
              onClick={() => stepZoom(1)}
              disabled={zoomMode === ZOOM_PRESETS[ZOOM_PRESETS.length - 1]}
              aria-label="Zoom in"
              className="p-1 rounded text-slate-600 hover:bg-slate-100 disabled:opacity-40"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setZoomMode('fit')}
              aria-label="Fit Screen"
              className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] font-medium rounded transition-colors ${
                zoomMode === 'fit'
                  ? 'bg-bookabook-teal text-white'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <Maximize2 className="w-2.5 h-2.5" />
              Fit Screen
            </button>
          </div>
        </div>
      </div>

      {/* Inline Policy / Context Banner (Cover standalone / Single / Unknown) */}
      {(activePage.layout_type === 'COVER_SPREAD' || activeSpread.statusNote) && (
        <div
          className={`px-4 py-2 border-b text-[11px] flex items-center gap-2 ${
            activePage.crop_readiness === 'NOT_APPLICABLE'
              ? 'bg-rose-50/70 border-rose-200/80 text-rose-800'
              : activePage.crop_readiness === 'MANUAL_REVIEW_REQUIRED'
                ? 'bg-amber-50/70 border-amber-200/80 text-amber-900'
                : 'bg-sky-50/60 border-sky-200/70 text-sky-900'
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>
            {activeSpread.statusNote ||
              'Cover Spread displayed independently (protected spine zone intact).'}
          </span>
        </div>
      )}

      {/* Book Spread Presentation Stage (Matching 02-book-preview.png) */}
      <div className="p-4 sm:p-5 bg-white space-y-3">
        <div
          className={`bg-bookabook-field/70 border border-slate-200/80 rounded-md p-4 sm:p-5 overflow-auto flex justify-center items-center admin-scrollbar`}
          style={{ minHeight: compact ? '270px' : '380px' }}
        >
          {viewMode === 'spread' &&
          activeSpread.kind === 'BOOK_SPREAD' &&
          activeSpread.leftSlot &&
          activeSpread.rightSlot ? (
            <div
              className="flex flex-col items-center mx-auto"
              style={spreadContainerStyle}
            >
              {/* Open Two-Page Spread Book Mockup */}
              <div className="flex items-stretch justify-center w-full shadow-[0_8px_24px_rgba(15,23,42,0.12)] rounded-sm overflow-hidden border border-slate-200 bg-white">
                <div
                  className="relative flex-1 bg-white overflow-hidden"
                  style={{
                    aspectRatio: `${activeSpread.leftSlot.widthPt} / ${activeSpread.leftSlot.heightPt}`,
                  }}
                >
                  {renderSlotContent(
                    activeSpread.leftSlot,
                    `Left spread page ${activeSpread.leftSlot.label}`
                  )}
                  <div
                    className="pointer-events-none absolute inset-y-0 right-0 w-4 bg-gradient-to-l from-slate-900/15 to-transparent"
                    aria-hidden="true"
                  />
                </div>

                {/* Center Spine Fold */}
                <div
                  className="w-[3px] shrink-0 bg-gradient-to-r from-slate-700/30 via-slate-400/20 to-slate-700/30"
                  aria-hidden="true"
                />

                <div
                  className="relative flex-1 bg-white overflow-hidden"
                  style={{
                    aspectRatio: `${activeSpread.rightSlot.widthPt} / ${activeSpread.rightSlot.heightPt}`,
                  }}
                >
                  {renderSlotContent(
                    activeSpread.rightSlot,
                    `Right spread page ${activeSpread.rightSlot.label}`
                  )}
                  <div
                    className="pointer-events-none absolute inset-y-0 left-0 w-4 bg-gradient-to-r from-slate-900/15 to-transparent"
                    aria-hidden="true"
                  />
                </div>
              </div>

              {/* Crisp Quadrant & Logical Page Tags Below Spread */}
              <div className="mt-2.5 flex items-center justify-between w-full px-1 text-[11px] text-slate-500">
                <span className="font-medium text-slate-700">
                  {activeSpread.leftSlot.label}
                </span>
                <span className="font-mono text-[10px] text-slate-400">
                  Native Aspect Ratio Preserved
                </span>
                <span className="font-medium text-slate-700">
                  {activeSpread.rightSlot.label}
                </span>
              </div>
            </div>
          ) : (
            <div
              className="flex flex-col items-center mx-auto"
              style={{
                maxWidth: '100%',
              }}
            >
              <div className="inline-flex shadow-[0_6px_20px_rgba(15,23,42,0.10)] rounded-sm overflow-hidden border border-slate-200 bg-white mx-auto">
                {renderSlotContent(
                  activeSingleSlot,
                  singleAltText,
                  activePage.page_number,
                  zoomMode === 'fit'
                    ? { maxHeight: `${maxStageHeight}px`, maxWidth: '100%', width: 'auto', height: 'auto' }
                    : { height: `${Math.round(maxStageHeight * (zoomMode / 100))}px`, width: 'auto', maxWidth: 'none' },
                  'block object-contain select-none'
                )}
              </div>

              {activePage.layout_type === 'COVER_SPREAD' && viewMode === 'spread' && (
                <div className="mt-2.5 flex items-center gap-4 text-[11px] text-slate-500">
                  <span>BACKCOVER (Left)</span>
                  <span className="px-2 py-0.5 rounded bg-amber-50 border border-amber-200 text-amber-800 font-medium">
                    Protected Spine (42.57 pt)
                  </span>
                  <span>COVER (Right)</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Centered < previous  next > Bar Directly Underneath Spread (02-book-preview.png) */}
        <div className="flex items-center justify-center gap-5 pt-0.5 text-xs">
          <button
            type="button"
            onClick={() => handleSelectSpread(safeIndex - 1)}
            disabled={safeIndex <= 0}
            aria-label="Previous spread"
            className="inline-flex items-center gap-1 text-slate-600 hover:text-bookabook-teal font-medium disabled:opacity-35 transition-colors"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            previous
          </button>

          <span className="text-[11px] font-mono text-slate-500">
            {safeIndex + 1} / {spreads.length}
          </span>

          <button
            type="button"
            onClick={() => handleSelectSpread(safeIndex + 1)}
            disabled={safeIndex >= spreads.length - 1}
            aria-label="Next spread"
            className="inline-flex items-center gap-1 text-slate-600 hover:text-bookabook-teal font-medium disabled:opacity-35 transition-colors"
          >
            next
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Horizontal Bottom Thumbnail Navigation Strip (02-book-preview.png) */}
        <ThumbnailStrip
          thumbnails={thumbnails}
          activeSpreadIndex={safeIndex}
          activeSheetPageNumber={sheetPageNumber}
          viewMode={viewMode}
          getImageEntry={getImageEntry}
          onSelectThumbnail={(thumb) => {
            onSelectSpreadIndex(thumb.spreadIndex);
            onSelectSheetPage?.(thumb.sheetPageNumber);
          }}
          onRetryThumbnail={(thumb) =>
            onReloadImage(thumb.imageKey, thumb.apiPath, false)
          }
        />
      </div>
    </div>
  );
};
