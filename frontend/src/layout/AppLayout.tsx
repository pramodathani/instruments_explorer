import { useCallback, useEffect, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router';

import { ApiError, apiClient } from '../api/apiClient';
import type { StatusDocument } from '../api/types';
import { chatController } from '../assistant/chatController';
import { ChatPanel } from '../assistant/ChatPanel';
import { AmbientBackground } from '../components/AmbientBackground';
import { liveSocket } from '../live/liveServices';
import { Header } from './Header';
import type { LayoutContext } from './layoutContext';

/** Props for AppLayout. */
interface AppLayoutProps {
  onLoggedOut: () => void;
}

/**
 * The frame around every page: the 3D backdrop, the header, the page with its entrance animation, and the chat panel.
 * @param props What to do after logging out or when the session ends.
 * @returns The layout.
 */
export function AppLayout(props: AppLayoutProps) {
  const { onLoggedOut } = props;
  const location = useLocation();
  const navigate = useNavigate();
  const [chatOpen, setChatOpen] = useState(false);
  const [status, setStatus] = useState<StatusDocument | null>(null);

  const refreshStatus = useCallback(() => {
    apiClient
      .fetchStatus()
      .then(setStatus)
      .catch((caught: unknown) => {
        if (caught instanceof ApiError && caught.statusCode === 401) {
          onLoggedOut();
        }
      });
  }, [onLoggedOut]);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    liveSocket.start(onLoggedOut);
    return () => liveSocket.stop();
  }, [onLoggedOut]);

  useEffect(() => {
    chatController.setNavigator((path) => {
      if (window.location.pathname === '/chat') {
        setChatOpen(true);
      }
      void navigate(path);
    });
    return () => chatController.setNavigator(null);
  }, [navigate]);

  const closeChat = useCallback(() => setChatOpen(false), []);
  const openChat = useCallback(() => setChatOpen(true), []);

  const logOut = () => {
    apiClient.logOut().finally(onLoggedOut);
  };

  const context: LayoutContext = {
    status,
    refreshStatus,
    openChat,
  };

  return (
    <>
      <AmbientBackground pulseKey={location.pathname} />
      <Header chatOpen={chatOpen} onToggleChat={() => setChatOpen((open) => !open)} onLogOut={logOut} />
      <div className={`shell ${chatOpen ? 'shell-with-chat' : ''}`}>
        <main className="content">
          <div key={location.pathname} className="page-transition">
            <Outlet context={context} />
          </div>
        </main>
      </div>
      <ChatPanel open={chatOpen} assistant={status === null ? null : status.assistant} onClose={closeChat} />
    </>
  );
}
