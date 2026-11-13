export interface TrackedDocumentRef {
  document_id: string;
  filename: string;
  page_count?: number;
  added_at: string;
}

export interface TrackedSessionRef {
  session_id: string;
  document_id?: string;
  source_filename: string;
  added_at: string;
}

export interface WorkspaceStorageState {
  activeDocumentId: string | null;
  activeSessionId: string | null;
  reviewerId: string;
  documents: TrackedDocumentRef[];
  sessions: TrackedSessionRef[];
  documentSessionMap: Record<string, string>;
}

const STORAGE_KEY = 'bookabook_operator_workspace_v1';

const DEFAULT_STATE: WorkspaceStorageState = {
  activeDocumentId: null,
  activeSessionId: null,
  reviewerId: 'operator_1',
  documents: [],
  sessions: [],
  documentSessionMap: {},
};

export function loadWorkspaceState(): WorkspaceStorageState {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_STATE };
    const parsed = JSON.parse(raw) as Partial<WorkspaceStorageState>;
    return {
      activeDocumentId: typeof parsed.activeDocumentId === 'string' ? parsed.activeDocumentId : null,
      activeSessionId: typeof parsed.activeSessionId === 'string' ? parsed.activeSessionId : null,
      reviewerId:
        typeof parsed.reviewerId === 'string' && parsed.reviewerId.trim()
          ? parsed.reviewerId
          : 'operator_1',
      documents: Array.isArray(parsed.documents) ? parsed.documents : [],
      sessions: Array.isArray(parsed.sessions) ? parsed.sessions : [],
      documentSessionMap:
        parsed.documentSessionMap && typeof parsed.documentSessionMap === 'object'
          ? parsed.documentSessionMap
          : {},
    };
  } catch {
    return { ...DEFAULT_STATE };
  }
}

export function saveWorkspaceState(state: WorkspaceStorageState): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore storage quota or sandbox restrictions
  }
}

export function clearWorkspaceState(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore
  }
}

