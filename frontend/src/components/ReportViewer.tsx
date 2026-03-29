import { useState } from 'react';
import ReactMarkdown from 'react-markdown';

interface ReportViewerProps {
  contentMd: string;
  contentHtml?: string | null;
}

export default function ReportViewer({ contentMd, contentHtml }: ReportViewerProps) {
  const [view, setView] = useState<'md' | 'html'>('md');

  return (
    <div>
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setView('md')}
          className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
            view === 'md'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          Markdown
        </button>
        {contentHtml && (
          <button
            onClick={() => setView('html')}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
              view === 'html'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            HTML
          </button>
        )}
      </div>
      <div className="bg-white rounded-xl border border-gray-200 p-6 overflow-auto max-h-[600px]">
        {view === 'md' ? (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{contentMd}</ReactMarkdown>
          </div>
        ) : (
          <div dangerouslySetInnerHTML={{ __html: contentHtml || '' }} />
        )}
      </div>
    </div>
  );
}
