export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'instruments-explorer.theme';

/** Chooses light or dark, starting dark until the user picks light, and says when that changes. */
export class ThemeController {
  private readonly listeners = new Set<() => void>();

  /**
   * Finds the theme the page is showing now.
   * @returns The stored theme, or dark when none was chosen.
   */
  currentTheme = (): Theme => {
    return this.storedTheme() ?? 'dark';
  };

  /**
   * Starts telling a listener whenever the theme changes.
   * @param listener Called after every change.
   * @returns A function that stops listening.
   */
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  /** Applies the stored choice to the page before the first render. */
  applyStoredChoice(): void {
    document.documentElement.dataset.theme = this.currentTheme();
  }

  /**
   * Applies a theme to the page and remembers it for the next load.
   * @param theme The theme to show.
   */
  apply(theme: Theme): void {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      document.documentElement.dataset.theme = theme;
    }
    for (const listener of this.listeners) {
      listener();
    }
  }

  /**
   * Switches to the other theme and remembers the choice.
   * @returns The theme now shown.
   */
  toggle(): Theme {
    const next: Theme = this.currentTheme() === 'dark' ? 'light' : 'dark';
    this.apply(next);
    return next;
  }

  /**
   * Reads the theme stored by an earlier visit.
   * @returns The stored theme, or null when none is stored or storage is unavailable.
   */
  private storedTheme(): Theme | null {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === 'light' || stored === 'dark') {
        return stored;
      }
    } catch {
      return null;
    }
    return null;
  }
}

export const themeController = new ThemeController();
