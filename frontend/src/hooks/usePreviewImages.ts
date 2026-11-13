import { useCallback, useEffect, useRef, useState } from 'react';
import { previewsApi } from '@/api';
import { PagePreviewInfo } from '@/types/api';
import { BookThumbnailItem, getSheetImageKey } from '@/utils/bookSpreads';

export interface PreviewImageEntry {
  objectUrl?: string;
  loading: boolean;
  error?: string;
}

function makeCacheKey(itemKey: string, overlay: boolean): string {
  return `${itemKey}::overlay=${overlay ? '1' : '0'}`;
}

export function usePreviewImages(
  documentId: string | undefined,
  pages: PagePreviewInfo[],
  overlay = true,
  thumbnails: BookThumbnailItem[] = []
) {
  const [entries, setEntries] = useState<Record<string, PreviewImageEntry>>({});
  const objectUrlsRef = useRef<Record<string, string>>({});
  const inflightRef = useRef<Set<string>>(new Set());
  const docIdRef = useRef<string | undefined>(documentId);

  const revokeAll = useCallback(() => {
    Object.values(objectUrlsRef.current).forEach((url) => {
      URL.revokeObjectURL(url);
    });
    objectUrlsRef.current = {};
    inflightRef.current.clear();
  }, []);

  useEffect(() => {
    docIdRef.current = documentId;
    setEntries({});
    revokeAll();
    return () => revokeAll();
  }, [documentId, revokeAll]);

  const loadImage = useCallback(
    async (
      itemKey: string,
      apiPath?: string,
      withOverlay = overlay,
      fallbackPageNumber?: number
    ) => {
      const targetDocId = documentId;
      if (!targetDocId) return;
      const cacheKey = makeCacheKey(itemKey, withOverlay);

      if (objectUrlsRef.current[cacheKey] || inflightRef.current.has(cacheKey)) {
        return;
      }

      inflightRef.current.add(cacheKey);
      setEntries((prev) => ({
        ...prev,
        [cacheKey]: { ...prev[cacheKey], loading: true, error: undefined },
      }));

      try {
        const blob = apiPath
          ? await previewsApi.fetchPreviewPngByPath(apiPath, withOverlay)
          : fallbackPageNumber !== undefined
            ? await previewsApi.fetchPagePreviewPng(
                targetDocId,
                fallbackPageNumber,
                withOverlay
              )
            : await Promise.reject(new Error('Preview image path is unavailable.'));

        const objectUrl = URL.createObjectURL(blob);

        if (docIdRef.current !== targetDocId) {
          URL.revokeObjectURL(objectUrl);
          return;
        }

        objectUrlsRef.current[cacheKey] = objectUrl;
        setEntries((prev) => ({
          ...prev,
          [cacheKey]: { objectUrl, loading: false, error: undefined },
        }));
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to load preview image.';
        if (docIdRef.current === targetDocId) {
          setEntries((prev) => ({
            ...prev,
            [cacheKey]: { loading: false, error: msg },
          }));
        }
      } finally {
        inflightRef.current.delete(cacheKey);
      }
    },
    [documentId, overlay]
  );

  const reloadImage = useCallback(
    async (
      itemKey: string,
      apiPath?: string,
      withOverlay = overlay,
      fallbackPageNumber?: number
    ) => {
      const cacheKey = makeCacheKey(itemKey, withOverlay);
      const existing = objectUrlsRef.current[cacheKey];
      if (existing) {
        URL.revokeObjectURL(existing);
        delete objectUrlsRef.current[cacheKey];
      }
      inflightRef.current.delete(cacheKey);
      await loadImage(itemKey, apiPath, withOverlay, fallbackPageNumber);
    },
    [loadImage, overlay]
  );

  const getImageEntry = useCallback(
    (itemKey: string, withOverlay = overlay): PreviewImageEntry | undefined => {
      return entries[makeCacheKey(itemKey, withOverlay)];
    },
    [entries, overlay]
  );

  // Clean sequential background preload: prioritize book thumbnails (clean artwork) and sheets
  useEffect(() => {
    if (!documentId || (pages.length === 0 && thumbnails.length === 0)) return;
    let cancelled = false;

    const queue: Array<{ itemKey: string; apiPath: string; withOverlay: boolean }> = [];
    for (const thumb of thumbnails) {
      queue.push({ itemKey: thumb.imageKey, apiPath: thumb.apiPath, withOverlay: false });
    }
    for (const page of pages) {
      queue.push({
        itemKey: getSheetImageKey(page.page_number),
        apiPath: page.preview_image_url,
        withOverlay: overlay,
      });
    }

    const runPreload = async () => {
      for (const item of queue) {
        if (cancelled) break;
        const cacheKey = makeCacheKey(item.itemKey, item.withOverlay);
        if (!objectUrlsRef.current[cacheKey]) {
          await loadImage(item.itemKey, item.apiPath, item.withOverlay);
        }
      }
    };

    void runPreload();
    return () => {
      cancelled = true;
    };
  }, [documentId, pages, thumbnails, overlay, loadImage]);

  // Backward-compatible accessors for existing single-page callers
  const loadPageImage = useCallback(
    (pageNumber: number, customPath?: string, withOverlay = overlay) => {
      return loadImage(
        getSheetImageKey(pageNumber),
        customPath,
        withOverlay,
        pageNumber
      );
    },
    [loadImage, overlay]
  );

  const reloadPageImage = useCallback(
    (pageNumber: number, customPath?: string, withOverlay = overlay) => {
      return reloadImage(
        getSheetImageKey(pageNumber),
        customPath,
        withOverlay,
        pageNumber
      );
    },
    [reloadImage, overlay]
  );

  const sheetImagesByPage: Record<number, PreviewImageEntry> = {};
  for (const page of pages) {
    const entry = getImageEntry(getSheetImageKey(page.page_number), overlay);
    if (entry) {
      sheetImagesByPage[page.page_number] = entry;
    }
  }

  return {
    getImageEntry,
    loadImage,
    reloadImage,
    // Legacy aliases preserved for compatibility
    images: sheetImagesByPage,
    loadPageImage,
    reloadPageImage,
  };
}
