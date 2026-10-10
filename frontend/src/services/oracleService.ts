import api from './api';

export interface Source {
  title: string;
  file_path: string;
  similarity: number;
}

interface OracleQuery {
  question: string;
  context?: string;
  ai_provider?: 'shai' | 'kiro' | 'openai' | 'opcp_companion';
  temperature?: number;
  max_tokens?: number;
}

interface OracleResponse {
  id: number;
  question: string;
  answer: string;
  ai_provider: string;
  context?: string;
  created_at: string;
  user_id?: number;
  processing_time: number;
  tokens_used?: number;
  sources?: Source[];
}

interface OracleHistoryItem {
  id: number;
  question: string;
  answer: string;
  ai_provider: string;
  created_at: string;
  processing_time: number;
}

interface ForumAnalysisResponse {
  summary: string;
  job_loss_prediction_5y: number;
  job_loss_prediction_10y: number;
  job_loss_prediction_20y: number;
  key_topics: string[];
  sentiment: string;
  confidence: number;
}

export type AIProviderId = 'shai' | 'kiro' | 'openai' | 'opcp_companion';

export interface AvailableProvider {
  id: AIProviderId;
  name: string;
  description: string;
  default: boolean;
  enabled: boolean;
}

interface AvailableProvidersResponse {
  providers: AvailableProvider[];
}

class OracleService {
  async askOracle(query: OracleQuery): Promise<OracleResponse> {
    const response = await api.post('/oracle/ask', query);
    return response.data;
  }

  async askOracleStream(
    query: OracleQuery,
    onToken: (content: string) => void,
    onDone: (data: any) => void,
    onError: (error: string) => void
  ): Promise<void> {
    // Use fetch with ReadableStream for SSE with authentication
    await this.askOracleStreamFetch(query, onToken, onDone, onError);
  }

  private async askOracleStreamFetch(
    query: OracleQuery,
    onToken: (content: string) => void,
    onDone: (data: any) => void,
    onError: (error: string) => void
  ): Promise<void> {
    const token = localStorage.getItem('token');
    const baseURL = api.defaults.baseURL || '';
    
    try {
      const response = await fetch(`${baseURL}/oracle/ask/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` })
        },
        body: JSON.stringify(query)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'token') {
                onToken(data.content);
              } else if (data.type === 'done') {
                onDone(data);
              } else if (data.type === 'error') {
                onError(data.message);
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
          }
        }
      }
    } catch (error: any) {
      onError(error.message || 'Connection error');
    }
  }

  async getHistory(limit: number = 50): Promise<OracleHistoryItem[]> {
    const response = await api.get('/oracle/history', {
      params: { limit }
    });
    return response.data;
  }

  async analyzeForumMessages(aiProvider: 'shai' | 'kiro' | 'openai' | 'opcp_companion' = 'kiro'): Promise<ForumAnalysisResponse> {
    const response = await api.post('/oracle/analyze/forum', {
      analysis_type: 'forum_summary',
      ai_provider: aiProvider
    });
    return response.data;
  }

  async getAvailableProviders(): Promise<AvailableProvidersResponse> {
    const response = await api.get('/oracle/providers');
    return response.data;
  }
}

export const oracleService = new OracleService();
