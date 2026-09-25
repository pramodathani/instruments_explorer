/** The kinds of status a badge can show; each has its own shape so colour is never the only signal. */
export type StatusKind = 'good' | 'warning' | 'critical' | 'neutral';

/** Props for StatusIcon. */
interface StatusIconProps {
  kind: StatusKind;
}

/**
 * The shape for a status: a ticked circle, a triangle, an octagon with a cross, or a hollow circle with a dash.
 * @param props The status kind.
 * @returns The icon.
 */
export function StatusIcon(props: StatusIconProps) {
  const { kind } = props;
  if (kind === 'good') {
    return (
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <circle cx="6" cy="6" r="6" fill="currentColor" />
        <path d="M3.2 6.2 5.1 8 8.8 4.2" fill="none" stroke="var(--page)" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    );
  }
  if (kind === 'warning') {
    return (
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <path d="M6 0.8 11.4 11H0.6Z" fill="currentColor" />
        <path d="M6 4.4v3M6 9.2v0.1" stroke="var(--page)" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  if (kind === 'critical') {
    return (
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <path d="M3.5 0.5h5l3 3v5l-3 3h-5l-3-3v-5Z" fill="currentColor" />
        <path d="M4 4 8 8M8 4 4 8" stroke="var(--page)" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
      <circle cx="6" cy="6" r="5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M3.8 6h4.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

/** Props for StatusBadge. */
interface StatusBadgeProps {
  kind: StatusKind;
  label: string;
}

/**
 * A pill with a status shape and a text label.
 * @param props The status kind and its label.
 * @returns The badge.
 */
export function StatusBadge(props: StatusBadgeProps) {
  const { kind, label } = props;
  return (
    <span className={`status-badge status-${kind}`}>
      <StatusIcon kind={kind} />
      {label}
    </span>
  );
}
