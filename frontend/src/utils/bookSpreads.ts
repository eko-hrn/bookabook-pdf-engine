import { PagePreviewInfo, PreviewRegionInfo } from '@/types/api';

export type BookSpreadKind =
  | 'COVER_SPREAD'
  | 'BOOK_SPREAD'
  | 'SINGLE_PAGE'
  | 'UNKNOWN_LAYOUT';

export interface SpreadSlot {
  id: string;
  label: string;
  quadrant?: number | null;
  imageKey: string;
  apiPath: string;
  widthPt: number;
  heightPt: number;
  targetWidthPx?: number;
  targetHeightPx?: number;
  isBlank?: boolean;
}

export interface BookSpreadItem {
  id: string;
  index: number;
  kind: BookSpreadKind;
  title: string;
  shortLabel: string;
  subtitle: string;
  sheetPageNumber: number;
  sheetPage: PagePreviewInfo;
  leftSlot?: SpreadSlot;
  rightSlot?: SpreadSlot;
  singleSlot?: SpreadSlot;
  statusNote?: string;
}

export interface BookThumbnailItem {
  id: string;
  label: string;
  subLabel: string;
  spreadIndex: number;
  sheetPageNumber: number;
  imageKey: string;
  apiPath: string;
  widthPt: number;
  heightPt: number;
  quadrant?: number | null;
  cropReadiness: string;
  isCover: boolean;
}

export interface BookSpreadCollection {
  spreads: BookSpreadItem[];
  thumbnails: BookThumbnailItem[];
}

export function getSheetImageKey(pageNumber: number): string {
  return `sheet:${pageNumber}`;
}

export function getRegionImageKey(pageNumber: number, regionId: string): string {
  return `region:${pageNumber}:${regionId}`;
}

function makeRegionSlot(page: PagePreviewInfo, region: PreviewRegionInfo): SpreadSlot {
  return {
    id: `${page.page_number}:${region.region_id}`,
    label: region.quadrant ? `${region.region_id} (Q${region.quadrant})` : region.region_id,
    quadrant: region.quadrant,
    imageKey: getRegionImageKey(page.page_number, region.region_id),
    apiPath: region.preview_image_url,
    widthPt: region.width_pt,
    heightPt: region.height_pt,
    targetWidthPx: region.target_width_px,
    targetHeightPx: region.target_height_px,
    isBlank: region.blank_page_status === 'BLANK_DETECTED',
  };
}

function makeSheetSlot(page: PagePreviewInfo, label: string): SpreadSlot {
  return {
    id: `sheet-${page.page_number}`,
    label,
    quadrant: null,
    imageKey: getSheetImageKey(page.page_number),
    apiPath: page.preview_image_url,
    widthPt: page.width_pt,
    heightPt: page.height_pt,
  };
}

/**
 * Construct logical book spreads and bottom strip thumbnails from backend PagePreviewInfo list.
 *
 * Verified pairing rules (Layout_Classifier_Specification_v1.3.4.md §8):
 * - COVER_SPREAD (Sheet 1): rendered standalone (never paired with Sheet 2).
 * - IMPOSITION_4UP: Q1+Q2 forms the first interior spread, Q3+Q4 forms the second interior spread.
 * - SINGLE_PAGE / UNKNOWN_LAYOUT: displayed individually with clear status indicators when logical spread
 *   order cannot be safely inferred.
 */
export function buildBookSpreads(pages: PagePreviewInfo[]): BookSpreadCollection {
  const sortedPages = [...pages].sort((a, b) => a.page_number - b.page_number);
  const spreads: BookSpreadItem[] = [];
  const thumbnails: BookThumbnailItem[] = [];

  for (const page of sortedPages) {
    const regions = page.regions ?? [];

    if (page.layout_type === 'COVER_SPREAD') {
      const spreadIdx = spreads.length;
      const sheetKey = getSheetImageKey(page.page_number);
      spreads.push({
        id: `cover-s${page.page_number}`,
        index: spreadIdx,
        kind: 'COVER_SPREAD',
        title: 'COVER SPREAD',
        shortLabel: 'COVER',
        subtitle: `Sheet ${page.page_number} • Backcover + Protected Spine + Front Cover`,
        sheetPageNumber: page.page_number,
        sheetPage: page,
        singleSlot: makeSheetSlot(page, 'Cover Spread'),
        statusNote: 'Cover Spread displayed independently (protected spine zone intact).',
      });
      thumbnails.push({
        id: `thumb-cover-s${page.page_number}`,
        label: 'COVER',
        subLabel: `Sheet ${page.page_number}`,
        spreadIndex: spreadIdx,
        sheetPageNumber: page.page_number,
        imageKey: sheetKey,
        apiPath: page.preview_image_url,
        widthPt: page.width_pt,
        heightPt: page.height_pt,
        quadrant: null,
        cropReadiness: page.crop_readiness,
        isCover: true,
      });
      continue;
    }

    if (page.layout_type === 'IMPOSITION_4UP' && regions.length > 0) {
      const q1 = regions.find((r) => r.quadrant === 1) ?? regions[0];
      const q2 = regions.find((r) => r.quadrant === 2) ?? regions[1];
      const q3 = regions.find((r) => r.quadrant === 3) ?? regions[2];
      const q4 = regions.find((r) => r.quadrant === 4) ?? regions[3];

      const pairs: Array<{
        left?: PreviewRegionInfo;
        right?: PreviewRegionInfo;
        qLabel: string;
      }> = [
        { left: q1, right: q2, qLabel: 'Q1 + Q2' },
        { left: q3, right: q4, qLabel: 'Q3 + Q4' },
      ];

      for (const pair of pairs) {
        if (!pair.left && !pair.right) continue;
        const spreadIdx = spreads.length;
        const leftSlot = pair.left ? makeRegionSlot(page, pair.left) : undefined;
        const rightSlot = pair.right ? makeRegionSlot(page, pair.right) : undefined;

        const pairTitle =
          pair.left && pair.right
            ? `${pair.left.region_id} + ${pair.right.region_id}`
            : (pair.left ?? pair.right)!.region_id;

        if (leftSlot && rightSlot) {
          spreads.push({
            id: `spread-s${page.page_number}-${pair.qLabel.replace(/\s+/g, '')}`,
            index: spreadIdx,
            kind: 'BOOK_SPREAD',
            title: pairTitle,
            shortLabel: pairTitle,
            subtitle: `Sheet ${page.page_number} • ${pair.qLabel}`,
            sheetPageNumber: page.page_number,
            sheetPage: page,
            leftSlot,
            rightSlot,
          });
        } else {
          spreads.push({
            id: `spread-s${page.page_number}-${pair.qLabel.replace(/\s+/g, '')}`,
            index: spreadIdx,
            kind: 'SINGLE_PAGE',
            title: pairTitle,
            shortLabel: pairTitle,
            subtitle: `Sheet ${page.page_number} • ${pair.qLabel}`,
            sheetPageNumber: page.page_number,
            sheetPage: page,
            singleSlot: leftSlot ?? rightSlot,
          });
        }

        for (const reg of [pair.left, pair.right]) {
          if (!reg) continue;
          thumbnails.push({
            id: `thumb-s${page.page_number}-${reg.region_id}`,
            label: reg.region_id,
            subLabel: reg.quadrant ? `Q${reg.quadrant} • S${page.page_number}` : `S${page.page_number}`,
            spreadIndex: spreadIdx,
            sheetPageNumber: page.page_number,
            imageKey: getRegionImageKey(page.page_number, reg.region_id),
            apiPath: reg.preview_image_url,
            widthPt: reg.width_pt,
            heightPt: reg.height_pt,
            quadrant: reg.quadrant,
            cropReadiness: page.crop_readiness,
            isCover: false,
          });
        }
      }
      continue;
    }

    // SINGLE_PAGE, UNKNOWN_LAYOUT, or mocked page without region payloads: display individually
    const spreadIdx = spreads.length;
    const primaryRegion = regions[0];
    const isUnknown = !page.layout_type || page.crop_readiness === 'NOT_APPLICABLE';
    const kind: BookSpreadKind = isUnknown ? 'UNKNOWN_LAYOUT' : 'SINGLE_PAGE';
    const label = primaryRegion ? primaryRegion.region_id : `SHEET-${page.page_number}`;
    const slot = primaryRegion
      ? makeRegionSlot(page, primaryRegion)
      : makeSheetSlot(page, label);

    spreads.push({
      id: `single-s${page.page_number}`,
      index: spreadIdx,
      kind,
      title: label,
      shortLabel: label,
      subtitle: isUnknown
        ? `Sheet ${page.page_number} • Unknown Layout`
        : `Sheet ${page.page_number} • Single Page`,
      sheetPageNumber: page.page_number,
      sheetPage: page,
      singleSlot: slot,
      statusNote: isUnknown
        ? 'Unrecognized geometry — auto-crop disabled and displayed individually.'
        : 'Single Page sheet — displayed individually because logical spread pairing is unverified.',
    });

    thumbnails.push({
      id: `thumb-single-s${page.page_number}`,
      label,
      subLabel: `Sheet ${page.page_number}`,
      spreadIndex: spreadIdx,
      sheetPageNumber: page.page_number,
      imageKey: slot.imageKey,
      apiPath: slot.apiPath,
      widthPt: slot.widthPt,
      heightPt: slot.heightPt,
      quadrant: primaryRegion?.quadrant ?? null,
      cropReadiness: page.crop_readiness,
      isCover: false,
    });
  }

  return { spreads, thumbnails };
}

export function findSpreadIndexForSheet(
  spreads: BookSpreadItem[],
  sheetPageNumber: number
): number {
  const idx = spreads.findIndex((s) => s.sheetPageNumber === sheetPageNumber);
  return idx >= 0 ? idx : 0;
}

