import { useState } from 'react';
import { Link } from 'react-router';

import { ApiError, apiClient } from '../api/apiClient';
import type { ChatItem } from './chatController';
import { chatController } from './chatController';

const TOOL_LABELS: Record<string, string> = {
  search_instruments: 'Searching instruments',
  get_instrument: 'Reading instrument details',
  get_quote: 'Reading the quote',
  list_indicators: 'Listing indicators',
  get_price_history: 'Reading price history',
  get_option_chain: 'Reading the option chain',
  describe_screener: 'Reading the screener setup',
  run_screen: 'Running a screen',
  get_company: 'Reading the company',
  search_knowledge: 'Searching stored knowledge',
  request_knowledge_fetch: 'Asking to fetch company knowledge',
  show_in_ui: 'Opening a view',
  web_search: 'Searching the web',
};

/** Props for ToolCard. */
interface ToolCardProps {
  tool: Extract<ChatItem, { kind: 'tool' }>;
}

/**
 * One tool call: what Claude looked up, what came back, and any button the tool offers.
 * @param props The tool item.
 * @returns The card.
 */
export function ToolCard(props: ToolCardProps) {
  const { tool } = props;
  const label = TOOL_LABELS[tool.name] ?? tool.name;
  const state = !tool.done ? 'running' : tool.isError ? 'failed' : 'done';
  return (
    <div className={`tool-card tool-${state}`}>
      <details>
        <summary>
          <span className="tool-state" aria-hidden="true" />
          <span className="tool-label">{label}</span>
          {tool.summary !== '' ? <span className="tool-summary muted">{tool.summary}</span> : null}
        </summary>
        {tool.input !== undefined ? <pre className="tool-input mono">{JSON.stringify(tool.input, null, 2)}</pre> : null}
      </details>
      {tool.uiAction?.kind === 'navigate' ? (
        <button type="button" className="button button-quiet tool-action" onClick={() => chatController.navigate(tool.uiAction?.kind === 'navigate' ? tool.uiAction.path : '/')}>
          Open {tool.uiAction.label}
        </button>
      ) : null}
      {tool.uiAction?.kind === 'confirm_fetch' ? <FetchConfirmation action={tool.uiAction} /> : null}
    </div>
  );
}

/** Props for FetchConfirmation. */
interface FetchConfirmationProps {
  action: Extract<NonNullable<Extract<ChatItem, { kind: 'tool' }>['uiAction']>, { kind: 'confirm_fetch' }>;
}

/**
 * The button that starts a company knowledge fetch Claude asked for, which the user must press.
 * @param props The request.
 * @returns The confirmation.
 */
function FetchConfirmation(props: FetchConfirmationProps) {
  const { action } = props;
  const [state, setState] = useState<'asking' | 'starting' | 'started' | 'failed'>('asking');
  const [message, setMessage] = useState('');
  const name = action.company_name ?? action.symbol ?? 'this company';

  const start = () => {
    setState('starting');
    apiClient
      .startKnowledgeFetch(action.instrument_id, null)
      .then(() => setState('started'))
      .catch((caught: unknown) => {
        setState('failed');
        setMessage(caught instanceof ApiError ? caught.message : 'The fetch could not start.');
      });
  };

  return (
    <div className="fetch-confirmation">
      <p>
        Claude would like to fetch fresh knowledge about <strong>{name}</strong> from NSE, Yahoo Finance, Screener.in and news sites.
        {action.reason !== '' ? ` ${action.reason}` : ''}
      </p>
      {state === 'asking' || state === 'starting' ? (
        <button type="button" className="button button-primary" onClick={start} disabled={state === 'starting'}>
          {state === 'starting' ? 'Starting…' : `Fetch ${action.symbol ?? 'now'}`}
        </button>
      ) : null}
      {state === 'started' ? (
        <p className="muted">
          The fetch is running and takes about twenty seconds. Ask again when it is done, or follow it on the <Link to={`/instrument/${action.instrument_id}`}>instrument page</Link>.
        </p>
      ) : null}
      {state === 'failed' ? <p className="error-text">{message}</p> : null}
    </div>
  );
}
