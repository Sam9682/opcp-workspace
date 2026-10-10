import { useState, useEffect, useRef } from 'react';
import { oracleService } from '../services/oracleService';
import type { Source, AvailableProvider, AIProviderId } from '../services/oracleService';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import { SourcesList } from '../components/SourcesList';
import { useTranslation } from '../hooks/useLanguage';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  provider?: string;
  processingTime?: number;
  sources?: Source[];
}

export const OraclePage = () => {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [provider, setProvider] = useState<AIProviderId>('shai');
  const [enabledProviders, setEnabledProviders] = useState<AvailableProvider[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load which AI providers are enabled by the administrator. Only enabled
  // providers are shown in the dropdown; disabled ones are absent entirely.
  useEffect(() => {
    let cancelled = false;
    oracleService
      .getAvailableProviders()
      .then((data) => {
        if (cancelled) return;
        const enabled = (data.providers || []).filter((p) => p.enabled);
        setEnabledProviders(enabled);
        // If the currently selected provider is not enabled, fall back to the
        // first enabled one (shai is always enabled).
        setProvider((current) =>
          enabled.some((p) => p.id === current)
            ? current
            : (enabled[0]?.id ?? 'shai')
        );
      })
      .catch((error) => {
        console.error('Failed to load AI providers:', error);
        // Fall back to shai only, which is always available.
        setEnabledProviders([
          { id: 'shai', name: 'Shai AI (OVH)', description: '', default: true, enabled: true },
        ]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setMessages([
      {
        id: '0',
        role: 'assistant',
        content: t('page.oracle.welcome'),
        timestamp: new Date()
      }
    ]);
  }, [t]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadHistory = async () => {
    try {
      const data = await oracleService.getHistory();
      setHistory(data);
      setShowHistory(true);
    } catch (error) {
      console.error('Failed to load history:', error);
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    const questionText = input;
    setInput('');
    setLoading(true);

    const assistantMessageId = (Date.now() + 1).toString();
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      await oracleService.askOracleStream(
        {
          question: questionText,
          ai_provider: provider,
          temperature: 0.7,
          max_tokens: 2000
        },
        (content: string) => {
          setMessages(prev => 
            prev.map(msg => 
              msg.id === assistantMessageId
                ? { ...msg, content: msg.content + content }
                : msg
            )
          );
        },
        (data: any) => {
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessageId
                ? { ...msg, provider: data.provider, processingTime: data.processing_time, sources: data.sources }
                : msg
            )
          );
          setLoading(false);
        },
        (error: string) => {
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessageId
                ? { ...msg, content: `Erreur: ${error}` }
                : msg
            )
          );
          setLoading(false);
        }
      );
    } catch (error: any) {
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessageId
            ? { ...msg, content: `Erreur: ${error.message || t('page.oracle.error.contact')}` }
            : msg
        )
      );
      setLoading(false);
    }
  };

  const loadHistoryItem = (item: any) => {
    setMessages([
      {
        id: '0',
        role: 'assistant',
        content: t('page.oracle.welcome.short'),
        timestamp: new Date()
      },
      {
        id: item.id.toString() + '-q',
        role: 'user',
        content: item.question,
        timestamp: new Date(item.created_at)
      },
      {
        id: item.id.toString(),
        role: 'assistant',
        content: item.answer,
        timestamp: new Date(item.created_at),
        provider: item.ai_provider,
        processingTime: item.processing_time
      }
    ]);
    setShowHistory(false);
  };

  return (
    <div className="max-w-6xl mx-auto">
      <div className="bg-[#000E9C] rounded-lg p-6 mb-6">
        <h1 className="text-2xl font-bold text-white mb-1">{t('page.oracle.title')}</h1>
        <p className="text-sm text-blue-200">
          {t('page.oracle.subtitle')}        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar */}
        <div className="lg:col-span-1 space-y-4">
          <div className="card p-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">{t('page.oracle.provider.label')}</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as AIProviderId)}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent"
              disabled={loading}
            >
              {enabledProviders.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div className="card p-4">
            <button
              onClick={loadHistory}
              className="w-full px-4 py-2 bg-[#000E9C] text-white text-sm font-medium rounded hover:bg-[#4949FF] transition-colors"
            >
              {t('page.oracle.history')}
            </button>
          </div>

          <div className="card p-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">{t('page.oracle.examples.title')}</h4>
            <ul className="space-y-2 text-xs text-gray-600">
              <li className="cursor-pointer hover:text-[#4949FF] transition-colors" onClick={() => setInput("What is OPCP ?")}>
                {t('page.oracle.examples.medical')}
              </li>
              <li className="cursor-pointer hover:text-[#4949FF] transition-colors" onClick={() => setInput("What is Openstack ?")}>
                {t('page.oracle.examples.web')}
              </li>
              <li className="cursor-pointer hover:text-[#4949FF] transition-colors" onClick={() => setInput("Display curl command to get the list of servers via API openstack ?")}>
                {t('page.oracle.examples.ethics')}
              </li>
            </ul>
          </div>
        </div>

        {/* Chat Area */}
        <div className="lg:col-span-3">
          <div className="card flex flex-col" style={{ height: '600px' }}>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-3xl rounded-lg p-4 text-sm ${
                      message.role === 'user'
                        ? 'bg-[#000E9C] text-white'
                        : 'bg-gray-50 text-gray-800 border border-gray-200'
                    }`}
                  >
                    {message.role === 'user' ? (
                      <div className="whitespace-pre-wrap">{message.content}</div>
                    ) : (
                      <MarkdownRenderer content={message.content} />
                    )}
                    {message.provider && (
                      <div className="text-xs mt-2 opacity-60">
                        {message.provider} Â· {message.processingTime?.toFixed(2)}s
                      </div>
                    )}
                    {message.role === 'assistant' && message.sources?.length ? (
                      <SourcesList sources={message.sources} />
                    ) : null}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                    <div className="flex space-x-1.5">
                      <div className="w-2 h-2 bg-[#000E9C] rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-[#000E9C] rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-[#000E9C] rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSubmit} className="border-t border-gray-200 p-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={t('page.oracle.input.placeholder')}
                  className="flex-1 px-3 py-2.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="px-5 py-2.5 bg-[#000E9C] text-white text-sm font-medium rounded hover:bg-[#4949FF] disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  {t('page.oracle.send')}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>

      {/* History Modal */}
      {showHistory && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden">
            <div className="p-5 border-b border-gray-200 flex justify-between items-center">
              <h2 className="text-xl font-bold text-[#000E9C]">{t('page.oracle.history.title')}</h2>
              <button
                onClick={() => setShowHistory(false)}
                className="text-gray-400 hover:text-gray-600 text-xl"
              >
                Ã—
              </button>
            </div>
            <div className="p-5 overflow-y-auto max-h-[60vh]">
              {history.length === 0 ? (
                <p className="text-gray-500 text-center py-8 text-sm">{t('page.oracle.history.empty')}</p>
              ) : (
                <div className="space-y-3">
                  {history.map((item) => (
                    <div
                      key={item.id}
                      onClick={() => loadHistoryItem(item)}
                      className="card p-4 cursor-pointer hover:bg-gray-50 transition-colors"
                    >
                      <div className="text-sm font-medium text-gray-900 mb-1">{item.question}</div>
                      <div className="text-xs text-gray-600 line-clamp-2">{item.answer}</div>
                      <div className="text-xs text-gray-400 mt-2">
                        {item.ai_provider} Â· {new Date(item.created_at).toLocaleString('fr-FR')}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
