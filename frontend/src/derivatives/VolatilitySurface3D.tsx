import { useEffect, useRef } from 'react';

import type { VolatilitySurface } from '../api/types';
import { useMotionLevel } from '../components/useMotionLevel';
import { useTheme } from '../components/useTheme';
import type { SurfaceScene } from '../three/surfaceScene';

/** Props for VolatilitySurface3D. */
interface VolatilitySurface3DProps {
  surface: VolatilitySurface;
}

/**
 * The 3D volatility surface, loading its three.js scene on demand.
 * @param props The surface to show.
 * @returns The canvas the scene draws on.
 */
export function VolatilitySurface3D(props: VolatilitySurface3DProps) {
  const { surface } = props;
  const level = useMotionLevel();
  const theme = useTheme();
  const canvasReference = useRef<HTMLCanvasElement>(null);
  const sceneReference = useRef<SurfaceScene | null>(null);
  const surfaceReference = useRef(surface);
  surfaceReference.current = surface;

  useEffect(() => {
    const canvas = canvasReference.current;
    if (canvas === null) {
      return undefined;
    }
    let cancelled = false;
    let scene: SurfaceScene | null = null;
    const observer = new ResizeObserver(() => {
      scene?.resize(canvas.clientWidth, canvas.clientHeight);
    });
    import('../three/surfaceScene')
      .then((module) => {
        if (cancelled) {
          return;
        }
        scene = new module.SurfaceScene(canvas, level);
        sceneReference.current = scene;
        scene.setSurface(surfaceReference.current);
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
    sceneReference.current?.setSurface(surface);
  }, [surface]);

  useEffect(() => {
    sceneReference.current?.applyTheme();
  }, [theme]);

  return (
    <div className="surface-view-3d">
      <canvas ref={canvasReference} />
      <p className="candle-view-hint muted">
        Strike runs across, expiry runs back from the nearest, and height and colour show implied volatility. Drag to orbit, scroll to zoom.
      </p>
    </div>
  );
}
