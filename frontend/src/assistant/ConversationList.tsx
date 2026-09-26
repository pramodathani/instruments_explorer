import { useState } from 'react';

import type { ChatConversation } from '../api/types';
import { formatter } from '../utilities/formatter';
import { chatController } from './chatController';

/** Props for ConversationList. */
interface ConversationListProps {
  conversations: ChatConversation[];
  activeId: string | null;
  onOpened?: () => void;
}

/**
 * The past conversations, with rename and delete. Deleting asks for a second click instead of a browser dialog.
 * @param props The conversations, the open one, and what to do after opening one.
 * @returns The list.
 */
export function ConversationList(props: ConversationListProps) {
  const { conversations, activeId, onOpened } = props;
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [armedId, setArmedId] = useState<string | null>(null);

  const open = (conversationId: string) => {
    void chatController.open(conversationId);
    onOpened?.();
  };

  const saveTitle = (conversationId: string) => {
    const title = draft.trim();
    setEditingId(null);
    if (title !== '') {
      void chatController.rename(conversationId, title);
    }
  };

  const remove = (conversationId: string) => {
    if (armedId !== conversationId) {
      setArmedId(conversationId);
      return;
    }
    setArmedId(null);
    void chatController.remove(conversationId);
  };

  if (conversations.length === 0) {
    return <p className="muted conversation-empty">No conversations yet.</p>;
  }
  return (
    <ul className="conversation-list">
      {conversations.map((conversation) => (
        <li key={conversation.conversation_id} className={conversation.conversation_id === activeId ? 'conversation-active' : ''}>
          {editingId === conversation.conversation_id ? (
            <input
              className="input"
              value={draft}
              autoFocus
              onChange={(event) => setDraft(event.target.value)}
              onBlur={() => saveTitle(conversation.conversation_id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  saveTitle(conversation.conversation_id);
                }
                if (event.key === 'Escape') {
                  setEditingId(null);
                }
              }}
            />
          ) : (
            <button type="button" className="conversation-open" onClick={() => open(conversation.conversation_id)}>
              <span className="conversation-title">{conversation.title}</span>
              <span className="muted conversation-when">{formatter.dateTime(conversation.updated_at)}</span>
            </button>
          )}
          <div className="conversation-actions">
            <button
              type="button"
              className="facet-more"
              onClick={() => {
                setEditingId(conversation.conversation_id);
                setDraft(conversation.title);
              }}
            >
              Rename
            </button>
            <button type="button" className={`facet-more ${armedId === conversation.conversation_id ? 'conversation-armed' : ''}`} onClick={() => remove(conversation.conversation_id)} onBlur={() => setArmedId(null)}>
              {armedId === conversation.conversation_id ? 'Click again to delete' : 'Delete'}
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
