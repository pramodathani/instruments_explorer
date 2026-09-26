import { useEffect } from 'react';

import { ChatComposer } from './ChatComposer';
import { chatController } from './chatController';
import { UsageLine } from './ChatPanel';
import { ChatTranscript } from './ChatTranscript';
import { ConversationList } from './ConversationList';
import { pageContextReader } from './pageContext';
import { useChat } from './useChat';
import { useLayoutContext } from '../layout/layoutContext';

/**
 * The full-page chat: past conversations on the left and the open conversation on the right.
 * @returns The page.
 */
export function ChatPage() {
  const chat = useChat();
  const { status } = useLayoutContext();
  const configured = status !== null && status.assistant.configured;

  useEffect(() => {
    void chatController.refresh();
  }, []);

  const send = (text: string) => {
    void chatController.send(text, pageContextReader.read());
  };

  return (
    <>
      <h1 className="page-title">Chat</h1>
      <p className="page-subtitle">
        Talk to Claude about the market. It looks things up with the same tools as the other pages, and when it opens a view, the page changes and this conversation stays in the panel on the right.
      </p>
      <div className="chat-page">
        <aside className="card chat-page-list">
          <button type="button" className="button button-primary" onClick={() => chatController.startNew()} disabled={chat.streaming}>
            New conversation
          </button>
          <ConversationList conversations={chat.conversations} activeId={chat.activeId} />
        </aside>
        <section className="card chat-page-main">
          <h2 className="chat-page-title">{chat.activeTitle}</h2>
          {!configured && status !== null ? (
            <p className="muted">
              The assistant needs an API key: put it in <code>.env</code> as <code>INSTRUMENTS_EXPLORER_ANTHROPIC_API_KEY</code> and restart the server.
            </p>
          ) : null}
          <div className="chat-page-transcript">
            <ChatTranscript items={chat.items} streaming={chat.streaming} loading={chat.loading} onSuggestion={send} />
          </div>
          <ChatComposer disabled={!configured} streaming={chat.streaming} onSend={send} onStop={() => chatController.stop()} />
          {chat.usage !== null ? <UsageLine billable={chat.usage.billable} limit={chat.usage.limit} model={chat.usage.model} /> : null}
        </section>
      </div>
    </>
  );
}
