import { describe, expect, it } from 'vitest';
import { PagePreviewInfo } from '@/types/api';
import { buildBookSpreads, findSpreadIndexForSheet } from '@/utils/bookSpreads';
import { withOverlayQuery } from '@/api/previewsApi';

function makeBadge(status = 'CROP_READY') {
  return {
    status,
    badge_text: status,
    accessibility_label: status,
    stroke_color: '#10b981',
    fill_color: '#ecfdf5',
    pattern_type: 'solid',
  };
}

function make4UpSheet(pageNumber: number, startBookPage: number): PagePreviewInfo {
  return {
    page_number: pageNumber,
    pdf_page_index: pageNumber - 1,
    width_pt: 879.02,
    height_pt: 1247.34,
    orientation: 'PORTRAIT',
    layout_type: 'IMPOSITION_4UP',
    crop_readiness: 'CROP_READY',
    expected_page_yield: 4,
    preview_image_url: `/api/documents/doc_1/pages/${pageNumber}/preview.png`,
    status_badge: makeBadge('CROP_READY'),
    warnings: [],
    unresolved_discrepancies: [],
    regions: [1, 2, 3, 4].map((q) => {
      const pageNum = startBookPage + (q - 1);
      const id = `PAGE-${String(pageNum).padStart(2, '0')}`;
      return {
        region_id: id,
        quadrant: q,
        width_pt: 425.52,
        height_pt: 609.12,
        target_width_px: 1773,
        target_height_px: 2538,
        blank_page_status: 'CONTENT_PRESENT',
        preview_image_url: `/api/documents/doc_1/pages/${pageNumber}/regions/${id}/preview.png`,
      };
    }),
  };
}

describe('Book Spread Pairing & Overlay Query Helpers', () => {
  it('appends or replaces overlay query param without duplication', () => {
    expect(withOverlayQuery('/api/documents/doc_1/pages/1/preview.png', true)).toBe(
      '/api/documents/doc_1/pages/1/preview.png?overlay=true'
    );
    expect(withOverlayQuery('/api/documents/doc_1/pages/1/preview.png?overlay=true', false)).toBe(
      '/api/documents/doc_1/pages/1/preview.png?overlay=false'
    );
  });

  it('pairs Cover Spread standalone and 4-Up Q1+Q2, Q3+Q4 into consecutive interior spreads', () => {
    const coverSheet: PagePreviewInfo = {
      page_number: 1,
      pdf_page_index: 0,
      width_pt: 893.79,
      height_pt: 609.12,
      orientation: 'LANDSCAPE',
      layout_type: 'COVER_SPREAD',
      crop_readiness: 'MANUAL_REVIEW_REQUIRED',
      expected_page_yield: 2,
      preview_image_url: '/api/documents/doc_1/pages/1/preview.png',
      status_badge: makeBadge('MANUAL_REVIEW_REQUIRED'),
      warnings: ['Cover auto-crop disabled'],
      unresolved_discrepancies: [],
      regions: [
        {
          region_id: 'BACKCOVER',
          quadrant: null,
          width_pt: 425.61,
          height_pt: 609.12,
          target_width_px: 591,
          target_height_px: 846,
          blank_page_status: 'CONTENT_PRESENT',
          preview_image_url: '/api/documents/doc_1/pages/1/regions/BACKCOVER/preview.png',
        },
        {
          region_id: 'COVER',
          quadrant: null,
          width_pt: 425.61,
          height_pt: 609.12,
          target_width_px: 591,
          target_height_px: 846,
          blank_page_status: 'CONTENT_PRESENT',
          preview_image_url: '/api/documents/doc_1/pages/1/regions/COVER/preview.png',
        },
      ],
    };

    const sheet2 = make4UpSheet(2, 1);
    const sheet3 = make4UpSheet(3, 5);

    const { spreads, thumbnails } = buildBookSpreads([coverSheet, sheet2, sheet3]);

    // Total spreads: 1 cover + 2 from sheet2 + 2 from sheet3 = 5
    expect(spreads).toHaveLength(5);

    // 1. Cover Spread is standalone and never paired with Sheet 2
    expect(spreads[0].kind).toBe('COVER_SPREAD');
    expect(spreads[0].title).toBe('COVER SPREAD');
    expect(spreads[0].sheetPageNumber).toBe(1);

    // 2. Sheet 2 -> Q1+Q2 (PAGE-01 + PAGE-02) then Q3+Q4 (PAGE-03 + PAGE-04)
    expect(spreads[1].kind).toBe('BOOK_SPREAD');
    expect(spreads[1].title).toBe('PAGE-01 + PAGE-02');
    expect(spreads[1].leftSlot?.quadrant).toBe(1);
    expect(spreads[1].rightSlot?.quadrant).toBe(2);

    expect(spreads[2].kind).toBe('BOOK_SPREAD');
    expect(spreads[2].title).toBe('PAGE-03 + PAGE-04');
    expect(spreads[2].leftSlot?.quadrant).toBe(3);
    expect(spreads[2].rightSlot?.quadrant).toBe(4);

    // 3. Sheet 3 -> Q1+Q2 (PAGE-05 + PAGE-06) then Q3+Q4 (PAGE-07 + PAGE-08)
    expect(spreads[3].title).toBe('PAGE-05 + PAGE-06');
    expect(spreads[4].title).toBe('PAGE-07 + PAGE-08');

    // Thumbnails: COVER + PAGE-01..PAGE-08
    expect(thumbnails.map((t) => t.label)).toEqual([
      'COVER',
      'PAGE-01',
      'PAGE-02',
      'PAGE-03',
      'PAGE-04',
      'PAGE-05',
      'PAGE-06',
      'PAGE-07',
      'PAGE-08',
    ]);
    expect(thumbnails[3].spreadIndex).toBe(2); // PAGE-03 maps to spread 2 (PAGE-03 + PAGE-04)
    expect(findSpreadIndexForSheet(spreads, 3)).toBe(3);
  });

  it('displays SINGLE_PAGE and UNKNOWN_LAYOUT pages individually when logical spread order is unverified', () => {
    const single1: PagePreviewInfo = {
      page_number: 1,
      pdf_page_index: 0,
      width_pt: 425.52,
      height_pt: 609.12,
      orientation: 'PORTRAIT',
      layout_type: 'SINGLE_PAGE',
      crop_readiness: 'CROP_READY',
      expected_page_yield: 1,
      preview_image_url: '/api/documents/doc_single/pages/1/preview.png',
      status_badge: makeBadge('CROP_READY'),
      warnings: [],
      unresolved_discrepancies: [],
      regions: [
        {
          region_id: 'PAGE-01',
          quadrant: null,
          width_pt: 425.52,
          height_pt: 609.12,
          target_width_px: 1773,
          target_height_px: 2538,
          blank_page_status: 'CONTENT_PRESENT',
          preview_image_url: '/api/documents/doc_single/pages/1/regions/PAGE-01/preview.png',
        },
      ],
    };

    const unknown2: PagePreviewInfo = {
      page_number: 2,
      pdf_page_index: 1,
      width_pt: 700,
      height_pt: 700,
      orientation: 'SQUARE',
      layout_type: null,
      crop_readiness: 'NOT_APPLICABLE',
      expected_page_yield: 0,
      preview_image_url: '/api/documents/doc_single/pages/2/preview.png',
      status_badge: makeBadge('NOT_APPLICABLE'),
      warnings: ['Unrecognized sheet geometry'],
      unresolved_discrepancies: [],
      regions: [],
    };

    const { spreads } = buildBookSpreads([single1, unknown2]);
    expect(spreads).toHaveLength(2);
    expect(spreads[0].kind).toBe('SINGLE_PAGE');
    expect(spreads[0].statusNote).toContain('displayed individually');
    expect(spreads[1].kind).toBe('UNKNOWN_LAYOUT');
    expect(spreads[1].statusNote).toContain('auto-crop disabled');
  });
});

