import React, { useRef, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  Eye,
  FileText,
  FileUp,
  Loader2,
  X,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { ApiClientError, documentsApi, MAX_UPLOAD_SIZE_BYTES } from '@/api';
import { ErrorAlert } from '@/components/StateNotice';
import { StatusBadge } from '@/components/StatusBadge';
import { useWorkspaceContext } from '@/hooks/useWorkspaceContext';
import { DocumentUploadResponse } from '@/types/api';
import { formatBytes, formatTimestamp, validatePdfFile } from '@/utils/formatters';

export const UploadPage: React.FC = () => {
  const { registerDocument, reviewerId, setReviewerId } = useWorkspaceContext();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [validating, setValidating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<{ message: string; statusCode?: number } | null>(null);
  const [uploadedDoc, setUploadedDoc] = useState<DocumentUploadResponse | null>(null);

  const handleFileCandidate = async (file: File | null) => {
    setApiError(null);
    setValidationError(null);
    setUploadedDoc(null);
    setUploadProgress(0);

    if (!file) {
      setSelectedFile(null);
      return;
    }

    setValidating(true);
    const check = await validatePdfFile(file);
    setValidating(false);

    if (!check.valid) {
      setSelectedFile(null);
      setValidationError(check.error || 'Selected file failed PDF validation.');
      return;
    }

    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (uploading) return;
    const droppedFile = e.dataTransfer.files?.[0] ?? null;
    void handleFileCandidate(droppedFile);
  };

  const handleUpload = async () => {
    if (!selectedFile || uploading || validating) return;

    setUploading(true);
    setUploadProgress(0);
    setApiError(null);

    try {
      const response = await documentsApi.uploadDocument(selectedFile, (pct) => {
        setUploadProgress(pct);
      });
      setUploadedDoc(response);
      registerDocument({
        document_id: response.document_id,
        filename: response.filename,
        page_count: response.page_count,
      });
    } catch (err) {
      if (err instanceof ApiClientError) {
        setApiError({ message: err.message, statusCode: err.statusCode });
      } else {
        setApiError({
          message: err instanceof Error ? err.message : 'PDF upload failed.',
        });
      }
    } finally {
      setUploading(false);
    }
  };

  const clearSelection = () => {
    if (uploading) return;
    setSelectedFile(null);
    setValidationError(null);
    setApiError(null);
    setUploadProgress(0);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="max-w-3xl ml-0 mr-auto space-y-5">
      <div className="bg-white border border-slate-200/90 rounded-lg shadow-card overflow-hidden">
        {/* Production Admin Card Header */}
        <div className="px-5 py-3.5 border-b border-slate-200/80 flex items-center gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-900 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Books
          </Link>
          <span className="text-slate-300">|</span>
          <h2 className="text-[15px] font-semibold text-slate-900">New Book</h2>
        </div>

        <div className="p-5 space-y-5">
          {/* Production Profile / Context Fields matching 03-new-book.png */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1">
                Book Layout Profile
              </label>
              <div className="w-full px-3 py-2 text-xs text-slate-800 bg-bookabook-field border border-slate-200/70 rounded-md">
                Bookabook Opsi B (v1.3.4)
              </div>
            </div>

            <div>
              <label
                htmlFor="upload-reviewer-id"
                className="block text-[11px] font-medium text-slate-500 mb-1"
              >
                Operator / Reviewer ID
              </label>
              <input
                id="upload-reviewer-id"
                type="text"
                value={reviewerId}
                onChange={(e) => setReviewerId(e.target.value)}
                placeholder="operator_1"
                className="w-full px-3 py-2 text-xs text-slate-800 bg-bookabook-field border border-slate-200/70 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal focus:bg-white transition-colors"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1">
                Supported Sheet Classifications
              </label>
              <div className="w-full px-3 py-2 text-xs text-slate-700 bg-bookabook-field border border-slate-200/70 rounded-md">
                Cover Spread • 4-Up Imposition • Single Page
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-500 mb-1">
                Accepted Format &amp; Upload Limit
              </label>
              <div className="w-full px-3 py-2 text-xs text-slate-700 bg-bookabook-field border border-slate-200/70 rounded-md">
                Valid <span className="font-mono">.pdf (%PDF-)</span> • Max{' '}
                {formatBytes(MAX_UPLOAD_SIZE_BYTES)} (50 MiB)
              </div>
            </div>
          </div>

          {/* Compact Dashed Dropzone ("Book PDF" section matching 03-new-book.png) */}
          <div>
            <label className="block text-[11px] font-medium text-slate-500 mb-1.5">
              Book PDF File <span className="text-rose-500">*</span>
            </label>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (!uploading) setDragActive(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setDragActive(false);
              }}
              onDrop={handleDrop}
              className={`relative border border-dashed rounded-md px-5 py-7 text-center transition-colors ${
                dragActive
                  ? 'border-bookabook-teal bg-bookabook-tealSoft/30'
                  : 'border-slate-300 bg-bookabook-surface hover:border-slate-400'
              } ${uploading ? 'opacity-60 pointer-events-none' : ''}`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                aria-label="Choose PDF file"
                disabled={uploading}
                onChange={(e) => {
                  const file = e.target.files?.[0] ?? null;
                  void handleFileCandidate(file);
                }}
                className="hidden"
              />

              <div className="w-9 h-9 rounded-full bg-white border border-slate-200 flex items-center justify-center mx-auto mb-2.5 text-bookabook-teal">
                <FileUp className="w-4 h-4" />
              </div>

              <p className="text-xs font-medium text-slate-800">
                Drag and drop a book PDF here, or click to select
              </p>
              <p className="text-[11px] text-slate-500 mt-1">
                PDF dimensions are classified automatically in points (72 pt/in)
              </p>

              <button
                type="button"
                disabled={uploading}
                onClick={() => fileInputRef.current?.click()}
                className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 text-slate-700 rounded-md hover:bg-slate-50 transition-colors"
              >
                Browse Local PDF
              </button>
            </div>
          </div>

          {validating && (
            <div className="flex items-center gap-2 text-xs text-slate-600">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-bookabook-teal" />
              Validating PDF header and file size...
            </div>
          )}

          {validationError && (
            <ErrorAlert
              title="Client PDF Validation Failed"
              message={validationError}
              onDismiss={() => setValidationError(null)}
            />
          )}

          {apiError && (
            <ErrorAlert
              title="Upload Rejected by Backend"
              message={apiError.message}
              statusCode={apiError.statusCode}
              onDismiss={() => setApiError(null)}
            />
          )}

          {/* Selected File Summary */}
          {selectedFile && !uploadedDoc && (
            <div className="border border-slate-200 rounded-md p-3.5 bg-bookabook-field/70 space-y-2.5">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-8 h-8 rounded bg-white border border-slate-200 flex items-center justify-center shrink-0 text-bookabook-teal">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-slate-900 truncate">
                      {selectedFile.name}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      {formatBytes(selectedFile.size)} ({selectedFile.size.toLocaleString()} bytes) •{' '}
                      <span className="text-emerald-700 font-medium">PDF header verified</span>
                    </div>
                  </div>
                </div>

                {!uploading && (
                  <button
                    type="button"
                    onClick={clearSelection}
                    className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-white"
                    aria-label="Remove selected file"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {uploading && (
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-slate-600">
                    <span>Uploading PDF &amp; extracting page geometry...</span>
                    <span className="font-mono font-medium">{uploadProgress}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-bookabook-teal transition-all duration-150"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Action Footer Matching 03-new-book.png */}
          <div className="pt-3 border-t border-slate-200/80 flex items-center gap-2.5">
            <button
              type="button"
              disabled={!selectedFile || uploading || validating || Boolean(uploadedDoc)}
              onClick={() => void handleUpload()}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium bg-bookabook-teal text-white rounded-md hover:bg-bookabook-tealHover disabled:opacity-45 transition-colors"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <FileUp className="w-3.5 h-3.5" />
                  Upload &amp; Analyze PDF
                </>
              )}
            </button>

            <Link
              to="/"
              className="inline-flex items-center px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors"
            >
              Cancel
            </Link>
          </div>
        </div>
      </div>

      {/* Upload Success Summary */}
      {uploadedDoc && (
        <div className="bg-white border border-emerald-200 rounded-lg shadow-card p-5 space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  PDF Uploaded &amp; Registered Successfully
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  The backend extracted geometry metadata and assigned Document ID{' '}
                  <code className="font-mono font-semibold text-slate-800">
                    {uploadedDoc.document_id}
                  </code>
                  .
                </p>
              </div>
            </div>
            <StatusBadge status={uploadedDoc.status} size="sm" />
          </div>

          <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            <div className="bg-bookabook-field rounded-md p-2.5">
              <dt className="text-[11px] text-slate-500">Original Filename</dt>
              <dd className="font-medium text-slate-900 mt-0.5 break-all">
                {uploadedDoc.filename}
              </dd>
            </div>
            <div className="bg-bookabook-field rounded-md p-2.5">
              <dt className="text-[11px] text-slate-500">Document ID</dt>
              <dd className="font-mono font-medium text-slate-900 mt-0.5">
                {uploadedDoc.document_id}
              </dd>
            </div>
            <div className="bg-bookabook-field rounded-md p-2.5">
              <dt className="text-[11px] text-slate-500">Page Count &amp; Size</dt>
              <dd className="font-medium text-slate-900 mt-0.5">
                {uploadedDoc.page_count} sheets • {formatBytes(uploadedDoc.file_size_bytes)}
              </dd>
            </div>
            <div className="bg-bookabook-field rounded-md p-2.5">
              <dt className="text-[11px] text-slate-500">Uploaded At</dt>
              <dd className="font-medium text-slate-900 mt-0.5">
                {formatTimestamp(uploadedDoc.created_at)}
              </dd>
            </div>
          </dl>

          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={`/documents/${encodeURIComponent(uploadedDoc.document_id)}`}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-md bg-bookabook-teal text-white hover:bg-bookabook-tealHover transition-colors"
            >
              Open Document Detail
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
            <Link
              to={`/documents/${encodeURIComponent(uploadedDoc.document_id)}/preview`}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-md bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <Eye className="w-3.5 h-3.5" />
              Open Preview Workspace
            </Link>
            <Link
              to={`/documents/${encodeURIComponent(uploadedDoc.document_id)}/review`}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-md bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <ClipboardCheck className="w-3.5 h-3.5" />
              Open Review Workspace
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};
