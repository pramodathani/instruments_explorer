import { type PointerEvent, type ReactNode, useRef } from 'react';

import { useMotionLevel } from './useMotionLevel';

/** Props for TiltCard. */
interface TiltCardProps {
  className?: string;
  children: ReactNode;
}

const MAXIMUM_TILT_DEGREES = 9;

/**
 * A card that tilts toward the pointer in 3D with a moving glare, when the animation intensity is maximal.
 * @param props Extra class names and the card's contents.
 * @returns The card.
 */
export function TiltCard(props: TiltCardProps) {
  const { className, children } = props;
  const level = useMotionLevel();
  const cardReference = useRef<HTMLDivElement>(null);

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const card = cardReference.current;
    if (card === null || level !== 'maximal') {
      return;
    }
    const bounds = card.getBoundingClientRect();
    const across = (event.clientX - bounds.left) / bounds.width;
    const down = (event.clientY - bounds.top) / bounds.height;
    card.style.setProperty('--tilt-x', `${(0.5 - down) * MAXIMUM_TILT_DEGREES}deg`);
    card.style.setProperty('--tilt-y', `${(across - 0.5) * MAXIMUM_TILT_DEGREES * 1.2}deg`);
    card.style.setProperty('--glare-x', `${across * 100}%`);
    card.style.setProperty('--glare-y', `${down * 100}%`);
    card.style.setProperty('--glare-opacity', '1');
    card.classList.add('tilt-active');
  };

  const handlePointerLeave = () => {
    const card = cardReference.current;
    if (card === null) {
      return;
    }
    card.style.setProperty('--tilt-x', '0deg');
    card.style.setProperty('--tilt-y', '0deg');
    card.style.setProperty('--glare-opacity', '0');
    card.classList.remove('tilt-active');
  };

  return (
    <div
      ref={cardReference}
      className={`card tilt ${className ?? ''}`}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      {children}
    </div>
  );
}
