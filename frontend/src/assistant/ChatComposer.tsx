import { type KeyboardEvent, useState } from 'react';

import { Icon } from '../components/Icon';

/** Props for ChatComposer. */
interface ChatComposerProps {
  disabled: boolean;
  streaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

/**
 * The message box: Enter sends, Shift and Enter starts a new line, and the button stops an answer in progress.
 * @param props Whether sending is possible, whether an answer is streaming, and what sending and stopping do.
 * @returns The composer.
 */
export function ChatComposer(props: ChatComposerProps) {
  const { disabled, streaming, onSend, onStop } = props;
  const [text, setText] = useState('');

  const send = () => {
    if (text.trim() === '' || disabled || streaming) {
      return;
    }
    onSend(text);
    setText('');
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      send();
    }
  };

  return (
    <div className="chat-composer">
      <textarea
        className="input"
        placeholder={disabled ? 'The assistant needs an API key' : 'Ask Claude…'}
        value={text}
        disabled={disabled}
        rows={2}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      {streaming ? (
        <button type="button" className="button chat-send" onClick={onStop} aria-label="Stop the answer">
          Stop
        </button>
      ) : (
        <button type="button" className="button button-primary chat-send" onClick={send} disabled={disabled || text.trim() === ''} aria-label="Send">
          <Icon name="send" />
        </button>
      )}
    </div>
  );
}
