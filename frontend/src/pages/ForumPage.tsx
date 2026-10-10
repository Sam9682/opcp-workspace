import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { forumService, type Topic } from '../services/forumService';
import { useTranslation } from '../hooks/useLanguage';

export const ForumPage = () => {
  const { t } = useTranslation();
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTopics();
  }, []);

  const loadTopics = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await forumService.getTopics();
      setTopics(data);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || t('page.forum.error.load'));
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('fr-FR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="text-center py-12 text-gray-500">{t('page.forum.loading')}</div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-[#000E9C]">{t('page.forum.title')}</h1>
          <p className="mt-1 text-sm text-gray-600">{t('page.forum.subtitle')}</p>
        </div>
        <Link
          to="/forum/new"
          className="btn-primary text-sm"
        >
          {t('page.forum.newTopic')}
        </Link>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border-l-4 border-red-500 p-3 rounded">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      <div className="card overflow-hidden">
        {topics.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-600 mb-4">{t('page.forum.empty')}</p>
            <Link to="/forum/new" className="btn-primary text-sm">
              {t('page.forum.createFirst')}
            </Link>
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {topics.map((topic) => (
              <li key={topic.id}>
                <Link
                  to={`/forum/topics/${topic.id}`}
                  className="block px-5 py-4 hover:bg-gray-50 transition-colors hover:no-underline"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-sm font-semibold text-gray-900 truncate">
                          {topic.title}
                        </h3>
                        {topic.is_pinned && (
                          <span className="text-xs font-medium px-1.5 py-0.5 bg-yellow-100 text-yellow-800 rounded">
                            {t('page.forum.topic.pinned')}
                          </span>
                        )}
                        {topic.is_locked && (
                          <span className="text-xs font-medium px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
                            {t('page.forum.topic.locked')}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-500">
                        {topic.author_name} · {formatDate(topic.created_at)}
                      </div>
                    </div>
                    <div className="ml-4">
                      <span className="text-xs font-medium text-[#000E9C] bg-blue-50 px-2.5 py-1 rounded">
                        {topic.post_count} {t('page.forum.topic.repliesSuffix')}
                      </span>
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
