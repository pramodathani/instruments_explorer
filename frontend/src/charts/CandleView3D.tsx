import { useEffect, useRef } from 'react';

import type { CandleRow } from '../api/types';
import { useMotionLevel } from '../components/useMotionLevel';
import { useTheme } from '../components/useTheme';
import type { CandleScene } from '../three/candleScene';

/** Props for CandleView3D. */
interface CandleView3DProps {
  candles: CandleRow[];
}

/**
 * The 3D candle view, loading three.js's scene on demand.
 * @param props The candles to show.
 * @returns The canvas the scene draws on.
 */
export function CandleView3D(props: CandleView3DProps) {
  const { candles } = props;
  const level = useMotionLevel();
  const theme = useTheme();
  const canvasReference = useRef<HTMLCanvasElement>(null);
  const sceneReference = useRef<CandleScene | null>(null);
  const candlesReference = useRef(candles);
  candlesReference.current = candles;

  useEffect(() => {
    const canvas = canvasReference.current;
    if (canvas === null) {
      return undefined;
    }
    let cancelled = false;
    let scene: CandleScene | null = null;
    const observer = new ResizeObserver(() => {
      scene?.resize(canvas.clientWidth, canvas.clientHeight);
    });
    import('../three/candleScene')
      .then((module) => {
        if (cancelled) {
          return;
        }
        scene = new module.CandleScene(canvas, level);
        sceneReference.current = scene;
        scene.setCandles(candlesReference.current);
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
    sceneReference.current?.setCandles(candles);
  }, [candles]);

  useEffect(() => {
    sceneReference.current?.applyTheme();
  }, [theme]);

  return (
    <div className="candle-view-3d">
      <canvas ref={canvasReference} />
      <p className="candle-view-hint muted">Drag to orbit, scroll to zoom. The accent line is the 20-candle average.</p>
    </div>
  );
}
