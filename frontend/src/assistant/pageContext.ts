import type { ChatPage } from './chatController';

/** Describes the page the user is on, for the context Claude receives with each message. */
export class PageContextReader {
  /**
   * Reads the page's address and heading.
   * @returns The address with its query, and the page title shown in the content area.
   */
  read(): ChatPage {
    const heading = document.querySelector('.content .page-title');
    return {
      path: `${window.location.pathname}${window.location.search}`,
      title: heading?.textContent?.trim() ?? '',
    };
  }
}

export const pageContextReader = new PageContextReader();
