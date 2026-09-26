import { Link } from 'react-router';

import { AnimatedNumber } from '../components/AnimatedNumber';
import { Icon, type IconName } from '../components/Icon';
import { StatusBadge } from '../components/StatusBadge';
import { TiltCard } from '../components/TiltCard';
import { useLayoutContext } from '../layout/layoutContext';
import { formatter } from '../utilities/formatter';

/** One way of exploring the instruments, shown as a card linking to its page. */
interface Feature {
  path: string;
  title: string;
  description: string;
  icon: IconName;
}

const FEATURES: Feature[] = [
  {
    path: '/explore',
    title: 'Search and browse',
    description: 'Full-text search with filters for asset class, exchange, segment, kind, option type, expiry month and strike.',
    icon: 'explore',
  },
  {
    path: '/derivatives',
    title: 'Derivatives tree',
    description: 'Walk from an underlying to its futures and options, with an option chain and a 3D volatility surface.',
    icon: 'derivatives',
  },
  {
    path: '/universe',
    title: '3D universe map',
    description: 'Fly through every instrument as a point in space, grouped by market and coloured by the day’s move.',
    icon: 'universe',
  },
  {
    path: '/screener',
    title: 'Screener and heatmap',
    description: 'Filter by TA-Lib indicators such as RSI and moving-average crossovers, then see the results by sector.',
    icon: 'screener',
  },
  {
    path: '/knowledge',
    title: 'Company knowledge',
    description: 'Profiles, fundamentals, news and your own documents, searchable by meaning through ChromaDB.',
    icon: 'knowledge',
  },
];

/**
 * The landing page: whether the project's stores and the assistant are ready, and the ways to explore.
 * @returns The overview page.
 */
export function OverviewPage() {
  const { status, openChat } = useLayoutContext();
  const stores = status === null ? [] : status.stores;
  const index = status === null ? null : status.index;
  let reachableCount = 0;
  for (const store of stores) {
    if (store.reachable) {
      reachableCount += 1;
    }
  }

  return (
    <>
      <h1 className="page-title">Overview</h1>
      <p className="page-subtitle">The state of the explorer’s own services, and the ways to explore the instruments.</p>
      <div className="grid grid-tiles">
        <TiltCard className="stat-tile">
          <div className="tilt-lift">
            <div className="stat-label">Services reachable</div>
            <div className="stat-value">
              <AnimatedNumber value={reachableCount} /> <span className="muted">/ {stores.length}</span>
            </div>
            <div className="stat-detail">ubi, MongoDB and ChromaDB</div>
          </div>
        </TiltCard>
        <TiltCard className="stat-tile">
          <div className="tilt-lift">
            <div className="card-title">
              <span className="stat-label">Instrument index</span>
              {index === null ? null : (
                <StatusBadge
                  kind={index.state === 'ready' ? 'good' : index.state === 'unavailable' ? 'critical' : 'warning'}
                  label={index.state}
                />
              )}
            </div>
            <div className="stat-value">
              <AnimatedNumber value={index?.instrument_count ?? 0} />
            </div>
            <div className="stat-detail">
              {index?.mapping_date ? `instruments in the catalogue of ${formatter.date(index.mapping_date)}` : 'not built yet'}
            </div>
          </div>
        </TiltCard>
        {stores.map((store) => (
          <TiltCard key={store.name} className="stat-tile">
            <div className="tilt-lift">
              <div className="card-title">
                <span className="stat-label">{store.name}</span>
                <StatusBadge
                  kind={store.reachable ? 'good' : 'critical'}
                  label={store.reachable ? 'Reachable' : 'Unreachable'}
                />
              </div>
              <div className="stat-detail mono">{store.detail}</div>
            </div>
          </TiltCard>
        ))}
        <TiltCard className="stat-tile">
          <div className="tilt-lift">
            <div className="card-title">
              <span className="stat-label">Chat assistant</span>
              {status === null ? null : (
                <StatusBadge
                  kind={status.assistant.configured ? 'good' : 'warning'}
                  label={status.assistant.configured ? 'Key found' : 'Needs a key'}
                />
              )}
            </div>
            <div className="stat-detail mono">{status === null ? '…' : status.assistant.model}</div>
            <button type="button" className="button button-quiet" style={{ marginTop: 8 }} onClick={openChat}>
              Open the chat
            </button>
          </div>
        </TiltCard>
      </div>
      <section className="section">
        <h2>Ways to explore</h2>
        <div className="grid grid-cards">
          {FEATURES.map((feature) => (
            <Link key={feature.path} to={feature.path} className="feature-card-link">
              <TiltCard className="feature-card">
                <div className="tilt-lift">
                  <div className="feature-icon">
                    <Icon name={feature.icon} size={22} />
                  </div>
                  <h3 style={{ marginTop: 12 }}>{feature.title}</h3>
                  <p className="muted">{feature.description}</p>
                </div>
              </TiltCard>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
