import type { Source } from '../services/oracleService';

interface SourcesListProps {
  sources?: Source[];
}

export const SourcesList = ({ sources }: SourcesListProps) => {
  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <details className="mt-3 bg-gray-50 border border-gray-200 rounded">
      <summary className="cursor-pointer select-none px-3 py-2 text-sm font-semibold text-[#000E9C]">
        Sources ({sources.length})
      </summary>
      <ul className="px-3 pb-3 pt-1 space-y-2">
        {sources.map((source, index) => (
          <li key={index} className="text-sm text-gray-700">
            <div className="flex items-start justify-between gap-2">
              <span className="font-medium text-gray-800">{source.title}</span>
              <span className="shrink-0 text-xs font-semibold text-[#000E9C]">
                {(source.similarity * 100).toFixed(1)}%
              </span>
            </div>
            <p className="text-xs text-gray-500 break-all">{source.file_path}</p>
          </li>
        ))}
      </ul>
    </details>
  );
};
