import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { ForgotPasswordPage } from './pages/ForgotPasswordPage';
import { ResetPasswordPage } from './pages/ResetPasswordPage';
import { ForumPage } from './pages/ForumPage';
import { TopicDetailPage } from './pages/TopicDetailPage';
import { NewTopicPage } from './pages/NewTopicPage';
import { AdminUsersPage } from './pages/AdminUsersPage';
import { AdminConfigPage } from './pages/AdminConfigPage';
import { AdminEventsPage } from './pages/AdminEventsPage';
import { AdminTasksPage } from './pages/AdminTasksPage';
import { OraclePage } from './pages/OraclePage';
import { HowToUsePage } from './pages/HowToUsePage';
import { InstallationListPage } from './components/prerequisites/InstallationListPage';
import { InstallationPrereqPage } from './pages/InstallationPrereqPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { EventsPage } from './pages/EventsPage';
import { TasksPage } from './pages/TasksPage';
import { SecurityPage } from './pages/SecurityPage';
import { LanguageProvider } from './hooks/useLanguage';

function App() {
  return (
    <LanguageProvider>
      <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route
          path="/*"
          element={
            <Layout>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route
                  path="/forum"
                  element={
                    <ProtectedRoute>
                      <ForumPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/forum/new"
                  element={
                    <ProtectedRoute>
                      <NewTopicPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/forum/topics/:topicId"
                  element={
                    <ProtectedRoute>
                      <TopicDetailPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/users"
                  element={
                    <ProtectedRoute>
                      <AdminUsersPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/events"
                  element={
                    <ProtectedRoute>
                      <AdminEventsPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/tasks"
                  element={
                    <ProtectedRoute>
                      <AdminTasksPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/configuration"
                  element={
                    <ProtectedRoute>
                      <AdminConfigPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/oracle"
                  element={
                    <ProtectedRoute>
                      <OraclePage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/prerequisites/how-to-use"
                  element={
                    <ProtectedRoute>
                      <HowToUsePage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/prerequisites/installations"
                  element={
                    <ProtectedRoute>
                      <InstallationListPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/prerequisites/installations/:installationId/:slug"
                  element={
                    <ProtectedRoute>
                      <InstallationPrereqPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/documents"
                  element={
                    <ProtectedRoute>
                      <DocumentsPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/events"
                  element={
                    <ProtectedRoute>
                      <EventsPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/tasks"
                  element={
                    <ProtectedRoute>
                      <TasksPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/account/security"
                  element={
                    <ProtectedRoute>
                      <SecurityPage />
                    </ProtectedRoute>
                  }
                />
                {/* Additional routes will be added in future tasks */}
              </Routes>
            </Layout>
          }
        />
      </Routes>
      </Router>
    </LanguageProvider>
  );
}

export default App;
