import React, { useState } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  ImageOff,
  Maximize2,
  RefreshCw,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { LoadingState, ErrorAlert } from '@/components/StateNotice';
import { StatusBadge } from '@/components/StatusBadge';
import { PreviewImageEntry } from '@/hooks/usePreviewImages';
import { PagePreviewInfo } from '@/types/api';
import { formatLayoutLabel } from '@/utils/formatters';

interface PreviewCanvasProps {
  page: PagePreviewInfo;
  totalPages: number;
  imageState?: PreviewImageEntry;
  onPrevPage: () => void;
  onNextPage: () => void;
  onRetryImage: () => void;
}

const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2];

export const PreviewCanvas: React.FC<PreviewCanvasProps> = ({
  page,
  totalPages,
  imageState,
  onPrevPage,
  onNextPage,
  onRetryImage,
}) => {
  const [fitToScreen, setFitToScreen] = useState<boolean>(true);
  const [zoom, setZoom] = useState<number>(1);

  const handleZoomIn = () => {
    setFitToScreen(false);
    const next = ZOOM_STEPS.find((z) => z > zoom);
    setZoom(next ?? Math.min(2.5, Number((zoom + 0.25).toFixed(2))));
  };

  const handleZoomOut = () => {
    setFitToScreen(false);
    const reversed = [...ZOOM_STEPS].reverse();
    const prev = reversed.find((z) => z < zoom);
    setZoom(prev ?? Math.max(0.25, Number((zoom - 0.25).toFixed(2))));
  };

  const handleSetActualSize = () => {
    setFitToScreen(false);
    setZoom(1);
  };

  const handleSetFitToScreen = () => {
    setFitToScreen(true);
    setZoom(1);
  };

  return (
    <div className="flex-1 min-w-0 bg-white border border-slate-200 rounded-lg flex flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="px-4 py-2.5 border-b border-slate-200 bg-slate-50 flex flex-wrap items-center justify-between gap-3">
        {/* Page Navigation & Current Indicator */}
        <div className="flex items-center gap-2">
          <div className="inline-flex items-center rounded-md border border-slate-300 bg-white overflow-hidden">
            <button
              type="button"
              onClick={onPrevPage}
              disabled={page.page_number <= 1}
              className="px-2.5 py-1.5 text-slate-700 hover:bg-slate-100 disabled:opacity-40 disabled:hover:bg-white border-r border-slate-200"
              aria-label="Previous sheet"
              title="Previous sheet"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-3 py-1 text-xs font-medium text-slate-800 whitespace-nowrap">
              Sheet <strong className="font-semibold">{page.page_number}</strong> of{' '}
              <strong className="font-semibold">{totalPages}</strong>
            </span>
            <button
              type="button"
              onClick={onNextPage}
              disabled={page.page_number >= totalPages}
              className="px-2.5 py-1.5 text-slate-700 hover:bg-slate-100 disabled:opacity-40 disabled:hover:bg-white border-l border-slate-200"
              aria-label="Next sheet"
              title="Next sheet"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <StatusBadge status={page.layout_type} />
          <StatusBadge status={page.crop_readiness} />
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleZoomOut}
            className="p-1.5 bg-white border border-slate-300 rounded text-slate-700 hover:bg-slate-100"
            aria-label="Zoom out"
            title="Zoom out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>

          <span className="px-2 py-1 text-xs font-mono text-slate-700 bg-white border border-slate-200 rounded min-w-[4.5rem] text-center">
            {fitToScreen ? 'Fit' : `${Math.round(zoom * 100)}%`}
          </span>

          <button
            type="button"
            onClick={handleZoomIn}
            className="p-1.5 bg-white border border-slate-300 rounded text-slate-700 hover:bg-slate-100"
            aria-label="Zoom in"
            title="Zoom in"
          >
            <ZoomIn className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={handleSetActualSize}
            className={`px-2.5 py-1 text-xs font-medium rounded border transition-colors ${
              !fitToScreen && zoom === 1
                ? 'bg-slate-900 text-white border-slate-900'
                : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100'
            }`}
          >
            100%
          </button>

          <button
            type="button"
            onClick={handleSetFitToScreen}
            className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded border transition-colors ${
              fitToScreen
                ? 'bg-slate-900 text-white border-slate-900'
                : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100'
            }`}
          >
            <Maximize2 className="w-3.5 h-3.5" />
            <span>Fit Screen</span>
          </button>
        </div>
      </div>

      {/* Preview Image Viewport */}
      <div className="relative bg-slate-100/90 overflow-auto p-4 flex items-center justify-center min-h-[440px]">
        {imageState?.error ? (
          <div className="max-w-md w-full space-y-3">
            <div className="flex flex-col items-center text-slate-500 mb-2">
              <ImageOff className="w-8 h-8 text-rose-500 mb-1" />
            </div>
            <ErrorAlert
              title={`Failed to load Sheet ${page.page_number} Preview PNG`}
              message={imageState.error}
              onRetry={onRetryImage}
            />
          </div>
        ) : !imageState?.objectUrl || imageState.loading ? (
          <LoadingState label={`Rendering composite preview PNG for Sheet ${page.page_number}...`} />
        ) : fitToScreen ? (
          <img
            src={imageState.objectUrl}
            alt={`Preview of Sheet ${page.page_number} (${formatLayoutLabel(page.layout_type)}) with backend crop boundaries`}
            className="max-w-full max-h-[calc(100vh-19rem)] w-auto h-auto object-contain rounded shadow-sm border border-slate-300 bg-white"
          />
        ) : (
          <div className="overflow-auto w-full max-h-[calc(100vh-19rem)] flex items-start justify-center">
            <img
              src={imageState.objectUrl}
              alt={`Preview of Sheet ${page.page_number} (${formatLayoutLabel(page.layout_type)}) at ${Math.round(zoom * 100)}% zoom`}
              style={{
                width: `${zoom * 100}%`,
                maxWidth: 'none',
              }}
              className="rounded shadow-sm border border-slate-300 bg-white shrink-0"
            />
          </div>
        )}
      </div>

      {/* Caption Bar */}
      <div className="px-4 py-2 border-t border-slate-200 bg-white flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
        <div>
          <span className="font-medium text-slate-800">Backend Composited PNG Overlay:</span>{' '}
          {page.layout_type === 'COVER_SPREAD' &&
            'Displays BACKCOVER & COVER crop boundaries, Protected Spine Exclusion Zone, and Manual Review markers.'}
          {page.layout_type === 'IMPOSITION_4UP' &&
            'Displays Quadrants Q1–Q4 (PAGE labels), vertical/horizontal midpoint cut lines, and outer sheet trim boundaries.'}
          {page.layout_type === 'SINGLE_PAGE' &&
            'Displays Single Page artwork crop boundary and nominal/non-nominal dimension status.'}
          {!page.layout_type &&
            'Unclassified sheet geometry — no crop boundaries generated.'}
        </div>
        <button
          type="button"
          onClick={onRetryImage}
          className="inline-flex items-center gap-1 text-slate-500 hover:text-slate-900"
          title="Reload PNG image from backend"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Reload Image</span>
        </button>
      </div>
    </div>
  );
};

