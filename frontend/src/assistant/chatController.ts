import { ApiError, apiClient } from '../api/apiClient';
import type { ChatConversation, ChatStoredItem, ChatStreamEvent, ChatUiAction, ChatUsage } from '../api/types';

/** One piece of the conversation as the chat draws it. */
export type ChatItem =
  | {
      kind: 'user';
      key: string;
      text: string;
    }
  | {
      kind: 'text';
      key: string;
      text: string;
    }
  | {
      kind: 'thinking';
      key: string;
      text: string;
    }
  | {
      kind: 'tool';
      key: string;
      id: string;
      name: string;
      input: unknown;
      summary: string;
      isError: boolean;
      done: boolean;
      uiAction: ChatUiAction | null;
    }
  | {
      kind: 'notice';
      key: string;
      tone: 'error' | 'refusal';
      text: string;
    };

/** Everything the chat shows, replaced as a whole on every change so React sees each change. */
export interface ChatState {
  conversations: ChatConversation[];
  activeId: string | null;
  activeTitle: string;
  items: ChatItem[];
  streaming: boolean;
  loading: boolean;
  error: string;
  usage: ChatUsage | null;
}

/** The page the user is on, sent with each message. */
export interface ChatPage {
  path: string;
  title: string;
}

const EMPTY_STATE: ChatState = {
  conversations: [],
  activeId: null,
  activeTitle: 'New chat',
  items: [],
  streaming: false,
  loading: false,
  error: '',
  usage: null,
};

/** Holds the chat's conversations and the open one, sends messages and follows the streamed answers, for both the panel and the chat page. */
export class ChatController {
  private state: ChatState = EMPTY_STATE;
  private readonly listeners = new Set<() => void>();
  private navigator: ((path: string) => void) | null = null;
  private abortController: AbortController | null = null;
  private keyCounter = 0;

  /**
   * Gives the current state.
   * @returns The state.
   */
  snapshot = (): ChatState => {
    return this.state;
  };

  /**
   * Starts telling a listener whenever the state changes.
   * @param listener Called after every change.
   * @returns A function that stops listening.
   */
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  /**
   * Sets what opens a page when Claude asks to show something.
   * @param navigator Opens a page address, or null to stop.
   */
  setNavigator(navigator: ((path: string) => void) | null): void {
    this.navigator = navigator;
  }

  /**
   * Opens a page address with the navigator, when one is set.
   * @param path The address.
   */
  navigate(path: string): void {
    this.navigator?.(path);
  }

  /** Reloads the conversation list and today's usage. */
  async refresh(): Promise<void> {
    try {
      const [conversations, usage] = await Promise.all([apiClient.listConversations(), apiClient.fetchChatUsage()]);
      this.update({
        conversations,
        usage,
      });
    } catch (caught) {
      this.update({
        error: caught instanceof ApiError ? caught.message : 'The conversations could not be loaded.',
      });
    }
  }

  /**
   * Opens a stored conversation.
   * @param conversationId The conversation's id.
   */
  async open(conversationId: string): Promise<void> {
    if (this.state.streaming) {
      return;
    }
    this.update({
      activeId: conversationId,
      items: [],
      loading: true,
      error: '',
    });
    try {
      const document = await apiClient.fetchConversation(conversationId);
      this.update({
        activeTitle: document.conversation.title,
        items: this.fromStored(document.items),
        loading: false,
      });
    } catch (caught) {
      this.update({
        loading: false,
        error: caught instanceof ApiError ? caught.message : 'The conversation could not be loaded.',
      });
    }
  }

  /** Clears the open conversation, so the next message starts a new one. */
  startNew(): void {
    if (this.state.streaming) {
      return;
    }
    this.update({
      activeId: null,
      activeTitle: 'New chat',
      items: [],
      error: '',
    });
  }

  /**
   * Sends a message and follows the answer until it ends.
   * @param text What the user wrote.
   * @param page The page the user is on.
   */
  async send(text: string, page: ChatPage): Promise<void> {
    const trimmed = text.trim();
    if (trimmed === '' || this.state.streaming) {
      return;
    }
    this.abortController = new AbortController();
    this.update({
      streaming: true,
      error: '',
      items: [
        ...this.state.items,
        {
          kind: 'user',
          key: this.nextKey(),
          text: trimmed,
        },
      ],
    });
    try {
      let conversationId = this.state.activeId;
      if (conversationId === null) {
        const created = await apiClient.createConversation();
        conversationId = created.conversation_id;
        this.update({
          activeId: conversationId,
          activeTitle: created.title,
        });
      }
      await apiClient.sendChatMessage(conversationId, trimmed, page, (event) => this.apply(event), this.abortController.signal);
    } catch (caught) {
      if (!this.abortController.signal.aborted) {
        this.addNotice('error', caught instanceof ApiError ? caught.message : 'The message could not be sent.');
      }
    } finally {
      this.abortController = null;
      this.update({
        streaming: false,
      });
      void this.refresh();
    }
  }

  /** Stops following the answer being streamed. */
  stop(): void {
    this.abortController?.abort();
    this.addNotice('error', 'Stopped. The part of the answer already written is kept.');
  }

  /**
   * Renames a conversation.
   * @param conversationId The conversation's id.
   * @param title The new title.
   */
  async rename(conversationId: string, title: string): Promise<void> {
    await apiClient.renameConversation(conversationId, title);
    if (conversationId === this.state.activeId) {
      this.update({
        activeTitle: title,
      });
    }
    await this.refresh();
  }

  /**
   * Deletes a conversation, clearing it when it is open.
   * @param conversationId The conversation's id.
   */
  async remove(conversationId: string): Promise<void> {
    await apiClient.deleteConversation(conversationId);
    if (conversationId === this.state.activeId) {
      this.startNew();
    }
    await this.refresh();
  }

  /**
   * Applies one streamed event to the items.
   * @param event The event.
   */
  private apply(event: ChatStreamEvent): void {
    if (event.type === 'text_start' || event.type === 'thinking_start') {
      this.pushItem({
        kind: event.type === 'text_start' ? 'text' : 'thinking',
        key: this.nextKey(),
        text: '',
      });
    } else if (event.type === 'text' || event.type === 'thinking') {
      this.appendText(event.type, event.text);
    } else if (event.type === 'tool_call') {
      this.upsertTool(event.id, (tool) => ({
        ...tool,
        name: event.name,
        input: event.input ?? tool.input,
      }));
    } else if (event.type === 'tool_result') {
      this.upsertTool(event.id, (tool) => ({
        ...tool,
        summary: event.summary,
        isError: event.is_error,
        done: true,
      }));
    } else if (event.type === 'ui_action') {
      this.upsertTool(event.id, (tool) => ({
        ...tool,
        uiAction: event.action,
      }));
      if (event.action.kind === 'navigate') {
        this.navigate(event.action.path);
      }
    } else if (event.type === 'title') {
      this.update({
        activeTitle: event.title,
      });
    } else if (event.type === 'usage') {
      if (this.state.usage !== null) {
        this.update({
          usage: {
            ...this.state.usage,
            billable: event.today,
          },
        });
      }
    } else if (event.type === 'error' || event.type === 'refusal') {
      this.addNotice(event.type, event.text);
    }
  }

  /**
   * Adds text to the last text or thinking item, starting one when there is none.
   * @param kind Which kind of item the text belongs to.
   * @param text The new text.
   */
  private appendText(kind: 'text' | 'thinking', text: string): void {
    const items = [...this.state.items];
    const last = items[items.length - 1];
    if (last !== undefined && last.kind === kind) {
      items[items.length - 1] = {
        ...last,
        text: last.text + text,
      };
      this.update({
        items,
      });
      return;
    }
    this.pushItem({
      kind,
      key: this.nextKey(),
      text,
    });
  }

  /**
   * Changes a tool item, adding it when it is new.
   * @param id The tool call's id.
   * @param change Makes the changed item from the current one.
   */
  private upsertTool(id: string, change: (tool: Extract<ChatItem, { kind: 'tool' }>) => Extract<ChatItem, { kind: 'tool' }>): void {
    const items = [...this.state.items];
    const position = items.findIndex((item) => item.kind === 'tool' && item.id === id);
    if (position >= 0) {
      items[position] = change(items[position] as Extract<ChatItem, { kind: 'tool' }>);
    } else {
      items.push(
        change({
          kind: 'tool',
          key: this.nextKey(),
          id,
          name: '',
          input: undefined,
          summary: '',
          isError: false,
          done: false,
          uiAction: null,
        }),
      );
    }
    this.update({
      items,
    });
  }

  /**
   * Adds an error or refusal notice.
   * @param tone Whether it is an error or a refusal.
   * @param text What to say.
   */
  private addNotice(tone: 'error' | 'refusal', text: string): void {
    this.pushItem({
      kind: 'notice',
      key: this.nextKey(),
      tone,
      text,
    });
  }

  /**
   * Adds an item at the end.
   * @param item The item.
   */
  private pushItem(item: ChatItem): void {
    this.update({
      items: [...this.state.items, item],
    });
  }

  /**
   * Turns stored items into chat items, joining each tool result to its call.
   * @param stored The stored items.
   * @returns The chat items.
   */
  private fromStored(stored: ChatStoredItem[]): ChatItem[] {
    const items: ChatItem[] = [];
    const tools = new Map<string, number>();
    for (const entry of stored) {
      if (entry.kind === 'tool_call') {
        tools.set(entry.id, items.length);
        items.push({
          kind: 'tool',
          key: this.nextKey(),
          id: entry.id,
          name: entry.name,
          input: entry.input,
          summary: '',
          isError: false,
          done: false,
          uiAction: null,
        });
      } else if (entry.kind === 'tool_result') {
        const position = tools.get(entry.id);
        if (position !== undefined) {
          const tool = items[position] as Extract<ChatItem, { kind: 'tool' }>;
          items[position] = {
            ...tool,
            summary: entry.summary,
            isError: entry.is_error,
            done: true,
            uiAction: entry.ui_action,
          };
        }
      } else {
        items.push({
          kind: entry.kind,
          key: this.nextKey(),
          text: entry.text,
        });
      }
    }
    return items;
  }

  /**
   * Makes a key for a new item.
   * @returns A key no other item has.
   */
  private nextKey(): string {
    this.keyCounter += 1;
    return `item-${this.keyCounter}`;
  }

  /**
   * Replaces part of the state and tells every listener.
   * @param changes The changed fields.
   */
  private update(changes: Partial<ChatState>): void {
    this.state = {
      ...this.state,
      ...changes,
    };
    for (const listener of this.listeners) {
      listener();
    }
  }
}

export const chatController = new ChatController();
