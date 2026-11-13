import React from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { WorkspaceProvider } from '@/hooks/useWorkspaceContext';
import { AppLayout } from '@/layouts/AppLayout';
import { DashboardPage } from '@/pages/DashboardPage';
import { BooksCatalogPage } from '@/pages/BooksCatalogPage';
import { BookViewerPage } from '@/pages/BookViewerPage';
import { CreateBookPage } from '@/pages/CreateBookPage';
import { DocumentDetailPage } from '@/pages/DocumentDetailPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { PreviewWorkspacePage } from '@/pages/PreviewWorkspacePage';
import { ReviewWorkspacePage } from '@/pages/ReviewWorkspacePage';
import { UploadPage } from '@/pages/UploadPage';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/books" element={<BooksCatalogPage />} />
        <Route path="/books/new" element={<CreateBookPage />} />
        <Route path="/create-book" element={<CreateBookPage />} />
        <Route path="/books/:bookId" element={<BookViewerPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/documents" element={<DocumentDetailPage />} />
        <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
        <Route path="/preview" element={<PreviewWorkspacePage />} />
        <Route path="/documents/:documentId/preview" element={<PreviewWorkspacePage />} />
        <Route path="/review" element={<ReviewWorkspacePage />} />
        <Route path="/documents/:documentId/review" element={<ReviewWorkspacePage />} />
        <Route path="/reviews/:sessionId" element={<ReviewWorkspacePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
};

export const App: React.FC = () => {
  return (
    <WorkspaceProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </WorkspaceProvider>
  );
};

export default App;

