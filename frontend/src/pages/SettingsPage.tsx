import { StatusBadge } from '../components/StatusBadge';
import { TiltCard } from '../components/TiltCard';
import { useMotionLevel } from '../components/useMotionLevel';
import { useTheme } from '../components/useTheme';
import { useLayoutContext } from '../layout/layoutContext';
import { formatter } from '../utilities/formatter';
import { type MotionLevel, motionController } from '../utilities/motionController';
import { type Theme, themeController } from '../utilities/themeController';

/** One choice on the settings page. */
interface Choice<Value> {
  value: Value;
  label: string;
  description: string;
}

const THEMES: Choice<Theme>[] = [
  {
    value: 'dark',
    label: 'Dark',
    description: 'Charcoal pages with the deep orange accent. Easiest on the eyes for long sessions.',
  },
  {
    value: 'light',
    label: 'Light',
    description: 'White pages for bright rooms and for printing.',
  },
];

const MOTION_LEVELS: Choice<MotionLevel>[] = [
  {
    value: 'maximal',
    label: 'Maximal',
    description: 'The drifting particle field, tilting cards, scenes that turn by themselves, the universe unfolding, and camera flights.',
  },
  {
    value: 'reduced',
    label: 'Reduced',
    description: 'Scenes stay still until you move them, and the background moves less. Camera flights remain.',
  },
  {
    value: 'off',
    label: 'Off',
    description: 'No background animation, no tilt, and the camera jumps instead of flying. 3D views still work when you drag them.',
  },
];

/**
 * The settings page: theme, animation intensity, and the state of every connection.
 * @returns The page.
 */
export function SettingsPage() {
  const theme = useTheme();
  const level = useMotionLevel();
  const { status, refreshStatus } = useLayoutContext();

  return (
    <>
      <h1 className="page-title">Settings</h1>
      <p className="page-subtitle">These choices are kept in this browser, so each browser remembers its own.</p>
      <section className="section">
        <h2 className="section-heading">Theme</h2>
        <div className="settings-choices">
          {THEMES.map((choice) => (
            <TiltCard key={choice.value} className={`settings-choice ${theme === choice.value ? 'settings-chosen' : ''}`}>
              <button type="button" className="settings-choice-button" aria-pressed={theme === choice.value} onClick={() => themeController.apply(choice.value)}>
                <span className={`settings-swatch settings-swatch-${choice.value}`}>
                  <i />
                  <i />
                  <i />
                </span>
                <span className="settings-choice-label">{choice.label}</span>
                <span className="muted">{choice.description}</span>
              </button>
            </TiltCard>
          ))}
        </div>
      </section>
      <section className="section">
        <h2 className="section-heading">Animation</h2>
        <div className="settings-choices">
          {MOTION_LEVELS.map((choice) => (
            <TiltCard key={choice.value} className={`settings-choice ${level === choice.value ? 'settings-chosen' : ''}`}>
              <button type="button" className="settings-choice-button" aria-pressed={level === choice.value} onClick={() => motionController.apply(choice.value)}>
                <span className="settings-choice-label">{choice.label}</span>
                <span className="muted">{choice.description}</span>
              </button>
            </TiltCard>
          ))}
        </div>
      </section>
      <section className="section">
        <div className="card-title">
          <h2 className="section-heading">Connections</h2>
          <button type="button" className="button button-quiet" onClick={refreshStatus}>
            Check again
          </button>
        </div>
        <div className="card">
          {status === null ? (
            <p className="muted">Checking…</p>
          ) : (
            <table className="data-table">
              <tbody>
                {status.stores.map((store) => (
                  <tr key={store.name}>
                    <td>{store.name}</td>
                    <td>
                      <StatusBadge kind={store.reachable ? 'good' : 'critical'} label={store.reachable ? 'Reachable' : 'Unreachable'} />
                    </td>
                    <td className="muted">{store.detail}</td>
                  </tr>
                ))}
                <tr>
                  <td>Instrument index</td>
                  <td>
                    <StatusBadge kind={status.index.state === 'ready' ? 'good' : status.index.state === 'unavailable' ? 'critical' : 'warning'} label={status.index.state} />
                  </td>
                  <td className="muted">
                    {formatter.count(status.index.instrument_count)} instruments{status.index.mapping_date ? `, mapping ${status.index.mapping_date}` : ''}
                  </td>
                </tr>
                <tr>
                  <td>Claude assistant</td>
                  <td>
                    <StatusBadge kind={status.assistant.configured ? 'good' : 'warning'} label={status.assistant.configured ? 'Configured' : 'No API key'} />
                  </td>
                  <td className="muted mono">{status.assistant.model}</td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      </section>
    </>
  );
}
