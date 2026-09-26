import { useCallback, useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router';

import { apiClient } from './api/apiClient';
import { ExplorePage } from './explore/ExplorePage';
import { InstrumentPage } from './instrument/InstrumentPage';
import { AppLayout } from './layout/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { OverviewPage } from './pages/OverviewPage';
import { PlannedPage } from './pages/PlannedPage';

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
              <PlannedPage
                title="Derivatives"
                description="Walk from an underlying to its futures and options."
                phase={4}
                items={[
                  'An expiry tree for each underlying.',
                  'An option chain with LTP, open interest and implied volatility.',
                  'A 3D volatility surface of strike, expiry and implied volatility.',
                ]}
              />
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
              <PlannedPage
                title="Knowledge"
                description="Company and instrument information gathered from the internet and your own documents."
                phase={5}
                items={[
                  'Fetchers for NSE, BSE, yfinance, Wikipedia, Screener.in, news feeds and web search.',
                  'Document upload for PDFs, web pages and notes.',
                  'Semantic search across everything, stored in MongoDB and ChromaDB.',
                ]}
              />
            }
          />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
