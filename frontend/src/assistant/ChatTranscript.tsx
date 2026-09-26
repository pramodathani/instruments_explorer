import { useEffect, useRef } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import type { ChatItem } from './chatController';
import { ToolCard } from './ToolCard';

const SUGGESTIONS = [
  'Chart TCS with RSI and the 50 and 200 day moving averages',
  'Show NIFTY options for the nearest expiry with the highest open interest',
  'What does Reliance Industries do, and is there any recent news?',
  'Screen for IT stocks near their 52-week high',
];

/** Props for ChatTranscript. */
interface ChatTranscriptProps {
  items: ChatItem[];
  streaming: boolean;
  loading: boolean;
  onSuggestion: (text: string) => void;
}

/**
 * The conversation: the user's messages, Claude's answers in Markdown, its thinking summaries and its tool calls.
 * @param props The items, whether an answer is streaming, and what a suggestion does.
 * @returns The transcript.
 */
export function ChatTranscript(props: ChatTranscriptProps) {
  const { items, streaming, loading, onSuggestion } = props;
  const endReference = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endReference.current?.scrollIntoView({
      block: 'end',
    });
  }, [items]);

  if (loading) {
    return <p className="muted">Loading the conversation…</p>;
  }
  if (items.length === 0) {
    return (
      <div className="chat-empty">
        <p className="muted">Ask about any instrument, chart, option chain, screen or company. Claude looks things up with the same tools as these pages and can open views for you.</p>
        <div className="chat-suggestions">
          {SUGGESTIONS.map((suggestion) => (
            <button key={suggestion} type="button" className="chat-suggestion" onClick={() => onSuggestion(suggestion)}>
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    );
  }
  const last = items[items.length - 1];
  const waiting = streaming && (last.kind === 'user' || (last.kind === 'tool' && last.done));
  return (
    <div className="chat-transcript">
      {items.map((item) => {
        if (item.kind === 'user') {
          return (
            <div key={item.key} className="chat-user">
              {item.text}
            </div>
          );
        }
        if (item.kind === 'text') {
          return (
            <div key={item.key} className="chat-answer">
              <Markdown remarkPlugins={[remarkGfm]}>{item.text}</Markdown>
            </div>
          );
        }
        if (item.kind === 'thinking') {
          return (
            <details key={item.key} className="chat-thinking">
              <summary>Thinking</summary>
              <div className="muted">
                <Markdown remarkPlugins={[remarkGfm]}>{item.text}</Markdown>
              </div>
            </details>
          );
        }
        if (item.kind === 'tool') {
          return <ToolCard key={item.key} tool={item} />;
        }
        return (
          <div key={item.key} className={`chat-notice-line ${item.tone === 'error' ? 'error-text' : 'chat-refusal'}`}>
            {item.text}
          </div>
        );
      })}
      {waiting ? (
        <div className="chat-waiting" aria-label="Claude is working">
          <span />
          <span />
          <span />
        </div>
      ) : null}
      <div ref={endReference} />
    </div>
  );
}
