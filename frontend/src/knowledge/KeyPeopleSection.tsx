import { useState } from 'react';

import { ApiError, apiClient } from '../api/apiClient';
import type { KeyPeople, KeyPerson, KnowledgeDocument } from '../api/types';

const SOURCE_LABELS: Record<string, string> = {
  yahoo: 'Yahoo',
  zaubacorp: 'Registry',
  upload: 'Your upload',
};

/** Props for KeyPeopleSection. */
interface KeyPeopleSectionProps {
  instrumentId: string;
  keyPeople: KeyPeople;
  uploads: KnowledgeDocument[];
  canRead: boolean;
  onChanged: () => void;
}

/**
 * The company's executives and board of directors, merged from Yahoo, the company registry and the user's uploads, with a way to read people from an uploaded document.
 * @param props The instrument, its key people, the uploaded documents, whether Claude can read them, and what to do after reading one.
 * @returns The section.
 */
export function KeyPeopleSection(props: KeyPeopleSectionProps) {
  const { instrumentId, keyPeople, uploads, canRead, onChanged } = props;
  const [chosen, setChosen] = useState('');
  const [reading, setReading] = useState(false);
  const [message, setMessage] = useState('');
  const empty = keyPeople.executives.length === 0 && keyPeople.board.length === 0;

  const read = () => {
    const documentId = chosen !== '' ? chosen : uploads[0]?.document_id;
    if (documentId === undefined) {
      return;
    }
    setReading(true);
    setMessage('Claude is reading the document…');
    apiClient
      .extractKeyPeople(instrumentId, documentId)
      .then((answer) => {
        setMessage(`Found ${answer.found} people in the document.`);
        onChanged();
      })
      .catch((caught: unknown) => setMessage(caught instanceof ApiError ? caught.message : 'The document could not be read.'))
      .finally(() => setReading(false));
  };

  return (
    <section className="key-people">
      <h3 className="section-heading">Key people</h3>
      {empty ? <p className="muted">Nobody is stored yet. Fetching company knowledge reads the officers from Yahoo Finance and the board from the company registry.</p> : null}
      {keyPeople.executives.length > 0 ? <PeopleTable title="Executives" people={keyPeople.executives} showAge /> : null}
      {keyPeople.board.length > 0 ? <PeopleTable title="Board of directors" people={keyPeople.board} showAge={false} /> : null}
      {uploads.length > 0 ? (
        <div className="key-people-read">
          <select className="input" value={chosen} onChange={(event) => setChosen(event.target.value)} disabled={!canRead || reading}>
            {uploads.map((document) => (
              <option key={document.document_id} value={document.document_id}>
                {document.title}
              </option>
            ))}
          </select>
          <button type="button" className="button" onClick={read} disabled={!canRead || reading}>
            {reading ? 'Reading…' : 'Read people from this upload'}
          </button>
          {!canRead ? <span className="muted">Needs the Claude API key.</span> : null}
        </div>
      ) : (
        <p className="muted">To add people from an annual report, upload it under Documents below, then read it here.</p>
      )}
      {message !== '' ? <p className="muted">{message}</p> : null}
    </section>
  );
}

/** Props for PeopleTable. */
interface PeopleTableProps {
  title: string;
  people: KeyPerson[];
  showAge: boolean;
}

/**
 * One group of key people with their roles, where each role came from, and when they were appointed.
 * @param props The group's title, its people, and whether to show ages.
 * @returns The table.
 */
function PeopleTable(props: PeopleTableProps) {
  const { title, people, showAge } = props;
  return (
    <div className="people-group">
      <h4 className="people-group-title">
        {title} <span className="muted">({people.length})</span>
      </h4>
      <table className="data-table people-table">
        <tbody>
          {people.map((person) => (
            <tr key={`${title}-${person.name}`}>
              <td className="people-name">{person.name}</td>
              <td>
                {person.roles.map((role) => (
                  <div key={`${role.source}-${role.role}`} className="people-role">
                    {role.role} <span className="chip chip-small">{SOURCE_LABELS[role.source] ?? role.source}</span>
                  </div>
                ))}
              </td>
              <td className="muted mono people-facts">
                {showAge && person.age ? <div>age {person.age}</div> : null}
                {person.appointed_on ? <div>since {person.appointed_on}</div> : null}
                {person.din ? <div title="Director identification number">DIN {person.din}</div> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
