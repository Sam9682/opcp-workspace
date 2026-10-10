import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { forumService } from '../services/forumService';
import { useTranslation } from '../hooks/useLanguage';

export const NewTopicPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    try {
      setSubmitting(true);
      setError(null);
      const topic = await forumService.createTopic({ title });
      navigate(`/forum/topics/${topic.id}`);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || t('page.newTopic.error.create'));
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="mb-5">
        <Link to="/forum" className="text-sm font-medium text-[#4949FF] hover:underline">
          {t('page.newTopic.back')}
        </Link>
      </div>

      <div className="card p-6">
        <h1 className="text-2xl font-bold text-[#000E9C] mb-5">{t('page.newTopic.title')}</h1>

        <form onSubmit={handleSubmit}>
          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-1">
              {t('page.newTopic.field.title')}
            </label>
            <input
              type="text"
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-[#4949FF] focus:border-transparent"
              placeholder={t('page.newTopic.placeholder.title')}
              disabled={submitting}
              required
              maxLength={255}
            />
            <p className="mt-1 text-xs text-gray-500">
              {t('page.newTopic.hint')}
            </p>
          </div>

          <div className="mt-5 flex justify-end gap-3">
            <Link
              to="/forum"
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 transition-colors"
            >
              {t('page.newTopic.cancel')}
            </Link>
            <button
              type="submit"
              disabled={submitting || !title.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-[#000E9C] rounded hover:bg-[#4949FF] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? t('page.newTopic.submitting') : t('page.newTopic.submit')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
