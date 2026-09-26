import { NavLink } from 'react-router';

import { Icon, type IconName } from '../components/Icon';
import { LogoMark } from '../components/LogoMark';
import { useMotionLevel } from '../components/useMotionLevel';
import { useTheme } from '../components/useTheme';
import { motionController } from '../utilities/motionController';
import { themeController } from '../utilities/themeController';

/** One tab in the header's navigation. */
interface NavigationItem {
  path: string;
  label: string;
  icon: IconName;
}

const NAVIGATION: NavigationItem[] = [
  {
    path: '/overview',
    label: 'Overview',
    icon: 'overview',
  },
  {
    path: '/explore',
    label: 'Explore',
    icon: 'explore',
  },
  {
    path: '/derivatives',
    label: 'Derivatives',
    icon: 'derivatives',
  },
  {
    path: '/universe',
    label: 'Universe',
    icon: 'universe',
  },
  {
    path: '/earth',
    label: 'Earth',
    icon: 'earth',
  },
  {
    path: '/screener',
    label: 'Screener',
    icon: 'screener',
  },
  {
    path: '/knowledge',
    label: 'Knowledge',
    icon: 'knowledge',
  },
];

const MOTION_LABELS = {
  maximal: 'Animation: maximal',
  reduced: 'Animation: reduced',
  off: 'Animation: off',
};

/** Props for Header. */
interface HeaderProps {
  chatOpen: boolean;
  onToggleChat: () => void;
  onLogOut: () => void;
}

/**
 * The sticky top bar: the mark, the page tabs, and the theme, animation, chat and logout controls.
 * @param props Whether the chat panel is open, and what to do for the chat and logout buttons.
 * @returns The header.
 */
export function Header(props: HeaderProps) {
  const { chatOpen, onToggleChat, onLogOut } = props;
  const theme = useTheme();
  const level = useMotionLevel();

  return (
    <header className="header">
      <NavLink to="/overview" className="brand">
        <LogoMark size={28} />
        <span className="brand-name">Instruments Explorer</span>
      </NavLink>
      <nav className="navigation" aria-label="Pages">
        {NAVIGATION.map((item) => (
          <NavLink key={item.path} to={item.path}>
            <Icon name={item.icon} size={16} />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="header-actions">
        <button
          type="button"
          className="icon-button"
          title={theme === 'dark' ? 'Switch to the light theme' : 'Switch to the dark theme'}
          aria-label={theme === 'dark' ? 'Switch to the light theme' : 'Switch to the dark theme'}
          onClick={() => themeController.toggle()}
        >
          <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
        </button>
        <button
          type="button"
          className="icon-button"
          title={`${MOTION_LABELS[level]}. Click to change.`}
          aria-label={`${MOTION_LABELS[level]}. Click to change.`}
          onClick={() => motionController.cycle()}
        >
          <Icon name="motion" />
        </button>
        <button
          type="button"
          className="icon-button"
          title="Chat with Claude"
          aria-label="Chat with Claude"
          aria-pressed={chatOpen}
          onClick={onToggleChat}
        >
          <Icon name="chat" />
        </button>
        <NavLink to="/settings" className="icon-button" title="Settings" aria-label="Settings">
          <Icon name="settings" />
        </NavLink>
        <button type="button" className="icon-button" title="Log out" aria-label="Log out" onClick={onLogOut}>
          <Icon name="logout" />
        </button>
      </div>
    </header>
  );
}
