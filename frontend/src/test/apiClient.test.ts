import { AxiosError } from 'axios';
import { describe, expect, it } from 'vitest';
import {
  ApiClientError,
  API_BASE_URL,
  extractErrorMessage,
  MAX_UPLOAD_SIZE_BYTES,
  resolveApiUrl,
} from '@/api/client';
import { formatBytes, formatLayoutLabel, validatePdfFile } from '@/utils/formatters';

function makeBlobFile(
  parts: BlobPart[],
  name: string,
  type = 'application/pdf'
): File {
  const file = new File(parts, name, { type });
  if (typeof file.arrayBuffer !== 'function') {
    Object.defineProperty(file, 'arrayBuffer', {
      value: async () => {
        const text = typeof parts[0] === 'string' ? parts[0] : '';
        return new TextEncoder().encode(text).buffer;
      },
    });
  }
  return file;
}

describe('API Client & PDF Validation Utilities', () => {
  it('uses exact 50 MiB upload limit matching FastAPI backend (52428800 bytes)', () => {
    expect(MAX_UPLOAD_SIZE_BYTES).toBe(52_428_800);
    expect(formatBytes(50_430_718)).toBe('48.09 MB');
  });

  it('resolves relative backend endpoints accurately', () => {
    expect(resolveApiUrl('/api/documents/doc_1/pages/1/preview.png')).toBe(
      `${API_BASE_URL}/api/documents/doc_1/pages/1/preview.png`
    );
    expect(resolveApiUrl('api/health')).toBe(`${API_BASE_URL}/api/health`);
    expect(resolveApiUrl('https://example.com/preview.png')).toBe(
      'https://example.com/preview.png'
    );
  });

  it('normalizes FastAPI string detail, Pydantic error list, and network failures', () => {
    const strErr = new AxiosError('Bad Request', '400', undefined, undefined, {
      status: 400,
      statusText: 'Bad Request',
      headers: {},
      config: {} as never,
      data: { detail: 'REJECTED page must transition to NEEDS_REVISION before approval.' },
    });
    const parsedStr = extractErrorMessage(strErr);
    expect(parsedStr).toBeInstanceOf(ApiClientError);
    expect(parsedStr.statusCode).toBe(400);
    expect(parsedStr.message).toContain('NEEDS_REVISION');

    const validationErr = new AxiosError('Unprocessable Entity', '422', undefined, undefined, {
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: {},
      config: {} as never,
      data: {
        detail: [
          { loc: ['body', 'reviewer_id'], msg: 'String should have at least 1 character' },
        ],
      },
    });
    const parsedVal = extractErrorMessage(validationErr);
    expect(parsedVal.statusCode).toBe(422);
    expect(parsedVal.message).toContain('body.reviewer_id');

    const netErr = new AxiosError('Network Error');
    const parsedNet = extractErrorMessage(netErr);
    expect(parsedNet.isNetworkError).toBe(true);
    expect(parsedNet.message).toContain('Cannot reach backend API');

    const compErr = new AxiosError('Unprocessable Entity', '422', undefined, undefined, {
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: {},
      config: {} as never,
      data: {
        detail: 'COVER.jpg exceeds 512,000 bytes at minimum quality.',
        compression_status: 'FAILED',
        compression_failures: [
          {
            filename: 'COVER.jpg',
            page_key: 'COVER',
            page_kind: 'COVER',
            actual_size_bytes: 600_000,
            max_allowed_bytes: 512_000,
            min_quality_threshold: 55,
            quality_attempted: 55,
            reason: 'Exceeds 512,000 bytes at minimum quality q=55.',
          },
        ],
      },
    });
    const parsedComp = extractErrorMessage(compErr);
    expect(parsedComp.compressionStatus).toBe('FAILED');
    expect(parsedComp.compressionFailures).toHaveLength(1);
    expect(parsedComp.compressionFailures?.[0].filename).toBe('COVER.jpg');
  });

  it('rejects non-pdf extension, empty file, oversized file, and fake PDF header', async () => {
    const wrongExt = makeBlobFile(['%PDF-1.4\n'], 'notes.txt', 'text/plain');
    expect((await validatePdfFile(wrongExt)).valid).toBe(false);

    const emptyPdf = makeBlobFile([], 'empty.pdf');
    expect((await validatePdfFile(emptyPdf)).valid).toBe(false);

    const fakePdf = makeBlobFile(['<html>not a pdf</html>'], 'fake.pdf');
    const fakeRes = await validatePdfFile(fakePdf);
    expect(fakeRes.valid).toBe(false);
    expect(fakeRes.error).toContain('%PDF-');

    const hugeFile = {
      name: 'oversized.pdf',
      size: MAX_UPLOAD_SIZE_BYTES + 1,
      slice: () => new Blob(['%PDF-1.7']),
    } as unknown as File;
    const hugeRes = await validatePdfFile(hugeFile);
    expect(hugeRes.valid).toBe(false);
    expect(hugeRes.error).toContain('exceeds the maximum backend upload limit');

    const validPdf = makeBlobFile(['%PDF-1.7\n1 0 obj\n<<>>\nendobj\n'], 'book.pdf');
    expect(await validatePdfFile(validPdf)).toEqual({ valid: true });
  });

  it('formats layout labels strictly according to backend enums', () => {
    expect(formatLayoutLabel('COVER_SPREAD')).toBe('Cover Spread');
    expect(formatLayoutLabel('IMPOSITION_4UP')).toBe('4-Up Imposition');
    expect(formatLayoutLabel('SINGLE_PAGE')).toBe('Single Page');
    expect(formatLayoutLabel(null)).toBe('Unknown Layout');
  });
});

