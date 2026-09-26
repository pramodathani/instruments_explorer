import type { FetchJob } from '../api/types';
import { StatusBadge, type StatusKind } from '../components/StatusBadge';
import { formatter } from '../utilities/formatter';

const STEP_KINDS: Record<string, StatusKind> = {
  queued: 'neutral',
  running: 'warning',
  done: 'good',
  failed: 'critical',
  skipped: 'neutral',
};

/** Props for JobProgress. */
interface JobProgressProps {
  job: FetchJob;
  showCompany: boolean;
}

/**
 * A fetch job's steps, one line per source with its status and message.
 * @param props The job, and whether to name the company it is for.
 * @returns The job's progress.
 */
export function JobProgress(props: JobProgressProps) {
  const { job, showCompany } = props;
  return (
    <div className={`job job-${job.status}`}>
      <div className="job-heading">
        {showCompany ? <strong>{job.company.name}</strong> : <strong>Fetch</strong>}
        <span className="muted">
          {job.reason} · {formatter.dateTime(job.created_at)}
        </span>
        <StatusBadge kind={STEP_KINDS[job.status] ?? 'neutral'} label={job.status} />
      </div>
      <ul className="job-steps">
        {job.steps.map((step) => (
          <li key={step.source} className={`job-step job-step-${step.status}`}>
            <StatusBadge kind={STEP_KINDS[step.status] ?? 'neutral'} label={step.status} />
            <span className="job-step-label">{step.label}</span>
            <span className="muted job-step-message">
              {step.message}
              {step.status === 'done' && step.new > 0 ? ` · ${step.new} new` : ''}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
