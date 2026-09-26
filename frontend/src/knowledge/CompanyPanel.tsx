import { type ChangeEvent, useCallback, useEffect, useMemo, useState } from 'react';

import { ApiError, apiClient } from '../api/apiClient';
import type { EarthCompany, FetchJob, InstrumentCompany, KnowledgeSource } from '../api/types';
import { TiltCard } from '../components/TiltCard';
import { liveSocket } from '../live/liveServices';
import { formatter } from '../utilities/formatter';
import { HeadquartersSection } from './HeadquartersSection';
import { JobProgress } from './JobProgress';
import { KeyPeopleSection } from './KeyPeopleSection';
import { KnowledgeSearch } from './KnowledgeSearch';

const DOCUMENTS_SHOWN = 12;

/** How one Yahoo fundamental is labelled and formatted. */
interface FundamentalFormat {
  label: string;
  format: (value: number) => string;
}

const FUNDAMENTALS: Record<string, FundamentalFormat> = {
  marketCap: {
    label: 'Market cap',
    format: (value) => `₹ ${formatter.count(Math.round(value / 1e7))} Cr`,
  },
  trailingPE: {
    label: 'P/E (trailing)',
    format: (value) => value.toFixed(1),
  },
  forwardPE: {
    label: 'P/E (forward)',
    format: (value) => value.toFixed(1),
  },
  priceToBook: {
    label: 'Price to book',
    format: (value) => value.toFixed(2),
  },
  dividendYield: {
    label: 'Dividend yield',
    format: (value) => `${value.toFixed(2)}%`,
  },
  profitMargins: {
    label: 'Profit margin',
    format: (value) => `${(value * 100).toFixed(1)}%`,
  },
  revenueGrowth: {
    label: 'Revenue growth',
    format: (value) => `${(value * 100).toFixed(1)}%`,
  },
  returnOnEquity: {
    label: 'Return on equity',
    format: (value) => `${(value * 100).toFixed(1)}%`,
  },
  debtToEquity: {
    label: 'Debt to equity',
    format: (value) => `${value.toFixed(0)}%`,
  },
  beta: {
    label: 'Beta',
    format: (value) => value.toFixed(2),
  },
};

/** Props for CompanyPanel. */
interface CompanyPanelProps {
  instrumentId: string;
}

/**
 * Everything known about an instrument's company: profile, ratios, strengths and weaknesses, documents, a question box, uploads, and a button to fetch more.
 * @param props The instrument.
 * @returns The panel, or a short note when the instrument is not a company.
 */
export function CompanyPanel(props: CompanyPanelProps) {
  const { instrumentId } = props;
  const [data, setData] = useState<InstrumentCompany | null>(null);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [job, setJob] = useState<FetchJob | null>(null);
  const [error, setError] = useState('');
  const [uploadMessage, setUploadMessage] = useState('');
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(() => {
    apiClient
      .fetchInstrumentCompany(instrumentId)
      .then((loaded) => {
        setData(loaded);
        setError('');
      })
      .catch((caught: unknown) => setError(caught instanceof ApiError ? caught.message : 'The company could not be loaded.'));
  }, [instrumentId]);

  useEffect(() => {
    setData(null);
    setJob(null);
    load();
  }, [load]);

  useEffect(() => {
    apiClient
      .fetchKnowledgeOverview()
      .then((overview) => {
        setSources(overview.sources);
        const available = new Set<string>();
        for (const source of overview.sources) {
          if (source.available) {
            available.add(source.key);
          }
        }
        setChosen(available);
      })
      .catch(() => undefined);
  }, []);

  const companyKey = data?.company?.company_key ?? null;

  const mapDot = useMemo((): EarthCompany | null => {
    const location = data?.headquarters?.location;
    if (data === null || data.company === null || location === undefined || location === null) {
      return null;
    }
    return {
      company_key: data.company.company_key,
      name: data.profile?.name ?? data.company.name,
      symbol: data.company.symbol,
      sector: data.profile?.sector ?? null,
      city: data.headquarters?.city ?? null,
      address: (data.headquarters?.address_lines ?? []).join(', '),
      latitude: location.latitude,
      longitude: location.longitude,
      precision: location.precision,
      instrument_id: instrumentId,
    };
  }, [data, instrumentId]);

  useEffect(() => {
    if (companyKey === null) {
      return undefined;
    }
    return liveSocket.onFetchJob((updated) => {
      if (updated.company.company_key !== companyKey) {
        return;
      }
      setJob(updated);
      if (updated.status === 'done' || updated.status === 'failed') {
        load();
      }
    });
  }, [companyKey, load]);

  const startFetch = () => {
    apiClient
      .startKnowledgeFetch(instrumentId, [...chosen])
      .then((started) => {
        setJob(started);
        setError('');
      })
      .catch((caught: unknown) => setError(caught instanceof ApiError ? caught.message : 'The fetch could not be started.'));
  };

  const toggleSource = (key: string) => {
    const next = new Set(chosen);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    setChosen(next);
  };

  const upload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file === undefined) {
      return;
    }
    setUploadMessage(`Reading ${file.name}…`);
    apiClient
      .uploadKnowledgeDocument(instrumentId, file)
      .then((stored) => {
        setUploadMessage(`Stored ${stored.title}: ${formatter.count(stored.characters)} characters in ${stored.chunks} searchable pieces.`);
        load();
      })
      .catch((caught: unknown) => setUploadMessage(caught instanceof ApiError ? caught.message : 'The upload failed.'));
  };

  if (error !== '' && data === null) {
    return (
      <TiltCard className="company-panel">
        <p className="error-text">{error}</p>
      </TiltCard>
    );
  }
  if (data === null) {
    return (
      <TiltCard className="company-panel">
        <p className="muted">Loading the company…</p>
      </TiltCard>
    );
  }
  if (data.company === null) {
    return (
      <TiltCard className="company-panel">
        <h2>Company</h2>
        <p className="muted">{data.reason}</p>
      </TiltCard>
    );
  }

  const profile = data.profile;
  const running = job !== null && (job.status === 'queued' || job.status === 'running');
  const fundamentals = Object.entries(profile?.fundamentals ?? {}).filter(([key]) => FUNDAMENTALS[key] !== undefined);
  const ratios = Object.entries(profile?.screener_ratios ?? {});
  const documents = showAll ? data.documents : data.documents.slice(0, DOCUMENTS_SHOWN);
  const fetchedBefore = profile?.sources !== undefined && Object.keys(profile.sources).length > 0;

  return (
    <div className="card company-panel">
      <div className="company-heading">
        <div>
          <h2 className="company-name">{profile?.name ?? data.company.name}</h2>
          <div className="company-facts">
            {data.company.isin ? <span className="chip mono">{data.company.isin}</span> : null}
            {profile?.classification !== undefined && profile.classification.length > 0 ? (
              <span className="company-classification">{profile.classification.join(' › ')}</span>
            ) : profile?.sector ? (
              <span className="company-classification">
                {profile.sector}
                {profile.industry ? ` › ${profile.industry}` : ''}
              </span>
            ) : null}
            {profile?.website ? (
              <a href={profile.website} target="_blank" rel="noreferrer">
                {profile.website.replace(/^https?:\/\//, '')}
              </a>
            ) : null}
            {profile?.employees ? <span className="muted">{formatter.count(profile.employees)} employees</span> : null}
            {profile?.listed_on ? <span className="muted">listed {formatter.date(profile.listed_on)}</span> : null}
          </div>
        </div>
        <div className="company-fetch">
          <div className="company-sources">
            {sources.map((source) => (
              <label key={source.key} className={`source-choice ${source.available ? '' : 'source-unavailable'}`} title={source.available ? source.description : source.reason}>
                <input type="checkbox" checked={chosen.has(source.key)} disabled={!source.available} onChange={() => toggleSource(source.key)} />
                {source.label}
              </label>
            ))}
          </div>
          <button type="button" className="button button-primary" onClick={startFetch} disabled={running || chosen.size === 0}>
            {running ? 'Fetching…' : fetchedBefore ? 'Fetch again' : 'Fetch company knowledge'}
          </button>
          {profile?.updated_at ? <span className="muted company-updated">Last fetched {formatter.dateTime(profile.updated_at)}</span> : null}
        </div>
      </div>
      {error !== '' ? <p className="error-text">{error}</p> : null}
      {job !== null ? <JobProgress job={job} showCompany={false} /> : null}
      {!fetchedBefore && job === null ? (
        <p className="muted">
          Nothing has been fetched for this company yet. Fetching reads NSE announcements, Yahoo Finance (with the headquarters and officers), Screener.in, the board of directors from the company registry, and news, which takes about thirty seconds.
        </p>
      ) : null}
      <div className="company-grid">
        {profile?.about ? (
          <section>
            <h3 className="section-heading">About</h3>
            <p>{profile.about}</p>
          </section>
        ) : null}
        {ratios.length > 0 || fundamentals.length > 0 ? (
          <section>
            <h3 className="section-heading">Ratios</h3>
            <dl className="figures figures-two">
              {ratios.map(([name, value]) => (
                <div key={`screener-${name}`}>
                  <dt>{name}</dt>
                  <dd className="mono">{value}</dd>
                </div>
              ))}
              {fundamentals.map(([key, value]) => (
                <div key={`yahoo-${key}`}>
                  <dt>{FUNDAMENTALS[key].label}</dt>
                  <dd className="mono">{FUNDAMENTALS[key].format(value)}</dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}
        {(profile?.pros?.length ?? 0) > 0 || (profile?.cons?.length ?? 0) > 0 ? (
          <section>
            <h3 className="section-heading">Strengths and weaknesses</h3>
            <ul className="pros-cons">
              {(profile?.pros ?? []).map((item) => (
                <li key={`pro-${item}`} className="pro">
                  {item}
                </li>
              ))}
              {(profile?.cons ?? []).map((item) => (
                <li key={`con-${item}`} className="con">
                  {item}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
      {data.headquarters !== null ? <HeadquartersSection headquarters={data.headquarters} company={mapDot} instrumentId={instrumentId} /> : null}
      {data.key_people !== null ? (
        <KeyPeopleSection
          instrumentId={instrumentId}
          keyPeople={data.key_people}
          uploads={data.documents.filter((document) => document.source === 'upload')}
          canRead={data.can_read_people}
          onChanged={load}
        />
      ) : null}
      <section className="company-ask">
        <h3 className="section-heading">Ask about {data.company.symbol}</h3>
        <KnowledgeSearch companyKey={data.company.company_key} placeholder="Such as “what does the company earn from telecom?” or “recent dividend”" />
      </section>
      <section>
        <div className="card-title">
          <h3 className="section-heading">Documents ({data.documents.length})</h3>
          <label className="button button-quiet upload-button">
            Upload a PDF, HTML or text file
            <input type="file" accept=".pdf,.html,.htm,.md,.txt" onChange={upload} hidden />
          </label>
        </div>
        {uploadMessage !== '' ? <p className="muted">{uploadMessage}</p> : null}
        <table className="data-table documents-table">
          <tbody>
            {documents.map((document) => (
              <tr key={document.document_id}>
                <td className="muted mono">{formatter.dateTime(document.published_at ?? document.fetched_at)}</td>
                <td>
                  <span className="chip chip-small">{formatter.source(document.source)}</span>
                </td>
                <td className="document-title">
                  {document.url ? (
                    <a href={document.url} target="_blank" rel="noreferrer">
                      {document.title}
                    </a>
                  ) : (
                    document.title
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.documents.length > DOCUMENTS_SHOWN ? (
          <button type="button" className="facet-more" onClick={() => setShowAll(!showAll)}>
            {showAll ? 'Show fewer' : `Show all ${data.documents.length}`}
          </button>
        ) : null}
      </section>
    </div>
  );
}
