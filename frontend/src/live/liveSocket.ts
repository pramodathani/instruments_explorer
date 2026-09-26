import { apiClient } from '../api/apiClient';
import type { Quote } from '../api/types';
import type { QuoteStore } from './quoteStore';

/** A message the server sends over /api/live. */
interface ServerMessage {
  type: string;
  quotes?: Quote[];
  message?: string;
}

const FIRST_RETRY_MILLISECONDS = 1000;
const LONGEST_RETRY_MILLISECONDS = 15000;
const PING_MILLISECONDS = 20000;

/** The browser's end of /api/live: reconnects by itself and counts who watches which instrument. */
export class LiveSocket {
  private socket: WebSocket | null = null;
  private counts = new Map<string, number>();
  private sent = new Set<string>();
  private retryMilliseconds = FIRST_RETRY_MILLISECONDS;
  private retryTimer: number | null = null;
  private pingTimer: number | null = null;
  private running = false;
  private onLoggedOut: () => void = () => undefined;
  private readonly quoteStore: QuoteStore;

  /**
   * Creates the socket without connecting.
   * @param quoteStore Receives every quote.
   */
  constructor(quoteStore: QuoteStore) {
    this.quoteStore = quoteStore;
  }

  /**
   * Connects, and keeps reconnecting until stopped.
   * @param onLoggedOut Called when the session turns out to have ended.
   */
  start(onLoggedOut: () => void): void {
    this.onLoggedOut = onLoggedOut;
    if (this.running) {
      return;
    }
    this.running = true;
    this.connect();
  }

  /** Disconnects and stops reconnecting. */
  stop(): void {
    this.running = false;
    if (this.retryTimer !== null) {
      window.clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    if (this.pingTimer !== null) {
      window.clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
    this.socket?.close();
    this.socket = null;
    this.sent.clear();
  }

  /**
   * Starts watching instruments; each call must be matched by a release.
   * @param instrumentIds The instruments.
   */
  retain(instrumentIds: string[]): void {
    for (const instrumentId of instrumentIds) {
      this.counts.set(instrumentId, (this.counts.get(instrumentId) ?? 0) + 1);
    }
    this.synchronise();
  }

  /**
   * Stops watching instruments retained earlier.
   * @param instrumentIds The instruments.
   */
  release(instrumentIds: string[]): void {
    for (const instrumentId of instrumentIds) {
      const count = (this.counts.get(instrumentId) ?? 0) - 1;
      if (count <= 0) {
        this.counts.delete(instrumentId);
      } else {
        this.counts.set(instrumentId, count);
      }
    }
    this.synchronise();
  }

  /** Opens the WebSocket and wires its events. */
  private connect(): void {
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${scheme}://${window.location.host}/api/live`);
    this.socket = socket;
    socket.addEventListener('open', () => {
      this.retryMilliseconds = FIRST_RETRY_MILLISECONDS;
      this.sent.clear();
      this.synchronise();
      this.pingTimer = window.setInterval(() => this.send({ type: 'ping' }), PING_MILLISECONDS);
    });
    socket.addEventListener('message', (event) => this.receive(event.data));
    socket.addEventListener('close', () => this.handleClose(socket));
  }

  /**
   * Handles a closed socket by checking the session and scheduling a reconnect.
   * @param socket The socket that closed.
   */
  private handleClose(socket: WebSocket): void {
    if (this.socket !== socket) {
      return;
    }
    this.socket = null;
    this.sent.clear();
    if (this.pingTimer !== null) {
      window.clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
    if (!this.running) {
      return;
    }
    apiClient
      .isLoggedIn()
      .then((loggedIn) => {
        if (!loggedIn) {
          this.stop();
          this.onLoggedOut();
        }
      })
      .catch(() => undefined);
    this.retryTimer = window.setTimeout(() => {
      this.retryTimer = null;
      if (this.running) {
        this.connect();
      }
    }, this.retryMilliseconds);
    this.retryMilliseconds = Math.min(this.retryMilliseconds * 2, LONGEST_RETRY_MILLISECONDS);
  }

  /**
   * Handles one message from the server.
   * @param data The message text.
   */
  private receive(data: unknown): void {
    if (typeof data !== 'string') {
      return;
    }
    let message: ServerMessage;
    try {
      message = JSON.parse(data) as ServerMessage;
    } catch {
      return;
    }
    if (message.type === 'quotes' && message.quotes !== undefined) {
      this.quoteStore.update(message.quotes);
    }
  }

  /** Tells the server which instruments are newly watched and which are no longer watched. */
  private synchronise(): void {
    if (this.socket === null || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }
    const added: string[] = [];
    for (const instrumentId of this.counts.keys()) {
      if (!this.sent.has(instrumentId)) {
        added.push(instrumentId);
        this.sent.add(instrumentId);
      }
    }
    const removed: string[] = [];
    for (const instrumentId of this.sent) {
      if (!this.counts.has(instrumentId)) {
        removed.push(instrumentId);
      }
    }
    for (const instrumentId of removed) {
      this.sent.delete(instrumentId);
    }
    if (added.length > 0) {
      this.send({
        type: 'subscribe',
        instrument_ids: added,
      });
    }
    if (removed.length > 0) {
      this.send({
        type: 'unsubscribe',
        instrument_ids: removed,
      });
    }
  }

  /**
   * Sends a message if the socket is open.
   * @param message The message.
   */
  private send(message: Record<string, unknown>): void {
    if (this.socket !== null && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }
}
