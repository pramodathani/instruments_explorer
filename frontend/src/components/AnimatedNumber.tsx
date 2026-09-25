import { useEffect, useRef, useState } from 'react';

import { useMotionLevel } from './useMotionLevel';

/** Props for AnimatedNumber. */
interface AnimatedNumberProps {
  value: number;
  decimals?: number;
}

const DURATION_MILLISECONDS = 900;

/**
 * A number that counts up or down to each new value, or jumps straight there when animation is reduced or off.
 * @param props The value to show and how many decimal places to print.
 * @returns The formatted number.
 */
export function AnimatedNumber(props: AnimatedNumberProps) {
  const { value, decimals = 0 } = props;
  const level = useMotionLevel();
  const [shown, setShown] = useState(level === 'maximal' ? 0 : value);
  const shownReference = useRef(shown);

  useEffect(() => {
    if (level !== 'maximal') {
      shownReference.current = value;
      setShown(value);
      return undefined;
    }
    const startValue = shownReference.current;
    const startTime = performance.now();
    let frameRequest = 0;
    const step = (time: number) => {
      const progress = Math.min((time - startTime) / DURATION_MILLISECONDS, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const next = startValue + (value - startValue) * eased;
      shownReference.current = next;
      setShown(next);
      if (progress < 1) {
        frameRequest = requestAnimationFrame(step);
      }
    };
    frameRequest = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameRequest);
  }, [value, level]);

  return (
    <>
      {shown.toLocaleString('en-IN', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
    </>
  );
}
