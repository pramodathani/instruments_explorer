import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';

import { ApiError, apiClient } from '../api/apiClient';
import type { UniverseMap } from '../api/types';
import { useMotionLevel } from '../components/useMotionLevel';
import { useTheme } from '../components/useTheme';
import type { UniverseColouring, UniverseScene } from '../three/universeScene';
import { formatter } from '../utilities/formatter';

const SHAPE_NAMES = [
  'Cash',
  'Future',
  'Option',
];

const COLOURINGS: {
  key: UniverseColouring;
  label: string;
}[] = [
  {
    key: 'change',
    label: 'Day’s change',
  },
  {
    key: 'asset_class',
    label: 'Asset class',
  },
  {
    key: 'shape',
    label: 'Cash, future or option',
  },
];

const PALETTE_VARIABLES = [
  'var(--accent)',
  'var(--second)',
  'var(--up)',
  'var(--warning)',
  '#b388ff',
  'var(--ink-muted)',
];

const MATCHES_SHOWN = 8;

/** Where the hover card is drawn and which point it describes. */
interface Hover {
  index: number;
  x: number;
  y: number;
}

/**
 * The universe page: every instrument as a point in a 3D scene to fly through, with search, colourings and a card for the chosen instrument.
 * @returns The page.
 */
export function UniversePage() {
  const [query, setQuery] = useSearchParams();
  const includeOptions = query.get('options') === 'true';
  const focusId = query.get('focus');
  const level = useMotionLevel();
  const theme = useTheme();
  const [map, setMap] = useState<UniverseMap | null>(null);
  const [error, setError] = useState('');
  const [colouring, setColouring] = useState<UniverseColouring>('change');
  const [hover, setHover] = useState<Hover | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [searchText, setSearchText] = useState('');
  const canvasReference = useRef<HTMLCanvasElement>(null);
  const sceneReference = useRef<UniverseScene | null>(null);
  const mapReference = useRef<UniverseMap | null>(null);
  const colouringReference = useRef(colouring);
  colouringReference.current = colouring;

  useEffect(() => {
    const controller = new AbortController();
    setMap(null);
    setError('');
    apiClient
      .fetchUniverse(includeOptions, controller.signal)
      .then(setMap)
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof ApiError ? caught.message : 'The universe could not be loaded.');
        }
      });
    return () => controller.abort();
  }, [includeOptions]);

  const choose = useCallback((index: number) => {
    setSelected(index);
    sceneReference.current?.flyTo(index);
  }, []);

  useEffect(() => {
    const canvas = canvasReference.current;
    if (canvas === null) {
      return undefined;
    }
    let cancelled = false;
    let scene: UniverseScene | null = null;
    const observer = new ResizeObserver(() => {
      scene?.resize(canvas.clientWidth, canvas.clientHeight);
    });
    import('../three/universeScene')
      .then((module) => {
        if (cancelled) {
          return;
        }
        const created = new module.UniverseScene(canvas, level, {
          onHover: (index, x, y) => setHover(index === null ? null : { index, x, y }),
          onSelect: (index) => {
            setSelected(index);
            sceneReference.current?.flyTo(index);
          },
        });
        scene = created;
        sceneReference.current = created;
        created.resize(canvas.clientWidth, canvas.clientHeight);
        if (mapReference.current !== null) {
          created.setMap(mapReference.current);
          created.setColouring(colouringReference.current);
        }
        observer.observe(canvas);
        created.start();
      })
      .catch(() => setError('This browser cannot draw 3D scenes.'));
    return () => {
      cancelled = true;
      observer.disconnect();
      scene?.dispose();
      sceneReference.current = null;
    };
  }, [level]);

  useEffect(() => {
    mapReference.current = map;
    setSelected(null);
    setHover(null);
    if (map !== null) {
      sceneReference.current?.setMap(map);
      sceneReference.current?.setColouring(colouringReference.current);
    }
  }, [map]);

  useEffect(() => {
    if (map === null || focusId === null) {
      return;
    }
    const index = map.ids.indexOf(focusId);
    if (index >= 0) {
      const timer = window.setTimeout(() => choose(index), level === 'maximal' ? 2600 : 200);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [map, focusId, choose, level]);

  useEffect(() => {
    sceneReference.current?.setColouring(colouring);
  }, [colouring]);

  useEffect(() => {
    sceneReference.current?.applyTheme();
  }, [theme]);

  const matches = useMemo(() => {
    const text = searchText.trim().toLowerCase();
    if (map === null || text.length < 2) {
      return [];
    }
    const found: number[] = [];
    const startsWith: number[] = [];
    for (let index = 0; index < map.names.length && startsWith.length < MATCHES_SHOWN; index += 1) {
      const name = map.names[index].toLowerCase();
      if (name.startsWith(text)) {
        startsWith.push(index);
      } else if (found.length < MATCHES_SHOWN && name.includes(text)) {
        found.push(index);
      }
    }
    return [...startsWith, ...found].slice(0, MATCHES_SHOWN);
  }, [map, searchText]);

  const setIncludeOptions = (include: boolean) => {
    const next = new URLSearchParams(query);
    next.delete('focus');
    if (include) {
      next.set('options', 'true');
    } else {
      next.delete('options');
    }
    setQuery(next, {
      replace: true,
    });
  };

  const describe = (index: number) => {
    if (map === null) {
      return null;
    }
    const change = map.changes[index];
    return (
      <>
        <div className="universe-card-name">{map.names[index]}</div>
        <div className="universe-card-facts muted">
          {map.exchanges[index].toUpperCase()} · {SHAPE_NAMES[map.shapes[index]]} · {map.asset_class_names[map.asset_classes[index]].replace('_', ' ')}
        </div>
        <div className={`mono ${formatter.changeClass(change)}`}>{change === null ? 'No quote today' : formatter.signedPercent(change)}</div>
      </>
    );
  };

  return (
    <>
      <h1 className="page-title">Universe</h1>
      <p className="page-subtitle">
        Every instrument is a point. Asset classes are galaxies on a ring, each underlying is a cluster with the largest in the middle, and futures and options orbit their underlying with calls above and puts below.
      </p>
      <div className="universe-toolbar card">
        <div className="segmented" role="group" aria-label="Instruments shown">
          <button type="button" className={includeOptions ? '' : 'segmented-active'} onClick={() => setIncludeOptions(false)}>
            Without options
          </button>
          <button type="button" className={includeOptions ? 'segmented-active' : ''} onClick={() => setIncludeOptions(true)}>
            With options
          </button>
        </div>
        <div className="segmented" role="group" aria-label="Colour by">
          {COLOURINGS.map((entry) => (
            <button key={entry.key} type="button" className={entry.key === colouring ? 'segmented-active' : ''} onClick={() => setColouring(entry.key)}>
              {entry.label}
            </button>
          ))}
        </div>
        <div className="universe-search">
          <input className="input" type="search" placeholder="Fly to an instrument…" value={searchText} onChange={(event) => setSearchText(event.target.value)} />
          {matches.length > 0 ? (
            <ul className="universe-matches card">
              {matches.map((index) => (
                <li key={map?.ids[index]}>
                  <button
                    type="button"
                    onClick={() => {
                      choose(index);
                      setSearchText('');
                    }}
                  >
                    {map?.names[index]}
                    <span className="muted"> {map?.exchanges[index].toUpperCase()}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
      {error !== '' ? <p className="error-text">{error}</p> : null}
      <div className="universe-view card">
        <canvas ref={canvasReference} />
        {map === null && error === '' ? <p className="universe-loading muted">Laying out the universe…</p> : null}
        {map !== null ? (
          <div className="universe-overlay">
            <div className="universe-galaxies">
              <button type="button" className="chip" onClick={() => sceneReference.current?.flyHome()}>
                All
              </button>
              {map.galaxies.map((galaxy) => (
                <button key={galaxy.label} type="button" className="chip" onClick={() => sceneReference.current?.flyToLabel(galaxy)}>
                  {galaxy.label.replace('_', ' ')} <span className="muted">{formatter.count(galaxy.count)}</span>
                </button>
              ))}
            </div>
            <div className="universe-stats muted">
              {formatter.count(map.ids.length)} instruments · {formatter.count(map.quoted)} with a quote today · mapping {map.mapping_date}
            </div>
            <div className="universe-legend">
              {colouring === 'change' ? (
                <>
                  <span className="legend-item">
                    <i style={{ background: 'var(--down)' }} /> falling
                  </span>
                  <span className="legend-item">
                    <i style={{ background: 'var(--ink-faint)' }} /> flat
                  </span>
                  <span className="legend-item">
                    <i style={{ background: 'var(--up)' }} /> rising
                  </span>
                  <span className="muted">full colour at ±3%</span>
                </>
              ) : (
                (colouring === 'shape' ? SHAPE_NAMES : map.asset_class_names).map((name, position) => (
                  <span key={name} className="legend-item">
                    <i style={{ background: PALETTE_VARIABLES[position % PALETTE_VARIABLES.length] }} /> {name.replace('_', ' ')}
                  </span>
                ))
              )}
            </div>
          </div>
        ) : null}
        {selected !== null && map !== null ? (
          <div className="universe-selected card">
            {describe(selected)}
            <div className="universe-card-actions">
              <Link className="button button-primary" to={`/instrument/${map.ids[selected]}`}>
                Open
              </Link>
              <button type="button" className="button button-quiet" onClick={() => setSelected(null)}>
                Close
              </button>
            </div>
          </div>
        ) : null}
      </div>
      {hover !== null && map !== null ? (
        <div className="universe-hover card" style={{ left: hover.x + 14, top: hover.y + 14 }}>
          {describe(hover.index)}
        </div>
      ) : null}
      <p className="muted universe-hint">Drag to orbit, scroll to zoom, right-drag to pan. Hover a point to read it and click to choose it.</p>
    </>
  );
}
