import React, { useCallback, useEffect, useState } from 'react';
import { BookOpen, Calendar, Plus, RefreshCw, User } from 'lucide-react';
import { Link } from 'react-router-dom';
import { booksApi, extractErrorMessage } from '@/api';
import { EmptyState, ErrorAlert, LoadingState } from '@/components/StateNotice';
import { BookSummary } from '@/types/api';

export const BooksCatalogPage: React.FC = () => {
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCatalog = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await booksApi.listBooks();
      setBooks(data.books);
    } catch (err) {
      setError(extractErrorMessage(err).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchCatalog();
  }, [fetchCatalog]);

  return (
    <div className="max-w-6xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Books Showcase</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Published Bookabook editions saved from cropped 300 DPI JPG outputs.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void fetchCatalog()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white border border-slate-200 text-slate-700 rounded-md hover:bg-slate-50"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
          <Link
            to="/books/new"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-bookabook-teal text-white rounded-md hover:bg-bookabook-tealHover"
          >
            <Plus className="w-3.5 h-3.5" />
            Create Book
          </Link>
        </div>
      </div>

      {loading && <LoadingState label="Loading published books..." />}

      {error && (
        <ErrorAlert
          title="Could Not Load Books Catalog"
          message={error}
          onDismiss={() => setError(null)}
        />
      )}

      {!loading && !error && books.length === 0 && (
        <EmptyState
          title="No published books yet"
          description="Books appear here once processed on the Create Book page and saved with Save Book."
          action={
            <Link
              to="/books/new"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium bg-bookabook-teal text-white rounded-md hover:bg-bookabook-tealHover"
            >
              <Plus className="w-3.5 h-3.5" />
              Create First Book
            </Link>
          }
        />
      )}

      {!loading && books.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {books.map((book) => (
            <Link
              key={book.book_id}
              to={`/books/${encodeURIComponent(book.book_id)}`}
              className="group bg-white border border-slate-200 rounded-md overflow-hidden hover:border-bookabook-teal transition-colors flex flex-col"
            >
              <div className="h-60 bg-slate-50 border-b border-slate-100 flex items-center justify-center p-3">
                {book.cover_url ? (
                  <img
                    src={booksApi.getDownloadHref(book.cover_url)}
                    alt={`${book.title} cover`}
                    className="max-h-full max-w-full object-contain rounded-sm shadow-sm group-hover:scale-[1.01] transition-transform"
                  />
                ) : (
                  <BookOpen className="w-10 h-10 text-slate-300" />
                )}
              </div>

              <div className="p-4 flex-1 flex flex-col justify-between space-y-2.5">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900 group-hover:text-bookabook-teal line-clamp-1">
                    {book.title}
                  </h2>
                  {book.description && (
                    <p className="text-[11px] text-slate-500 mt-1 line-clamp-2">
                      {book.description}
                    </p>
                  )}
                </div>

                <div className="space-y-1.5 pt-2 border-t border-slate-100 text-[11px] text-slate-600">
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1 truncate">
                      <User className="w-3 h-3 text-slate-400" />
                      {book.author || book.authors_all || 'Unknown author'}
                    </span>
                    {book.year && (
                      <span className="inline-flex items-center gap-1 text-slate-500 shrink-0">
                        <Calendar className="w-3 h-3" />
                        {book.year}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-slate-500">
                    <span>{book.content_pages} content pages</span>
                    <span>
                      {book.sponsor ? book.sponsor : book.age_group ? `Ages ${book.age_group}` : `${book.total_exported_pages} JPGs`}
                    </span>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

