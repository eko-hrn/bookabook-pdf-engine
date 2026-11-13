import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  CheckSquare,
  Info,
  Layers,
  ShieldAlert,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { StatusBadge } from '@/components/StatusBadge';
import { DocumentPreviewResponse, PagePreviewInfo } from '@/types/api';
import { formatLayoutLabel } from '@/utils/formatters';

interface PreviewInspectorProps {
  documentId: string;
  preview: DocumentPreviewResponse;
  page: PagePreviewInfo;
}

export const PreviewInspector: React.FC<PreviewInspectorProps> = ({
  documentId,
  preview,
  page,
}) => {
  return (
    <div className="w-full xl:w-80 shrink-0 space-y-4">
      {/* Selected Page Properties */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-900">
              Sheet {page.page_number} Metadata
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-500">idx {page.pdf_page_index}</span>
        </div>

        <dl className="grid grid-cols-[auto_1fr] gap-y-2.5 gap-x-3 items-center text-xs">
          <dt className="text-slate-500">Layout Type</dt>
          <dd className="text-right font-medium text-slate-900">
            {formatLayoutLabel(page.layout_type)}
          </dd>

          <dt className="text-slate-500">Crop Readiness</dt>
          <dd className="flex justify-end min-w-0">
            <StatusBadge status={page.crop_readiness} size="sm" />
          </dd>

          <dt className="text-slate-500">Sheet Size (pt)</dt>
          <dd className="text-right font-mono text-slate-900">
            {page.width_pt.toFixed(2)} × {page.height_pt.toFixed(2)}
          </dd>

          <dt className="text-slate-500">Orientation</dt>
          <dd className="text-right font-medium text-slate-800">{page.orientation}</dd>

          <dt className="text-slate-500">Expected Output Yield</dt>
          <dd className="text-right font-semibold text-slate-900">
            {page.expected_page_yield} region{page.expected_page_yield === 1 ? '' : 's'}
          </dd>
        </dl>

        {/* Backend Status Badge Accessibility Label */}
        {page.status_badge && (
          <div className="bg-slate-50 border border-slate-200 rounded p-2.5 text-xs text-slate-700">
            <div className="font-semibold text-slate-900">{page.status_badge.badge_text}</div>
            <div className="text-slate-600 mt-0.5">{page.status_badge.accessibility_label}</div>
          </div>
        )}

        <Link
          to={`/documents/${encodeURIComponent(documentId)}/review?page=${page.page_number}`}
          className="w-full inline-flex items-center justify-center gap-2 px-3.5 py-2 text-xs font-semibold text-white bg-slate-900 rounded-md hover:bg-slate-800 transition-colors"
        >
          <CheckSquare className="w-3.5 h-3.5" />
          <span>Review Sheet {page.page_number} in Review Workspace</span>
        </Link>
      </div>

      {/* Layout Region Overlay Guide (No JS calculations — backend metadata & overlay legend) */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-2.5">
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-900 uppercase tracking-wide">
          <Info className="w-3.5 h-3.5 text-slate-500" />
          <span>Overlay Boundaries Legend</span>
        </div>

        {page.layout_type === 'COVER_SPREAD' && (
          <ul className="text-xs text-slate-600 space-y-1.5 leading-relaxed">
            <li className="flex items-start gap-2">
              <span className="w-2.5 h-2.5 mt-1 rounded-sm border-2 border-dashed border-amber-600 bg-amber-100 shrink-0" />
              <span>
                <strong>BACKCOVER &amp; COVER:</strong> Amber dashed crop regions marked{' '}
                <em>Manual Review Required</em> (auto-crop disabled).
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-2.5 h-2.5 mt-1 rounded-sm border border-amber-600 bg-amber-300/60 shrink-0" />
              <span>
                <strong>Protected Spine Zone:</strong> Hatched center exclusion band preserving
                book spine; crop regions never cross this zone.
              </span>
            </li>
          </ul>
        )}

        {page.layout_type === 'IMPOSITION_4UP' && (
          <ul className="text-xs text-slate-600 space-y-1.5 leading-relaxed">
            <li className="flex items-start gap-2">
              <span className="w-2.5 h-2.5 mt-1 rounded-sm border-2 border-emerald-600 bg-emerald-100 shrink-0" />
              <span>
                <strong>Quadrants Q1–Q4:</strong> Four numbered book page boundaries (Q1 top-left,
                Q2 top-right, Q3 bottom-left, Q4 bottom-right).
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-2.5 h-2.5 mt-1 rounded-sm border-2 border-dashed border-blue-600 bg-blue-100 shrink-0" />
              <span>
                <strong>Midpoint Cut Lines:</strong> Blue dashed vertical &amp; horizontal bisectors.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-2.5 h-2.5 mt-1 rounded-sm border-2 border-dashed border-violet-600 bg-violet-100 shrink-0" />
              <span>
                <strong>Outer Sheet Trim:</strong> Purple dashed perimeter trim boundary.
              </span>
            </li>
          </ul>
        )}

        {page.layout_type === 'SINGLE_PAGE' && (
          <ul className="text-xs text-slate-600 space-y-1.5 leading-relaxed">
            <li className="flex items-start gap-2">
              <span className="w-2.5 h-2.5 mt-1 rounded-sm border-2 border-emerald-600 bg-emerald-100 shrink-0" />
              <span>
                <strong>Single Page Crop Boundary:</strong> Annotated artwork crop box with target
                pixel &amp; DPI label. Non-nominal sizes hold for manual review.
              </span>
            </li>
          </ul>
        )}

        {!page.layout_type && (
          <p className="text-xs text-rose-700 leading-relaxed">
            Sheet geometry could not be classified into Cover, 4-Up, or Single Page layouts.
            Production cropping and approval are blocked.
          </p>
        )}
      </div>

      {/* Warnings & Discrepancies */}
      {(page.warnings.length > 0 || page.unresolved_discrepancies.length > 0) && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-900">
            <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
            <span>Warnings &amp; Safeguard Notices</span>
          </div>

          {page.warnings.length > 0 && (
            <ul className="list-disc pl-4 text-xs text-amber-900 space-y-1">
              {page.warnings.map((w, idx) => (
                <li key={idx} className="break-words">
                  {w}
                </li>
              ))}
            </ul>
          )}

          {page.unresolved_discrepancies.length > 0 && (
            <div className="pt-2 border-t border-amber-200/80 space-y-1">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-amber-800">
                Unresolved Spec Discrepancies
              </div>
              <ul className="space-y-1">
                {page.unresolved_discrepancies.map((d, idx) => (
                  <li
                    key={idx}
                    className="text-[11px] font-mono bg-white/80 border border-amber-200 rounded px-2 py-1 text-amber-900 break-all"
                  >
                    {d}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Document Validation Summary */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-900 uppercase tracking-wide">
            Crop Plan Validation
          </span>
          {preview.validation_summary.is_valid ? (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Valid
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-700">
              <ShieldAlert className="w-3.5 h-3.5" />
              Errors Found
            </span>
          )}
        </div>

        <dl className="grid grid-cols-2 gap-y-1.5 text-xs">
          <dt className="text-slate-500">Document Status</dt>
          <dd className="text-right font-mono text-[11px] text-slate-900">
            {preview.document_status}
          </dd>

          <dt className="text-slate-500">Expected Book Yield</dt>
          <dd className="text-right font-medium text-slate-900">
            {preview.expected_book_pages} pages
          </dd>

          <dt className="text-slate-500">Validated Regions</dt>
          <dd className="text-right font-medium text-slate-900">
            {preview.validation_summary.valid_regions_count} /{' '}
            {preview.validation_summary.total_regions}
          </dd>
        </dl>

        {preview.validation_summary.errors.length > 0 && (
          <div className="text-xs text-rose-800 bg-rose-50 border border-rose-200 rounded p-2 space-y-1">
            {preview.validation_summary.errors.map((err, i) => (
              <div key={i}>{err}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

