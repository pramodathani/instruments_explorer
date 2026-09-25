import { useEffect, useRef } from 'react';

import type { AmbientFieldScene } from '../three/ambientFieldScene';
import { useMotionLevel } from './useMotionLevel';
import { useTheme } from './useTheme';

/** Props for AmbientBackground. */
interface AmbientBackgroundProps {
  pulseKey: string;
}

/**
 * The full-window three.js backdrop behind every page, rebuilt when the animation intensity changes.
 * @param props A key that starts a camera dolly whenever it changes, such as the current path.
 * @returns The fixed backdrop.
 */
export function AmbientBackground(props: AmbientBackgroundProps) {
  const { pulseKey } = props;
  const level = useMotionLevel();
  const theme = useTheme();
  const canvasReference = useRef<HTMLCanvasElement>(null);
  const sceneReference = useRef<AmbientFieldScene | null>(null);

  useEffect(() => {
    const canvas = canvasReference.current;
    if (level === 'off' || canvas === null) {
      return undefined;
    }
    let cancelled = false;
    let scene: AmbientFieldScene | null = null;
    const observer = new ResizeObserver(() => {
      scene?.resize(canvas.clientWidth, canvas.clientHeight);
    });
    import('../three/ambientFieldScene')
      .then((module) => {
        if (cancelled) {
          return;
        }
        scene = new module.AmbientFieldScene(canvas, level);
        sceneReference.current = scene;
        observer.observe(canvas);
        scene.resize(canvas.clientWidth, canvas.clientHeight);
        scene.start();
      })
      .catch(() => {
        scene = null;
      });
    return () => {
      cancelled = true;
      observer.disconnect();
      scene?.dispose();
      sceneReference.current = null;
    };
  }, [level]);

  useEffect(() => {
    sceneReference.current?.applyTheme();
  }, [theme]);

  useEffect(() => {
    sceneReference.current?.nudge();
  }, [pulseKey]);

  return (
    <div className="ambient-background" aria-hidden="true">
      {level === 'off' ? null : <canvas ref={canvasReference} />}
    </div>
  );
}
