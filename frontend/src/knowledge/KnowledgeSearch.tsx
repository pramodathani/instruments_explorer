import { type FormEvent, useRef, useState } from 'react';

import { ApiError, apiClient } from '../api/apiClient';
import type { KnowledgeHit } from '../api/types';
import { Icon } from '../components/Icon';
import { formatter } from '../utilities/formatter';

/** Props for KnowledgeSearch. */
interface KnowledgeSearchProps {
  companyKey: string | null;
  placeholder: string;
}

/**
 * A question box that finds stored passages by meaning, with each passage's score, source and a way to open it.
 * @param props The company to search within, or null for every company, and the box's placeholder.
 * @returns The search.
 */
export function KnowledgeSearch(props: KnowledgeSearchProps) {
  const { companyKey, placeholder } = props;
  const [question, setQuestion] = useState('');
  const [hits, setHits] = useState<KnowledgeHit[] | null>(null);
  const [error, setError] = useState('');
  const [searching, setSearching] = useState(false);
  const [openText, setOpenText] = useState<Record<string, string>>({});
  const controllerReference = useRef<AbortController | null>(null);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (question.trim() === '') {
      return;
    }
    controllerReference.current?.abort();
    const controller = new AbortController();
    controllerReference.current = controller;
    setSearching(true);
    apiClient
      .searchKnowledge(question, companyKey, controller.signal)
      .then((found) => {
        setHits(found);
        setError('');
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof ApiError ? caught.message : 'The search failed.');
        }
      })
      .finally(() => setSearching(false));
  };

  const toggleDocument = (documentId: string) => {
    if (openText[documentId] !== undefined) {
      const next = { ...openText };
      delete next[documentId];
      setOpenText(next);
      return;
    }
    apiClient
      .fetchKnowledgeDocument(documentId)
      .then((document) => setOpenText((current) => ({ ...current, [documentId]: document.text ?? '' })))
      .catch(() => undefined);
  };

  return (
    <div className="knowledge-search">
      <form className="knowledge-search-form" onSubmit={submit}>
        <Icon name="knowledge" />
        <input className="input" type="search" value={question} placeholder={placeholder} onChange={(event) => setQuestion(event.target.value)} aria-label="Question" />
        <button type="submit" className="button button-primary" disabled={searching || question.trim() === ''}>
          {searching ? 'Searching…' : 'Ask'}
        </button>
      </form>
      {error !== '' ? <p className="error-text">{error}</p> : null}
      {hits !== null && hits.length === 0 ? <p className="muted">Nothing stored matches yet. Fetch some company knowledge first.</p> : null}
      {hits !== null && hits.length > 0 ? (
        <ol className="knowledge-hits">
          {hits.map((hit, position) => (
            <li key={`${hit.document_id}-${position}`} className="knowledge-hit" style={{ animationDelay: `${position * 40}ms` }}>
              <div className="knowledge-hit-heading">
                <span className="knowledge-score" title="How close in meaning, from 0 to 1">
                  <span style={{ width: `${Math.max(0, Math.min(1, hit.score)) * 100}%` }} />
                </span>
                <span className="chip chip-small">{formatter.source(hit.source)}</span>
                {companyKey === null && hit.symbol !== null ? <span className="chip chip-small mono">{hit.symbol}</span> : null}
                {hit.url ? (
                  <a href={hit.url} target="_blank" rel="noreferrer" className="knowledge-hit-title">
                    {hit.title}
                  </a>
                ) : (
                  <button type="button" className="link-button knowledge-hit-title" onClick={() => toggleDocument(hit.document_id)}>
                    {hit.title}
                  </button>
                )}
                <span className="muted">{formatter.dateTime(hit.published_at)}</span>
              </div>
              <p className="knowledge-hit-text">{hit.text}</p>
              {openText[hit.document_id] !== undefined ? <pre className="knowledge-document-text">{openText[hit.document_id]}</pre> : null}
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}
