import { useSyncExternalStore } from 'react';

import { type ChatState, chatController } from './chatController';

/**
 * Follows the chat's state, re-rendering when it changes.
 * @returns The state.
 */
export function useChat(): ChatState {
  return useSyncExternalStore(chatController.subscribe, chatController.snapshot);
}
