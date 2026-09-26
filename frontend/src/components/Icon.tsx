/** The names of the icons the application draws. */
export type IconName =
  | 'overview'
  | 'explore'
  | 'derivatives'
  | 'universe'
  | 'screener'
  | 'knowledge'
  | 'chat'
  | 'sun'
  | 'moon'
  | 'motion'
  | 'logout'
  | 'close'
  | 'send'
  | 'settings'
  | 'expand'
  | 'earth';

const PATHS: Record<IconName, string> = {
  overview: 'M3 3h7v7H3zM14 3h7v4h-7zM14 11h7v10h-7zM3 14h7v7H3z',
  explore: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4',
  derivatives: 'M4 20V10M10 20V4M16 20v-8M22 20H2M4 10l6-6 6 8 5-5',
  universe: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18',
  screener: 'M3 5h18l-7 8v6l-4 2v-8z',
  knowledge: 'M4 4h6a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4zM20 4h-6a3 3 0 0 0-3 3',
  chat: 'M4 5h16v11H9l-5 4zM8 9h8M8 12h5',
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z',
  motion: 'M3 12c3-6 6-6 9 0s6 6 9 0M3 18c3-4 6-4 9 0M12 6c3-4 6-4 9 0',
  logout: 'M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10',
  close: 'M6 6l12 12M18 6 6 18',
  send: 'M4 12 20 4l-6 16-3-7z',
  earth: 'M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21zM12 7a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z',
  expand: 'M14 4h6v6M20 4l-7 7M10 20H4v-6M4 20l7-7',
  settings: 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1',
};

/** Props for Icon. */
interface IconProps {
  name: IconName;
  size?: number;
}

/**
 * A line icon drawn in the current text colour.
 * @param props The icon's name and size in pixels.
 * @returns The icon.
 */
export function Icon(props: IconProps) {
  const { name, size = 18 } = props;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
