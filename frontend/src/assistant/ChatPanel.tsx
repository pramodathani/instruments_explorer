import { useEffect, useState } from 'react';
import { Link } from 'react-router';

import type { AssistantStatus } from '../api/types';
import { Icon } from '../components/Icon';
import { StatusBadge } from '../components/StatusBadge';
import { ChatComposer } from './ChatComposer';
import { chatController } from './chatController';
import { ChatTranscript } from './ChatTranscript';
import { ConversationList } from './ConversationList';
import { pageContextReader } from './pageContext';
import { useChat } from './useChat';

/** Props for ChatPanel. */
interface ChatPanelProps {
  open: boolean;
  assistant: AssistantStatus | null;
  onClose: () => void;
}

/**
 * The Claude chat panel that slides in from the right beside any page.
 * @param props Whether the panel is open, the assistant's status, and what closing does.
 * @returns The panel.
 */
export function ChatPanel(props: ChatPanelProps) {
  const { open, assistant, onClose } = props;
  const chat = useChat();
  const [showList, setShowList] = useState(false);
  const configured = assistant !== null && assistant.configured;

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    void chatController.refresh();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  const send = (text: string) => {
    void chatController.send(text, pageContextReader.read());
  };

  const tabIndex = open ? 0 : -1;

  return (
    <aside className={`chat-panel ${open ? 'chat-panel-open' : ''}`} aria-label="Chat with Claude" aria-hidden={!open}>
      <div className="chat-header">
        <div className="chat-title">
          <Icon name="chat" />
          <span className="chat-title-text">{chat.activeTitle}</span>
        </div>
        <div className="chat-header-actions">
          <button type="button" className="button button-quiet" onClick={() => setShowList(!showList)} tabIndex={tabIndex} aria-pressed={showList}>
            History
          </button>
          <button
            type="button"
            className="button button-quiet"
            onClick={() => {
              chatController.startNew();
              setShowList(false);
            }}
            tabIndex={tabIndex}
            disabled={chat.streaming}
          >
            New
          </button>
          <Link to="/chat" className="icon-button" title="Open the full chat page" aria-label="Open the full chat page" tabIndex={tabIndex} onClick={onClose}>
            <Icon name="expand" />
          </Link>
          <button type="button" className="icon-button" aria-label="Close the chat" onClick={onClose} tabIndex={tabIndex}>
            <Icon name="close" />
          </button>
        </div>
      </div>
      <div className="chat-body">
        {assistant !== null && !assistant.configured ? (
          <div className="chat-notice">
            <StatusBadge kind="warning" label="Needs an API key" />
            <p style={{ marginTop: 10 }}>
              Put the Claude API key in <code>.env</code> as <code>INSTRUMENTS_EXPLORER_ANTHROPIC_API_KEY</code> and restart the server.
            </p>
          </div>
        ) : null}
        {showList ? (
          <ConversationList conversations={chat.conversations} activeId={chat.activeId} onOpened={() => setShowList(false)} />
        ) : (
          <ChatTranscript items={chat.items} streaming={chat.streaming} loading={chat.loading} onSuggestion={send} />
        )}
        {chat.error !== '' ? <p className="error-text">{chat.error}</p> : null}
      </div>
      <ChatComposer disabled={!configured} streaming={chat.streaming} onSend={send} onStop={() => chatController.stop()} />
      {chat.usage !== null ? <UsageLine billable={chat.usage.billable} limit={chat.usage.limit} model={chat.usage.model} /> : null}
    </aside>
  );
}

/** Props for UsageLine. */
interface UsageLineProps {
  billable: number;
  limit: number;
  model: string;
}

/**
 * A thin bar showing today's tokens against the daily limit.
 * @param props Today's billable tokens, the limit and the model.
 * @returns The line.
 */
export function UsageLine(props: UsageLineProps) {
  const { billable, limit, model } = props;
  const share = limit > 0 ? Math.min(billable / limit, 1) : 0;
  return (
    <div className="chat-usage" title="Input, output and cache-write tokens used today, against the daily limit.">
      <div className="chat-usage-bar">
        <span style={{ width: `${share * 100}%` }} />
      </div>
      <span className="muted mono">
        {model} · {Math.round(billable / 1000).toLocaleString('en-IN')}k of {Math.round(limit / 1000).toLocaleString('en-IN')}k tokens today
      </span>
    </div>
  );
}
