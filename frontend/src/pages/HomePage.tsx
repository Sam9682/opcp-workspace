import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { forumService, type Topic } from '../services/forumService';
import { authService } from '../services/authService';
import { infoService, type Stats } from '../services/infoService';
import { useTranslation } from '../hooks/useLanguage';
import { buildPublicHtmlUrl } from '../utils/forumLinks';
import OPCPpng from '../assets/OPCP.png';

export const HomePage = () => {
  const { t } = useTranslation();
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loadingTopics, setLoadingTopics] = useState(true);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [viewButtonEnabled, setViewButtonEnabled] = useState(true);
  const isAuthenticated = authService.isAuthenticated();

  useEffect(() => {
    loadTopics();
    loadStats();
    loadForumConfig();
  }, []);

  const loadForumConfig = async () => {
    try {
      const cfg = await forumService.getForumConfig();
      setViewButtonEnabled(cfg.view_button_enabled);
    } catch (err) {
      console.error('Error loading forum config:', err);
      // leave viewButtonEnabled = true on error
    }
  };

  const loadTopics = async () => {
    try {
      setLoadingTopics(true);
      const data = isAuthenticated 
        ? await forumService.getTopics(false)
        : await forumService.getTopicsPublic();
      setTopics(data.slice(0, 5));
    } catch (err) {
      console.error('Error loading topics:', err);
      setTopics([]);
    } finally {
      setLoadingTopics(false);
    }
  };

  const loadStats = async () => {
    try {
      setLoadingStats(true);
      const data = await infoService.getStats();
      setStats(data);
    } catch (err) {
      console.error('Error loading stats:', err);
      setStats(null);
    } finally {
      setLoadingStats(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  return (
    <div>
      {/* Hero Section */}
      <div className="text-center mb-12">
        <h1 className="text-4xl md:text-5xl font-bold text-[#000E9C] mb-4">
          {t('page.home.hero.title')}
        </h1>
        <div className="flex justify-center mb-6">
          <img 
            src={OPCPpng} 
            alt="OPCP - Intelligence Artificielle" 
            className="max-w-xl w-full h-auto rounded-lg shadow-md border border-gray-200"
          />
        </div>
        <p className="text-lg text-gray-700 max-w-3xl mx-auto leading-relaxed mb-4">
          {t('page.home.hero.intro')}
        </p>
        <ul className="text-base text-gray-600 max-w-3xl mx-auto space-y-1 list-disc list-inside text-left">
          <li>{t('page.home.hero.bullet.prereq')}</li>
          <li>{t('page.home.hero.bullet.docs')}</li>
          <li>{t('page.home.hero.bullet.forum')}</li>
          <li>{t('page.home.hero.bullet.bots')}  <a href="https://opcp-psmc.com" target="_blank" rel="noopener noreferrer" className="text-[#4949FF] hover:underline font-medium">opcp-psmc.com</a></li>
        </ul>
        <div className="mt-8 flex justify-center gap-4 flex-wrap">
          <a href="/register" className="btn-primary">
            {t('page.home.cta.join')}
          </a>
          <a href="/forum" className="btn-secondary">
            {t('page.home.cta.discoverForum')}
          </a>
        </div>
      </div>

      {/* Features Grid */}
      <div className="grid md:grid-cols-3 gap-6 mb-12">
        <div className="card p-6">
          <h2 className="text-xl font-bold text-[#000E9C] mb-3">{t('page.home.mission.title')}</h2>
          <p className="text-gray-600 text-sm leading-relaxed">
            {t('page.home.mission.body')}
          </p>
        </div>
        
        <div className="card p-6">
          <h2 className="text-xl font-bold text-[#000E9C] mb-3">{t('page.home.activities.title')}</h2>
          <p className="text-gray-600 text-sm leading-relaxed">
            {t('page.home.activities.body')}
          </p>
        </div>
        
        <div className="card p-6">
          <h2 className="text-xl font-bold text-[#000E9C] mb-3">{t('page.home.join.title')}</h2>
          <p className="text-gray-600 text-sm leading-relaxed">
            {t('page.home.join.body')}
            <a href="https://opcp-psmc.com" target="_blank" rel="noopener noreferrer" className="text-[#4949FF] hover:underline font-medium">opcp-psmc.com</a>
          </p>
        </div>
      </div>

      {/* Stats Section */}
      <div className="bg-[#000E9C] rounded-lg p-8 mb-12 text-white">
        <div className="grid md:grid-cols-3 gap-8 text-center">
          <div>
            <div className="text-3xl font-bold mb-1">
              {loadingStats ? '...' : (stats?.total_users || 0)}+
            </div>
            <div className="text-sm text-blue-200">{t('page.home.stats.members')}</div>
          </div>
          <div>
            <div className="text-3xl font-bold mb-1">
              {loadingStats ? '...' : (stats?.total_events || 0)}+
            </div>
            <div className="text-sm text-blue-200">{t('page.home.stats.events')}</div>
          </div>
          <div>
            <div className="text-3xl font-bold mb-1">
              {loadingStats ? '...' : (stats?.total_topics || 0)}+
            </div>
            <div className="text-sm text-blue-200">{t('page.home.stats.topics')}</div>
          </div>
        </div>
      </div>

      {/* Forum Topics Section */}
      <div className="card p-6 mb-12">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-[#000E9C]">{t('page.home.recent.title')}</h2>
          {isAuthenticated ? (
            <Link to="/forum" className="text-sm font-medium text-[#4949FF] hover:underline">
              {t('page.home.recent.seeAll')}
            </Link>
          ) : (
            <Link to="/login" className="btn-primary text-sm py-1.5 px-4">
              {t('page.home.recent.loginToParticipate')}
            </Link>
          )}
        </div>

        {!isAuthenticated && (
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded text-sm text-gray-700">
            <p className="font-medium mb-0.5">{t('page.home.recent.previewTitle')}</p>
            <p className="text-gray-600">{t('page.home.recent.previewBody')}</p>
          </div>
        )}

        {loadingTopics ? (
          <div className="text-center py-8 text-gray-500">{t('page.home.loading')}</div>
        ) : topics.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-600 mb-4">{t('page.home.recent.empty')}</p>
            <Link to="/forum/new" className="btn-primary text-sm">
              {t('page.home.recent.createFirst')}
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {topics.map((topic) => (
              <div key={topic.id} className="py-3 hover:bg-gray-50 transition-colors rounded px-2">
                <div className="flex items-center justify-between">
                  <Link to={`/forum/topics/${topic.id}`} className="flex-1 min-w-0 hover:no-underline">
                    <div className="flex items-center gap-2 mb-0.5">
                      <h3 className="text-sm font-semibold text-gray-900 truncate">
                        {topic.title}
                      </h3>
                      {topic.is_pinned && (
                        <span className="text-xs font-medium px-1.5 py-0.5 bg-yellow-100 text-yellow-800 rounded">
                          {t('page.home.topic.pinned')}
                        </span>
                      )}
                      {!isAuthenticated && (
                        <span className="text-xs font-medium px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
                          {t('page.home.topic.readOnly')}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500">
                      {topic.author_name} · {formatDate(topic.created_at)}
                    </div>
                  </Link>
                  <div className="ml-4 flex items-center gap-2">
                    <span className="text-xs font-medium text-[#000E9C] bg-blue-50 px-2 py-1 rounded">
                      {topic.post_count} {t('page.home.topic.repliesSuffix')}
                    </span>
                    {!isAuthenticated && viewButtonEnabled && (
                      <a
                        href={buildPublicHtmlUrl(window.location.origin, topic.id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-medium text-white bg-[#27ae60] hover:bg-[#219a52] px-2 py-1 rounded transition-colors hover:no-underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {t('page.home.topic.view')}
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Contact Section */}
      <div className="card p-6">
        <h2 className="text-2xl font-bold text-[#000E9C] mb-6">{t('page.home.contact.title')}</h2>
        <div className="grid md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div>
              <p className="font-medium text-gray-900 text-sm">{t('page.home.contact.address.label')}</p>
              <p className="text-gray-600 text-sm">{t('page.home.contact.address.value')}</p>
            </div>
            <div>
              <p className="font-medium text-gray-900 text-sm">{t('page.home.contact.email.label')}</p>
              <a href="mailto:contact@opcp-psmc.com" className="text-[#4949FF] text-sm hover:underline">
                contact@opcp-psmc.com
              </a>
            </div>
          </div>
          <div className="bg-gray-50 p-5 rounded-lg">
            <h3 className="font-semibold text-gray-900 mb-2 text-sm">{t('page.home.contact.team.title')}</h3>
            <p className="text-gray-600 text-sm">
              {t('page.home.contact.team.body')}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
