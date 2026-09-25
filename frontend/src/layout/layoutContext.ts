import { useOutletContext } from 'react-router';

import type { StatusDocument } from '../api/types';

/** What the layout shares with every page. */
export interface LayoutContext {
  status: StatusDocument | null;
  refreshStatus: () => void;
  openChat: () => void;
}

/**
 * Reads what the layout shares with pages.
 * @returns The layout context.
 */
export function useLayoutContext(): LayoutContext {
  return useOutletContext<LayoutContext>();
}
