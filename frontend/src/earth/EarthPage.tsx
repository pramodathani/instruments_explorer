import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';

import { ApiError, apiClient } from '../api/apiClient';
import type { EarthCompanies, EarthCompany, LocateSweep } from '../api/types';
import { AnimatedNumber } from '../components/AnimatedNumber';
import { TiltCard } from '../components/TiltCard';
import { useMotionLevel } from '../components/useMotionLevel';
import { liveSocket } from '../live/liveServices';
import { formatter } from '../utilities/formatter';
import type { EarthMap } from './earthMap';

const MATCHES_SHOWN = 8;

/**
 * The Earth page: a satellite globe with a dot at each company's headquarters, a search that flies to one, and the sweep that locates every index company.
 * @returns The page.
 */
export function EarthPage() {
  const [query] = useSearchParams();
  const focusId = query.get('focus');
  const navigate = useNavigate();
  const level = useMotionLevel();
  const [data, setData] = useState<EarthCompanies | null>(null);
  const [sweep, setSweep] = useState<LocateSweep | null>(null);
  const [error, setError] = useState('');
  const [searchText, setSearchText] = useState('');
  const containerReference = useRef<HTMLDivElement>(null);
  const mapReference = useRef<EarthMap | null>(null);
  const companiesReference = useRef<EarthCompany[]>([]);

  const load = useCallback(() => {
    apiClient
      .fetchEarthCompanies()
      .then((loaded) => {
        setData(loaded);
        setSweep(loaded.sweep);
        companiesReference.current = loaded.companies;
        mapReference.current?.setCompanies(loaded.companies);
      })
      .catch((caught: unknown) => setError(caught instanceof ApiError ? caught.message : 'The companies could not be loaded.'));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    return liveSocket.onLocateJob((updated) => {
      setSweep(updated);
      if (updated.status !== 'running' || updated.done % 25 === 0) {
        load();
      }
    });
  }, [load]);

  useEffect(() => {
    const container = containerReference.current;
    if (container === null) {
      return undefined;
    }
    let cancelled = false;
    let map: EarthMap | null = null;
    const observer = new ResizeObserver(() => map?.resize());
    import('./earthMap')
      .then((module) => {
        if (cancelled) {
          return;
        }
        map = new module.EarthMap(
          container,
          level,
          {
            onOpen: (company) => {
              if (company.instrument_id !== null) {
                void navigate(`/instrument/${company.instrument_id}`);
              }
            },
          },
          null,
        );
        mapReference.current = map;
        map.setCompanies(companiesReference.current);
        observer.observe(container);
      })
      .catch(() => setError('This browser cannot draw the globe.'));
    return () => {
      cancelled = true;
      observer.disconnect();
      map?.dispose();
      mapReference.current = null;
    };
  }, [level, navigate]);

  useEffect(() => {
    if (data === null || focusId === null) {
      return undefined;
    }
    const company = data.companies.find((candidate) => candidate.instrument_id === focusId);
    if (company === undefined) {
      return undefined;
    }
    const timer = window.setTimeout(() => mapReference.current?.focus(company), 1200);
    return () => window.clearTimeout(timer);
  }, [data, focusId]);

  const matches = useMemo(() => {
    const text = searchText.trim().toLowerCase();
    if (data === null || text.length < 2) {
      return [];
    }
    const found: EarthCompany[] = [];
    for (const company of data.companies) {
      if (company.symbol.toLowerCase().startsWith(text) || company.name.toLowerCase().includes(text)) {
        found.push(company);
        if (found.length >= MATCHES_SHOWN) {
          break;
        }
      }
    }
    return found;
  }, [data, searchText]);

  const startSweep = () => {
    apiClient
      .startLocateSweep()
      .then(setSweep)
      .catch((caught: unknown) => setError(caught instanceof ApiError ? caught.message : 'Locating could not start.'));
  };

  const running = sweep !== null && sweep.status === 'running';
  const missing = data === null ? 0 : Math.max(data.index_companies - data.with_address, 0);

  return (
    <>
      <h1 className="page-title">Earth</h1>
      <p className="page-subtitle">Every company whose headquarters is known, on satellite imagery. Zoom into a cluster to separate its companies, and click a dot to read the address and open the company.</p>
      {data !== null && !data.geocoder_ready ? (
        <div className="card earth-notice">
          <strong>One download is needed to place the dots.</strong>
          <p>
            Headquarters are placed by postcode using GeoNames&apos; free list of Indian postcodes. Its site does not allow automated downloads, so please download it once by running this in the project folder:
          </p>
          <pre className="mono">
            mkdir -p data/geonames && curl -L -o data/geonames/IN.zip {data.download_url}
          </pre>
          <p className="muted">Then reload this page. {formatter.count(data.with_address)} companies already have an address waiting to be placed.</p>
        </div>
      ) : null}
      {error !== '' ? <p className="error-text">{error}</p> : null}
      {data !== null ? (
        <div className="grid grid-tiles section">
          <TiltCard className="stat-tile">
            <div className="tilt-lift">
              <div className="stat-label">On the globe</div>
              <div className="stat-value">
                <AnimatedNumber value={data.companies.length} />
              </div>
              <div className="stat-detail">of {formatter.count(data.with_address)} with an address</div>
            </div>
          </TiltCard>
          <TiltCard className="stat-tile">
            <div className="tilt-lift">
              <div className="stat-label">Index companies not yet located</div>
              <div className="stat-value">
                <AnimatedNumber value={missing} />
              </div>
              <div className="stat-detail">of {formatter.count(data.index_companies)} in the Nifty Total Market</div>
            </div>
          </TiltCard>
        </div>
      ) : null}
      <div className="card earth-toolbar">
        <div className="earth-search">
          <input className="input" type="search" placeholder="Fly to a company…" value={searchText} onChange={(event) => setSearchText(event.target.value)} />
          {matches.length > 0 ? (
            <ul className="universe-matches card">
              {matches.map((company) => (
                <li key={company.company_key}>
                  <button
                    type="button"
                    onClick={() => {
                      mapReference.current?.focus(company);
                      setSearchText('');
                    }}
                  >
                    {company.name}
                    <span className="muted"> {company.city}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <div className="earth-sweep">
          {running ? (
            <>
              <span>
                Locating: {formatter.count(sweep.done)} of {formatter.count(sweep.total - sweep.skipped)} · {formatter.count(sweep.located)} found
              </span>
              <div className="screener-progress">
                <span style={{ width: `${sweep.total > sweep.skipped ? (sweep.done / (sweep.total - sweep.skipped)) * 100 : 0}%` }} />
              </div>
            </>
          ) : sweep !== null ? (
            <span className="muted">
              Last run found {formatter.count(sweep.located)}
              {sweep.failed > 0 ? `, ${formatter.count(sweep.failed)} failed` : ''}
            </span>
          ) : null}
          <button type="button" className="button" onClick={startSweep} disabled={running || missing === 0} title="Reads Yahoo Finance's profile, which has the address and officers, for each index company not yet located, one every two seconds.">
            {running ? 'Locating…' : `Locate ${formatter.count(missing)} index companies`}
          </button>
        </div>
      </div>
      <div className="earth-view card" ref={containerReference} />
      <p className="muted earth-hint">Satellite imagery from Esri. Drag to turn the globe, scroll to zoom, right-drag to tilt.</p>
    </>
  );
}
