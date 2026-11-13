import React from 'react';
import { FileQuestion } from 'lucide-react';
import { Link } from 'react-router-dom';
import { EmptyState } from '@/components/StateNotice';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="max-w-xl mx-auto py-12">
      <EmptyState
        title="Page Not Found"
        description="The requested route does not exist in the Bookabook operator console."
        icon={<FileQuestion className="w-5 h-5" />}
        action={
          <Link
            to="/"
            className="px-4 py-2 text-xs font-medium rounded-lg bg-slate-900 text-white hover:bg-slate-800"
          >
            Return to Dashboard
          </Link>
        }
      />
    </div>
  );
};

