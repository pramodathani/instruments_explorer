/** Props for LogoMark. */
interface LogoMarkProps {
  size: number;
}

/**
 * The application's mark: a ring with a small body orbiting it.
 * @param props The mark's size in pixels.
 * @returns The mark.
 */
export function LogoMark(props: LogoMarkProps) {
  const { size } = props;
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="logo-mark">
      <circle cx="16" cy="16" r="9" fill="none" stroke="var(--accent)" strokeWidth="2.5" />
      <circle cx="16" cy="16" r="3" fill="var(--second)" />
      <g className="logo-orbit">
        <circle cx="16" cy="3.5" r="2.2" fill="var(--accent)" />
      </g>
    </svg>
  );
}
