/** How much animation the page shows. */
export type MotionLevel = 'maximal' | 'reduced' | 'off';

const STORAGE_KEY = 'instruments-explorer.motion';
const ORDER: MotionLevel[] = [
  'maximal',
  'reduced',
  'off',
];

/** Holds the animation intensity, starting reduced when the operating system asks for less motion, and says when it changes. */
export class MotionController {
  private readonly listeners = new Set<() => void>();

  /**
   * Finds the animation intensity in force now.
   * @returns The stored level, or the level the operating system suggests when none is stored.
   */
  currentLevel = (): MotionLevel => {
    const stored = this.storedLevel();
    if (stored !== null) {
      return stored;
    }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return 'reduced';
    }
    return 'maximal';
  };

  /**
   * Starts telling a listener whenever the level changes.
   * @param listener Called after every change.
   * @returns A function that stops listening.
   */
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  /** Marks the page with the level in force, so style sheets can follow it. */
  applyStoredChoice(): void {
    document.documentElement.dataset.motion = this.currentLevel();
  }

  /**
   * Moves to the next level: maximal, then reduced, then off, then maximal again.
   * @returns The level now in force.
   */
  cycle(): MotionLevel {
    const index = ORDER.indexOf(this.currentLevel());
    const next = ORDER[(index + 1) % ORDER.length];
    document.documentElement.dataset.motion = next;
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      document.documentElement.dataset.motion = next;
    }
    for (const listener of this.listeners) {
      listener();
    }
    return next;
  }

  /**
   * Reads the level stored by an earlier visit.
   * @returns The stored level, or null when none is stored or storage is unavailable.
   */
  private storedLevel(): MotionLevel | null {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === 'maximal' || stored === 'reduced' || stored === 'off') {
        return stored;
      }
    } catch {
      return null;
    }
    return null;
  }
}

export const motionController = new MotionController();
