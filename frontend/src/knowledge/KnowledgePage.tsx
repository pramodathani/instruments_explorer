import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router';

import { ApiError, apiClient } from '../api/apiClient';
import type { CompanyProfile, FetchJob, KnowledgeOverview } from '../api/types';
import { AnimatedNumber } from '../components/AnimatedNumber';
import { StatusBadge } from '../components/StatusBadge';
import { TiltCard } from '../components/TiltCard';
import { liveSocket } from '../live/liveServices';
import { formatter } from '../utilities/formatter';
import { JobProgress } from './JobProgress';
import { KnowledgeSearch } from './KnowledgeSearch';

/**
 * The knowledge page: what is stored, where it comes from, search by meaning across every company, and the latest fetch jobs.
 * @returns The page.
 */
export function KnowledgePage() {
  const [overview, setOverview] = useState<KnowledgeOverview | null>(null);
  const [companies, setCompanies] = useState<CompanyProfile[]>([]);
  const [jobs, setJobs] = useState<FetchJob[]>([]);
  const [message, setMessage] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(() => {
    apiClient
      .fetchKnowledgeOverview()
      .then((loaded) => {
        setOverview(loaded);
        setJobs(loaded.jobs);
      })
      .catch((caught: unknown) => setMessage(caught instanceof ApiError ? caught.message : 'The overview could not be loaded.'));
    apiClient
      .fetchCompanies('')
      .then(setCompanies)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    return liveSocket.onFetchJob((updated) => {
      setJobs((current) => {
        const others = current.filter((job) => job.job_id !== updated.job_id);
        return [updated, ...others].sort((first, second) => second.created_at - first.created_at).slice(0, 20);
      });
      if (updated.status === 'done' || updated.status === 'failed') {
        load();
      }
    });
  }, [load]);

  const refreshListing = () => {
    setRefreshing(true);
    setMessage('Reading NSE’s list of listed equities…');
    apiClient
      .refreshListing()
      .then((count) => {
        setMessage(`Imported ${formatter.count(count)} companies. The instrument search is being rebuilt with their names.`);
        load();
      })
      .catch((caught: unknown) => setMessage(caught instanceof ApiError ? caught.message : 'The import failed.'))
      .finally(() => setRefreshing(false));
  };

  const counts = overview?.counts;

  return (
    <>
      <h1 className="page-title">Knowledge</h1>
      <p className="page-subtitle">
        Company knowledge gathered from NSE, Yahoo Finance, Screener.in, news and your own documents, stored in MongoDB and searchable by meaning through ChromaDB. Open any company’s instrument page to fetch its knowledge.
      </p>
      <div className="grid grid-tiles">
        <TiltCard className="stat-tile">
          <div className="tilt-lift">
            <div className="stat-label">Listed companies</div>
            <div className="stat-value">{counts ? <AnimatedNumber value={counts.listed} /> : '…'}</div>
            <div className="stat-detail">from NSE’s equity list</div>
          </div>
        </TiltCard>
        <TiltCard className="stat-tile">
          <div className="tilt-lift">
            <div className="stat-label">Companies fetched</div>
            <div className="stat-value">{counts ? <AnimatedNumber value={counts.fetched} /> : '…'}</div>
            <div className="stat-detail">with knowledge from at least one source</div>
          </div>
        </TiltCard>
        <TiltCard className="stat-tile">
          <div className="tilt-lift">
            <div className="stat-label">Documents</div>
            <div className="stat-value">{counts ? <AnimatedNumber value={counts.documents} /> : '…'}</div>
            <div className="stat-detail">in MongoDB</div>
          </div>
        </TiltCard>
        <TiltCard className="stat-tile">
          <div className="tilt-lift">
            <div className="stat-label">Searchable passages</div>
            <div className="stat-value">{counts ? counts.chunks === null ? '–' : <AnimatedNumber value={counts.chunks} /> : '…'}</div>
            <div className="stat-detail">{counts && counts.chunks === null ? 'ChromaDB is unreachable' : 'embedded in ChromaDB'}</div>
          </div>
        </TiltCard>
      </div>
      <section className="section card knowledge-search-card">
        <h2>Search every company by meaning</h2>
        <KnowledgeSearch companyKey={null} placeholder="Such as “companies building solar capacity” or “credit rating downgrade”" />
      </section>
      <div className="knowledge-columns section">
        <section className="card">
          <div className="card-title">
            <h2>Recent fetches</h2>
          </div>
          {jobs.length === 0 ? <p className="muted">No fetches yet.</p> : null}
          <div className="job-list">
            {jobs.map((job) => (
              <JobProgress key={job.job_id} job={job} showCompany />
            ))}
          </div>
        </section>
        <div className="knowledge-side">
          <section className="card">
            <div className="card-title">
              <h2>Sources</h2>
              <button type="button" className="button button-quiet" onClick={refreshListing} disabled={refreshing}>
                Refresh NSE list
              </button>
            </div>
            {message !== '' ? <p className="muted">{message}</p> : null}
            <ul className="source-list">
              {(overview?.sources ?? []).map((source) => (
                <li key={source.key}>
                  <div className="card-title">
                    <strong>{source.label}</strong>
                    <StatusBadge kind={source.available ? 'good' : 'warning'} label={source.available ? 'on' : 'off'} />
                  </div>
                  <p className="muted">{source.available ? source.description : source.reason}</p>
                </li>
              ))}
            </ul>
          </section>
          <section className="card">
            <h2>Fetched companies</h2>
            {companies.length === 0 ? <p className="muted">None yet.</p> : null}
            <ul className="fetched-companies">
              {companies.map((company) => (
                <li key={company.company_key}>
                  <Link to={`/explore?q=${encodeURIComponent(company.symbol ?? '')}&shape=security`}>{company.name ?? company.symbol}</Link>
                  <span className="muted">
                    {company.classification?.[0] ?? company.sector ?? ''} · {formatter.dateTime(company.updated_at)}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}
