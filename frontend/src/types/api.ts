/**
 * TypeScript domain models matching the Bookabook FastAPI backend Pydantic schemas.
 * Strictly aligned with app/api/schemas/ and app/crop/review/models.py.
 */

export type LayoutType = 'COVER_SPREAD' | 'IMPOSITION_4UP' | 'SINGLE_PAGE';

export type Orientation = 'PORTRAIT' | 'LANDSCAPE' | 'SQUARE';

export type ClassificationStatus =
  | 'CLASSIFIED'
  | 'UNKNOWN_LAYOUT'
  | 'CANDIDATE_IMPOSITION_4UP_FLIPPED';

export type CropReadinessStatus =
  | 'CROP_READY'
  | 'MANUAL_REVIEW_REQUIRED'
  | 'NOT_APPLICABLE';

export type ReviewDecisionState =
  | 'PENDING'
  | 'APPROVED'
  | 'REJECTED'
  | 'NEEDS_REVISION';

export type DocumentReviewStatus =
  | 'PENDING_REVIEW'
  | 'PARTIALLY_REVIEWED'
  | 'REVIEW_COMPLETED'
  | 'REVIEW_REJECTED'
  | 'REVIEW_BLOCKED';

export type ReviewEventType =
  | 'SESSION_CREATED'
  | 'DECISION_RECORDED'
  | 'NOTES_UPDATED';

export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  database_connected: boolean;
  timestamp: string;
}

export interface PageDimensionInfo {
  page_number: number;
  width_pt: number;
  height_pt: number;
  orientation: Orientation | string;
  detected_layout: LayoutType | string | null;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  file_size_bytes: number;
  page_count: number;
  created_at: string;
  status: string;
}

export interface DocumentMetadataResponse {
  document_id: string;
  filename: string;
  file_size_bytes: number;
  page_count: number;
  created_at: string;
  status: string;
  pages: PageDimensionInfo[];
}

export interface PagePreviewStatusBadge {
  status: string;
  badge_text: string;
  accessibility_label: string;
  stroke_color: string;
  fill_color: string;
  pattern_type: string;
}

export interface PreviewRegionInfo {
  region_id: string;
  quadrant: number | null;
  width_pt: number;
  height_pt: number;
  target_width_px: number;
  target_height_px: number;
  blank_page_status: string;
  preview_image_url: string;
}

export interface PagePreviewInfo {
  page_number: number;
  pdf_page_index: number;
  width_pt: number;
  height_pt: number;
  orientation: string;
  layout_type: LayoutType | string | null;
  crop_readiness: CropReadinessStatus | string;
  expected_page_yield: number;
  preview_image_url: string;
  status_badge: PagePreviewStatusBadge;
  warnings: string[];
  unresolved_discrepancies: string[];
  regions?: PreviewRegionInfo[];
}

export interface PreviewValidationSummary {
  is_valid: boolean;
  overall_status: string;
  total_regions: number;
  valid_regions_count: number;
  invalid_regions_count: number;
  errors: string[];
  warnings: string[];
}

export interface DocumentPreviewResponse {
  document_id: string;
  source_filename: string;
  total_pages: number;
  expected_book_pages: number;
  document_status: string;
  has_unknown_layout: boolean;
  has_manual_review_required: boolean;
  pages: PagePreviewInfo[];
  validation_summary: PreviewValidationSummary;
}

export interface ReviewHistoryEntry {
  entry_id: string;
  pdf_page_index: number | null;
  pdf_page_number: number | null;
  event_type: ReviewEventType;
  previous_decision: ReviewDecisionState | null;
  new_decision: ReviewDecisionState | null;
  reviewer_id: string;
  timestamp: string;
  notes: string | null;
  reason: string | null;
}

export interface ReviewHistory {
  entries: ReviewHistoryEntry[];
}

export interface PageReviewRecord {
  pdf_page_index: number;
  pdf_page_number: number;
  layout_type: LayoutType | string | null;
  classification_status: ClassificationStatus | string;
  crop_readiness: CropReadinessStatus | string;
  review_decision: ReviewDecisionState;
  reviewer_id: string | null;
  reviewed_at: string | null;
  notes: string | null;
  warnings: string[];
  unresolved_discrepancies: string[];
  is_cover: boolean;
  is_non_nominal: boolean;
  history: ReviewHistoryEntry[];
}

export interface DocumentReviewSummary {
  session_id: string;
  source_filename: string;
  total_pages: number;
  approved_pages_count: number;
  rejected_pages_count: number;
  needs_revision_pages_count: number;
  pending_pages_count: number;
  status: DocumentReviewStatus;
  is_review_completed: boolean;
  requires_production_authorization: boolean;
  summary_message: string;
  unresolved_discrepancies: string[];
  reviewed_at: string | null;
}

export interface ReviewSession {
  session_id: string;
  source_filename: string;
  created_at: string;
  updated_at: string;
  page_records: PageReviewRecord[];
  document_summary: DocumentReviewSummary;
  history: ReviewHistory;
  metadata: Record<string, unknown>;
}

export interface CreateReviewSessionRequest {
  document_id: string;
  session_id?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface RecordDecisionRequest {
  decision: ReviewDecisionState;
  reviewer_id: string;
  notes?: string | null;
  reason?: string | null;
}

export interface UpdateNotesRequest {
  reviewer_id: string;
  notes: string;
}

export interface CompressionFailureItem {
  filename: string;
  page_key: string;
  page_kind: string;
  actual_size_bytes: number;
  max_allowed_bytes: number;
  min_quality_threshold: number;
  quality_attempted: number;
  reason: string;
}

export interface ExportValidationSummary {
  is_valid: boolean;
  auto_validated: boolean;
  compression_status?: 'PASSED' | 'FAILED' | string;
  total_pdf_pages: number;
  cover_detected: boolean;
  backcover_detected: boolean;
  content_pages_count: number;
  blank_pages_detected: number;
  total_exported_files: number;
  files_under_300kb: number;
  files_300_to_700kb: number;
  files_700kb_to_1mb: number;
  files_1mb_to_2mb: number;
  files_over_2mb: number;
  files_within_400kb?: number;
  files_within_500kb?: number;
  files_over_400kb_within_1mb?: number;
  files_over_500kb_within_1mb?: number;
  files_over_policy_limit?: number;
  compression_failures?: CompressionFailureItem[];
  warnings: string[];
  errors: string[];
}

export interface ProcessedPageItem {
  page_key: string;
  filename: string;
  page_kind: 'COVER' | 'CONTENT' | 'BACKCOVER' | string;
  order_index: number;
  source_pdf_page: number;
  quadrant: number | null;
  width_px: number;
  height_px: number;
  dpi: number;
  file_size_bytes: number;
  max_allowed_bytes?: number;
  quality_used: number;
  subsampling_used: string;
  compression_tier: string;
  compression_status?: 'PASSED' | 'FAILED' | string;
  is_blank: boolean;
  sha256: string;
  preview_url: string;
  download_url: string;
}

export interface ProcessPdfResponse {
  job_id: string;
  source_filename: string;
  target_dpi: number;
  content_pages_count: number;
  total_exported_files: number;
  validation: ExportValidationSummary;
  pages: ProcessedPageItem[];
  zip_download_url: string;
}

export interface SaveBookRequest {
  job_id: string;
  title: string;
  author: string;
  authors_all: string;
  description: string;
  year: number | null;
  age_group: string;
  sponsor: string;
  content_pages: number | null;
  phone: string;
  email: string;
}

export interface BookPageDetail {
  page_key: string;
  filename: string;
  page_kind: 'COVER' | 'CONTENT' | 'BACKCOVER' | string;
  order_index: number;
  source_pdf_page: number;
  quadrant: number | null;
  width_px: number;
  height_px: number;
  dpi: number;
  file_size_bytes: number;
  quality_used: number;
  subsampling_used: string;
  compression_tier: string;
  sha256: string;
  object_key: string;
  is_blank: boolean;
  preview_url: string;
  download_url: string;
}

export interface BookSummary {
  book_id: string;
  title: string;
  author: string;
  authors_all: string;
  description: string;
  year: number | null;
  age_group: string;
  sponsor: string;
  content_pages: number;
  phone: string;
  email: string;
  source_filename: string;
  total_exported_pages: number;
  cover_filename: string;
  backcover_filename: string;
  cover_url: string | null;
  storage_backend: string;
  created_at: string;
}

export interface BookDetailResponse extends BookSummary {
  validation_summary: Record<string, unknown>;
  pages: BookPageDetail[];
  zip_download_url: string;
}

export interface BookListResponse {
  books: BookSummary[];
  total: number;
}

