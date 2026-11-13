import React, { useState } from 'react';
import { Search } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface DocumentLookupBarProps {
  mode?: 'document' | 'preview' | 'review' | 'session';
  placeholder?: string;
  buttonLabel?: string;
}

export const DocumentLookupBar: React.FC<DocumentLookupBarProps> = ({
  mode = 'document',
  placeholder = 'Enter Document ID (e.g., doc_861c55342a0e)',
  buttonLabel = 'Open',
}) => {
  const [value, setValue] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) {
      setValidationError('Please enter a valid identifier.');
      return;
    }
    setValidationError(null);

    if (mode === 'session') {
      navigate(`/reviews/${encodeURIComponent(trimmed)}`);
    } else if (mode === 'preview') {
      navigate(`/documents/${encodeURIComponent(trimmed)}/preview`);
    } else if (mode === 'review') {
      navigate(`/documents/${encodeURIComponent(trimmed)}/review`);
    } else {
      navigate(`/documents/${encodeURIComponent(trimmed)}`);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              if (validationError) setValidationError(null);
            }}
            placeholder={placeholder}
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-bookabook-field border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-bookabook-teal/30 focus:border-bookabook-teal focus:bg-white font-mono text-slate-800 transition-colors"
          />
        </div>
        <button
          type="submit"
          className="px-3.5 py-1.5 text-xs font-medium text-white bg-bookabook-teal rounded-md hover:bg-bookabook-tealHover transition-colors shrink-0"
        >
          {buttonLabel}
        </button>
      </form>
      {validationError && (
        <p className="text-[11px] text-rose-600 mt-1">{validationError}</p>
      )}
    </div>
  );
};
