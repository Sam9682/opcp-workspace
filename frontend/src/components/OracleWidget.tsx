import { useState } from 'react';
import { oracleService } from '../services/oracleService';
import type { Source } from '../services/oracleService';
import { SourcesList } from './SourcesList';

interface OracleWidgetProps {
  onAnalysisComplete?: (analysis: any) => void;
}

interface WidgetAnalysis {
  summary: string;
  job_loss_prediction_5y: number;
  job_loss_prediction_10y: number;
  job_loss_prediction_20y: number;
  key_topics: string[];
  sentiment: string;
  confidence: number;
  sources?: Source[];
}

export const OracleWidget = ({ onAnalysisComplete }: OracleWidgetProps) => {
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<WidgetAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyzeForumMessages = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await oracleService.analyzeForumMessages('kiro');
      setAnalysis({ ...result, sources: (result as WidgetAnalysis).sources });
      if (onAnalysisComplete) {
        onAnalysisComplete(result);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors de l\'analyse');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[#000E9C]">Oracle IA</h3>
        <button
          onClick={analyzeForumMessages}
          disabled={loading}
          className="px-4 py-2 bg-[#000E9C] text-white text-sm font-medium rounded hover:bg-[#4949FF] disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Analyse...' : 'Analyser le forum'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm mb-4">
          {error}
        </div>
      )}

      {analysis && (
        <div className="space-y-4">
          <div className="bg-gray-50 rounded p-4">
            <h4 className="text-sm font-semibold text-gray-800 mb-1">Résumé des discussions</h4>
            <p className="text-sm text-gray-700">{analysis.summary}</p>
          </div>

          <div className="bg-gray-50 rounded p-4">
            <h4 className="text-sm font-semibold text-gray-800 mb-2">Prédictions de perte d'emplois</h4>
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-600">Dans 5 ans :</span>
                <span className="text-sm font-semibold text-orange-600">{analysis.job_loss_prediction_5y.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-600">Dans 10 ans :</span>
                <span className="text-sm font-semibold text-red-600">{analysis.job_loss_prediction_10y.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-600">Dans 20 ans :</span>
                <span className="text-sm font-semibold text-red-700">{analysis.job_loss_prediction_20y.toFixed(1)}%</span>
              </div>
            </div>
          </div>

          {analysis.key_topics && analysis.key_topics.length > 0 && (
            <div className="bg-gray-50 rounded p-4">
              <h4 className="text-sm font-semibold text-gray-800 mb-2">Sujets clés</h4>
              <div className="flex flex-wrap gap-1.5">
                {analysis.key_topics.map((topic: string, index: number) => (
                  <span key={index} className="px-2 py-0.5 bg-blue-50 text-[#000E9C] rounded text-xs font-medium">
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="bg-gray-50 rounded p-4">
            <div className="flex justify-between items-center">
              <div>
                <h4 className="text-sm font-semibold text-gray-800">Sentiment</h4>
                <p className="text-xs text-gray-600 capitalize">{analysis.sentiment}</p>
              </div>
              <div className="text-right">
                <h4 className="text-sm font-semibold text-gray-800">Confiance</h4>
                <p className="text-xs text-gray-600">{(analysis.confidence * 100).toFixed(0)}%</p>
              </div>
            </div>
          </div>

          <SourcesList sources={analysis.sources} />
        </div>
      )}

      {!analysis && !loading && (
        <div className="text-center py-6 text-gray-500">
          <p className="text-sm mb-2">Cliquez sur "Analyser le forum" pour obtenir :</p>
          <ul className="text-xs space-y-0.5">
            <li>Résumé des discussions</li>
            <li>Prédictions de perte d'emplois (5, 10, 20 ans)</li>
            <li>Sujets clés et sentiment général</li>
          </ul>
        </div>
      )}
    </div>
  );
};
