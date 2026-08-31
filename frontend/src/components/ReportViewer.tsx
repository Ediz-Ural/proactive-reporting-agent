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
          // Report HTML is built from database rows and LLM output, so it is
          // rendered in a fully sandboxed iframe: no scripts, no same-origin
          // access, no forms. Nothing inside it can reach the dashboard.
          <iframe
            title="Rapor HTML onizlemesi"
            sandbox=""
            srcDoc={contentHtml || ''}
            className="w-full h-[520px] border-0 bg-white"
          />
        )}
      </div>
    </div>
  );
}
