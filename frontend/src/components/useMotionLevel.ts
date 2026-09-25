import { useSyncExternalStore } from 'react';

import { type MotionLevel, motionController } from '../utilities/motionController';

/**
 * Follows the animation intensity, re-rendering when it changes.
 * @returns The level in force.
 */
export function useMotionLevel(): MotionLevel {
  return useSyncExternalStore(motionController.subscribe, motionController.currentLevel);
}
