import axios, { AxiosError, AxiosInstance } from 'axios';
import { CompressionFailureItem } from '@/types/api';

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
export const API_BASE_URL = rawBaseUrl.replace(/\/+$/, '');

// Matches backend Settings.MAX_UPLOAD_SIZE_BYTES (50 * 1024 * 1024 = 52428800 bytes)
export const MAX_UPLOAD_SIZE_BYTES =
  Number(import.meta.env.VITE_MAX_UPLOAD_SIZE_BYTES) || 50 * 1024 * 1024;

export interface FastAPIValidationItem {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

export interface FastAPIErrorBody {
  detail?: string | FastAPIValidationItem[];
  compression_status?: string;
  compression_failures?: CompressionFailureItem[];
}

export class ApiClientError extends Error {
  public readonly statusCode?: number;
  public readonly isNetworkError: boolean;
  public readonly detail?: string;
  public readonly compressionStatus?: string;
  public readonly compressionFailures?: CompressionFailureItem[];

  constructor(
    message: string,
    options?: {
      statusCode?: number;
      isNetworkError?: boolean;
      detail?: string;
      compressionStatus?: string;
      compressionFailures?: CompressionFailureItem[];
    }
  ) {
    super(message);
    this.name = 'ApiClientError';
    this.statusCode = options?.statusCode;
    this.isNetworkError = Boolean(options?.isNetworkError);
    this.detail = options?.detail;
    this.compressionStatus = options?.compressionStatus;
    this.compressionFailures = options?.compressionFailures;
  }
}

export function extractErrorMessage(error: unknown): ApiClientError {
  if (error instanceof ApiClientError) {
    return error;
  }

  if (axios.isAxiosError(error)) {
    const axiosErr = error as AxiosError<FastAPIErrorBody>;
    if (!axiosErr.response) {
      return new ApiClientError(
        `Cannot reach backend API at ${API_BASE_URL}. Ensure the FastAPI server is running.`,
        { isNetworkError: true }
      );
    }

    const status = axiosErr.response.status;
    const data = axiosErr.response.data;
    let detailMessage: string | undefined;

    if (data && typeof data === 'object' && 'detail' in data) {
      if (typeof data.detail === 'string') {
        detailMessage = data.detail;
      } else if (Array.isArray(data.detail)) {
        detailMessage = data.detail
          .map((item) => {
            const loc = Array.isArray(item.loc) ? item.loc.join('.') : '';
            return loc ? `${loc}: ${item.msg ?? 'Invalid value'}` : item.msg ?? 'Validation error';
          })
          .join('; ');
      }
    }

    const message =
      detailMessage ||
      axiosErr.message ||
      `HTTP ${status} error returned by backend API.`;

    return new ApiClientError(message, {
      statusCode: status,
      isNetworkError: false,
      detail: detailMessage,
      compressionStatus:
        data && typeof data === 'object' ? data.compression_status : undefined,
      compressionFailures:
        data && typeof data === 'object' && Array.isArray(data.compression_failures)
          ? data.compression_failures
          : undefined,
    });
  }

  if (error instanceof Error) {
    return new ApiClientError(error.message, { isNetworkError: false });
  }

  return new ApiClientError('An unexpected error occurred.', { isNetworkError: false });
}

export function resolveApiUrl(path: string): string {
  if (!path) return API_BASE_URL;
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120_000, // 120s generous timeout for up to 50 MiB PDF uploads & PNG compositing
  headers: {
    Accept: 'application/json',
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(extractErrorMessage(error))
);

