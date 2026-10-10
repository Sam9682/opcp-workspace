import { useState, useEffect } from 'react';
import { taskService, type Task } from '../services/taskService';
import { useTranslation } from '../hooks/useLanguage';

/**
 * Member-facing, read-only tasks view. Mirrors the data-loading pattern and
 * card layout of EventsPage but scoped to tasks. Members see their assigned
 * tasks as scoped by the backend `GET /tasks` endpoint.
 */
export const TasksPage = () => {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadTasks();
  }, []);

  const loadTasks = async () => {
    try {
      setLoading(true);
      const data = await taskService.listTasks();
      setTasks(data);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="text-center py-8 text-gray-500">{t('page.tasks.loading')}</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-[#000E9C]">{t('page.tasks.title')}</h1>
      </div>

      {tasks.length === 0 ? (
        <div className="text-center py-8 text-gray-500">{t('page.tasks.empty')}</div>
      ) : (
        <div className="grid gap-4">
          {tasks.map((task) => (
            <div key={task.id} className="card p-5">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-1">{task.title}</h3>
                  {task.description && <p className="text-sm text-gray-600 mb-2">{task.description}</p>}
                  <div className="text-xs text-gray-500 space-y-0.5">
                    <p>{t('page.tasks.start')} {new Date(task.start_date).toLocaleString('fr-FR')}</p>
                    <p>{t('page.tasks.end')} {new Date(task.end_date).toLocaleString('fr-FR')}</p>
                    {task.location && <p>{t('page.tasks.location')} {task.location}</p>}
                    <p>
                      <span className={`inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium ${
                        task.status === 'scheduled' ? 'bg-green-100 text-green-800' :
                        task.status === 'cancelled' ? 'bg-red-100 text-red-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {task.status}
                      </span>
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
