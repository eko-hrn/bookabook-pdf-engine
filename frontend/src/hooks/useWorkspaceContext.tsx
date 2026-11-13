import React, { createContext, useCallback, useContext, useState } from 'react';
import {
  clearWorkspaceState,
  loadWorkspaceState,
  saveWorkspaceState,
  TrackedDocumentRef,
  TrackedSessionRef,
  WorkspaceStorageState,
} from '@/utils/workspaceStore';

interface WorkspaceContextValue extends WorkspaceStorageState {
  setActiveDocumentId: (documentId: string | null) => void;
  setActiveSessionId: (sessionId: string | null) => void;
  setReviewerId: (reviewerId: string) => void;
  registerDocument: (doc: { document_id: string; filename: string; page_count?: number }) => void;
  registerSession: (session: {
    session_id: string;
    document_id?: string;
    source_filename: string;
  }) => void;
  getSessionIdForDocument: (documentId: string) => string | undefined;
  resetWorkspaceHistory: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<WorkspaceStorageState>(() => loadWorkspaceState());

  const updateState = useCallback(
    (updater: (prev: WorkspaceStorageState) => WorkspaceStorageState) => {
      setState((prev) => {
        const next = updater(prev);
        saveWorkspaceState(next);
        return next;
      });
    },
    []
  );

  const setActiveDocumentId = useCallback(
    (documentId: string | null) => {
      updateState((prev) => ({
        ...prev,
        activeDocumentId: documentId,
        activeSessionId: documentId
          ? prev.documentSessionMap[documentId] ?? prev.activeSessionId
          : prev.activeSessionId,
      }));
    },
    [updateState]
  );

  const setActiveSessionId = useCallback(
    (sessionId: string | null) => {
      updateState((prev) => ({
        ...prev,
        activeSessionId: sessionId,
      }));
    },
    [updateState]
  );

  const setReviewerId = useCallback(
    (reviewerId: string) => {
      updateState((prev) => ({
        ...prev,
        reviewerId: reviewerId,
      }));
    },
    [updateState]
  );

  const registerDocument = useCallback(
    (doc: { document_id: string; filename: string; page_count?: number }) => {
      updateState((prev) => {
        const filtered = prev.documents.filter((d) => d.document_id !== doc.document_id);
        const entry: TrackedDocumentRef = {
          document_id: doc.document_id,
          filename: doc.filename,
          page_count: doc.page_count,
          added_at: new Date().toISOString(),
        };
        return {
          ...prev,
          activeDocumentId: doc.document_id,
          documents: [entry, ...filtered].slice(0, 20),
        };
      });
    },
    [updateState]
  );

  const registerSession = useCallback(
    (session: { session_id: string; document_id?: string; source_filename: string }) => {
      updateState((prev) => {
        const filtered = prev.sessions.filter((s) => s.session_id !== session.session_id);
        const entry: TrackedSessionRef = {
          session_id: session.session_id,
          document_id: session.document_id,
          source_filename: session.source_filename,
          added_at: new Date().toISOString(),
        };
        const nextMap = { ...prev.documentSessionMap };
        if (session.document_id) {
          nextMap[session.document_id] = session.session_id;
        }
        return {
          ...prev,
          activeSessionId: session.session_id,
          activeDocumentId: session.document_id ?? prev.activeDocumentId,
          sessions: [entry, ...filtered].slice(0, 20),
          documentSessionMap: nextMap,
        };
      });
    },
    [updateState]
  );

  const getSessionIdForDocument = useCallback(
    (documentId: string) => state.documentSessionMap[documentId],
    [state.documentSessionMap]
  );

  const resetWorkspaceHistory = useCallback(() => {
    clearWorkspaceState();
    setState({
      activeDocumentId: null,
      activeSessionId: null,
      reviewerId: 'operator_1',
      documents: [],
      sessions: [],
      documentSessionMap: {},
    });
  }, []);

  return (
    <WorkspaceContext.Provider
      value={{
        ...state,
        setActiveDocumentId,
        setActiveSessionId,
        setReviewerId,
        registerDocument,
        registerSession,
        getSessionIdForDocument,
        resetWorkspaceHistory,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};

export function useWorkspaceContext(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    throw new Error('useWorkspaceContext must be used inside WorkspaceProvider');
  }
  return ctx;
}

