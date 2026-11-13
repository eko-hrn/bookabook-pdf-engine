import { MAX_UPLOAD_SIZE_BYTES } from '@/api/client';

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), units.length - 1);
  const value = bytes / Math.pow(k, i);
  return `${value.toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
}

export function formatTimestamp(isoString: string | null | undefined): string {
  if (!isoString) return '—';
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date);
}

export function formatUtcIsoShort(isoString: string | null | undefined): string {
  if (!isoString) return '—';
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return `${date.toISOString().replace('T', ' ').slice(0, 19)} UTC`;
}

export function formatLayoutLabel(layoutType: string | null | undefined): string {
  switch (layoutType) {
    case 'COVER_SPREAD':
      return 'Cover Spread';
    case 'IMPOSITION_4UP':
      return '4-Up Imposition';
    case 'SINGLE_PAGE':
      return 'Single Page';
    default:
      return 'Unknown Layout';
  }
}

export function formatDecisionLabel(decision: string | null | undefined): string {
  switch (decision) {
    case 'APPROVED':
      return 'Approved';
    case 'REJECTED':
      return 'Rejected';
    case 'NEEDS_REVISION':
      return 'Needs Revision';
    case 'PENDING':
    default:
      return 'Pending';
  }
}

export interface ClientPdfValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Validate uploaded PDF file client-side against backend rules:
 * - Non-empty (> 0 bytes)
 * - .pdf file extension
 * - Within configured MAX_UPLOAD_SIZE_BYTES (50 MiB = 52,428,800 bytes)
 * - Contains %PDF- magic bytes within initial 1024 bytes
 */
export async function validatePdfFile(file: File): Promise<ClientPdfValidationResult> {
  const lowerName = file.name.toLowerCase();
  if (!lowerName.endsWith('.pdf')) {
    return {
      valid: false,
      error: `Invalid file type for "${file.name}". Only .pdf documents are accepted.`,
    };
  }

  if (file.size === 0) {
    return {
      valid: false,
      error: 'Selected file is empty (0 bytes). Please choose a valid PDF document.',
    };
  }

  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return {
      valid: false,
      error: `File size (${formatBytes(file.size)}) exceeds the maximum backend upload limit of ${formatBytes(MAX_UPLOAD_SIZE_BYTES)}.`,
    };
  }

  try {
    const headerSlice = file.slice(0, 1024);
    const buffer =
      typeof headerSlice.arrayBuffer === 'function'
        ? await headerSlice.arrayBuffer()
        : await new Promise<ArrayBuffer>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              if (reader.result instanceof ArrayBuffer) {
                resolve(reader.result);
              } else {
                reject(new Error('Expected ArrayBuffer result'));
              }
            };
            reader.onerror = () => reject(reader.error ?? new Error('FileReader failed'));
            reader.readAsArrayBuffer(headerSlice);
          });
    const bytes = new Uint8Array(buffer);
    const ascii = new TextDecoder('latin1').decode(bytes);
    if (!ascii.includes('%PDF-')) {
      return {
        valid: false,
        error: 'Invalid PDF format: file is missing the required %PDF- header signature.',
      };
    }
  } catch {
    // If File slicing/reading is unsupported in a restricted environment, defer to backend validation
  }

  return { valid: true };
}

