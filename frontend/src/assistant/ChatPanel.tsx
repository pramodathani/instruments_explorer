import { useEffect } from 'react';

import type { AssistantStatus } from '../api/types';
import { Icon } from '../components/Icon';
import { StatusBadge } from '../components/StatusBadge';

const SUGGESTIONS = [
  'Chart TCS with RSI and the 50 and 200 day moving averages',
  'Show NIFTY options expiring this week with the highest open interest',
  'What does Reliance Industries do, and is there any recent news?',
  'Screen for IT stocks near their 52-week high',
];

/** Props for ChatPanel. */
interface ChatPanelProps {
  open: boolean;
  assistant: AssistantStatus | null;
  onClose: () => void;
}

/**
 * The Claude chat panel that slides in from the right; for now it shows whether the assistant is configured.
 * @param props Whether the panel is open, the assistant's status, and what closing does.
 * @returns The panel.
 */
export function ChatPanel(props: ChatPanelProps) {
  const { open, assistant, onClose } = props;

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  return (
    <aside className={`chat-panel ${open ? 'chat-panel-open' : ''}`} aria-label="Chat with Claude" aria-hidden={!open}>
      <div className="chat-header">
        <div className="chat-title">
          <Icon name="chat" />
          Claude
          {assistant === null ? null : <span className="chip mono">{assistant.model}</span>}
        </div>
        <button type="button" className="icon-button" aria-label="Close the chat" onClick={onClose} tabIndex={open ? 0 : -1}>
          <Icon name="close" />
        </button>
      </div>
      <div className="chat-body">
        {assistant === null ? <p className="muted">Checking the assistant…</p> : null}
        {assistant !== null && !assistant.configured ? (
          <div className="chat-notice">
            <StatusBadge kind="warning" label="Needs an API key" />
            <p style={{ marginTop: 10 }}>
              The assistant is not configured yet. Put the Claude API key in <code>.env</code> as{' '}
              <code>INSTRUMENTS_EXPLORER_ANTHROPIC_API_KEY</code> and restart the server.
            </p>
          </div>
        ) : null}
        {assistant !== null && assistant.configured ? (
          <div className="chat-notice">
            <StatusBadge kind="neutral" label="Key found" />
            <p style={{ marginTop: 10 }}>The key is set. The conversation itself is built in a later phase.</p>
          </div>
        ) : null}
        <p className="muted">Once it is ready, you will be able to ask things like:</p>
        <div className="chat-suggestions">
          {SUGGESTIONS.map((suggestion) => (
            <div key={suggestion} className="chat-suggestion">
              {suggestion}
            </div>
          ))}
        </div>
      </div>
      <div className="chat-composer">
        <textarea className="input" placeholder="Ask about any instrument…" disabled tabIndex={open ? 0 : -1} />
        <button type="button" className="button button-primary" disabled aria-label="Send">
          <Icon name="send" />
        </button>
      </div>
    </aside>
  );
}
