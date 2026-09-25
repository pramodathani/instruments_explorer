import { useSyncExternalStore } from 'react';

import { type Theme, themeController } from '../utilities/themeController';

/**
 * Follows the theme, re-rendering when it changes.
 * @returns The theme shown.
 */
export function useTheme(): Theme {
  return useSyncExternalStore(themeController.subscribe, themeController.currentTheme);
}
