import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router';

import { apiClient } from './api/apiClient';
import { ExplorePage } from './explore/ExplorePage';
import { InstrumentPage } from './instrument/InstrumentPage';
import { AppLayout } from './layout/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { OverviewPage } from './pages/OverviewPage';
import { PlannedPage } from './pages/PlannedPage';

const DerivativesPage = lazy(async () => {
  const module = await import('./derivatives/DerivativesPage');
  return {
    default: module.DerivativesPage,
  };
});

const KnowledgePage = lazy(async () => {
  const module = await import('./knowledge/KnowledgePage');
  return {
    default: module.KnowledgePage,
  };
});

type SessionState = 'checking' | 'logged-out' | 'logged-in';

/**
 * The application root: checks the session, then shows the login page or the application.
 * @returns The application.
 */
export function App() {
  const [sessionState, setSessionState] = useState<SessionState>('checking');

  useEffect(() => {
    apiClient
      .isLoggedIn()
      .then((loggedIn) => setSessionState(loggedIn ? 'logged-in' : 'logged-out'))
      .catch(() => setSessionState('logged-out'));
  }, []);

  const handleLoggedIn = useCallback(() => setSessionState('logged-in'), []);
  const handleLoggedOut = useCallback(() => setSessionState('logged-out'), []);

  if (sessionState === 'checking') {
    return <p className="centered-message">Loading…</p>;
  }
  if (sessionState === 'logged-out') {
    return <LoginPage onLoggedIn={handleLoggedIn} />;
  }
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout onLoggedOut={handleLoggedOut} />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<OverviewPage />} />
          <Route path="explore" element={<ExplorePage />} />
          <Route path="instrument/:instrumentId" element={<InstrumentPage />} />
          <Route
            path="derivatives"
            element={
              <Suspense fallback={<p className="muted">Loading the derivatives page…</p>}>
                <DerivativesPage />
              </Suspense>
            }
          />
          <Route
            path="universe"
            element={
              <PlannedPage
                title="Universe"
                description="Every instrument as a point in a 3D scene you can fly through."
                phase={7}
                items={[
                  'Clusters by exchange, segment and underlying or sector.',
                  'Points coloured by the day’s change.',
                  'Hover for details and click to open an instrument.',
                ]}
              />
            }
          />
          <Route
            path="screener"
            element={
              <PlannedPage
                title="Screener"
                description="Find instruments that meet technical conditions, computed daily with TA-Lib."
                phase={6}
                items={[
                  'Conditions such as RSI range, moving-average crossovers, distance from the 52-week high or low, and volume spikes.',
                  'A results table and a heatmap of the results by sector.',
                ]}
              />
            }
          />
          <Route
            path="knowledge"
            element={
              <Suspense fallback={<p className="muted">Loading the knowledge page…</p>}>
                <KnowledgePage />
              </Suspense>
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
