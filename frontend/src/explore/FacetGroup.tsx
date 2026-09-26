import { useState } from 'react';

import type { FacetColumn, FacetValue } from '../api/types';
import { formatter } from '../utilities/formatter';

const COLLAPSED_SIZE = 8;

/** Props for FacetGroup. */
interface FacetGroupProps {
  column: FacetColumn;
  title: string;
  values: FacetValue[];
  chosen: string[];
  onToggle: (column: FacetColumn, value: string) => void;
}

/**
 * One filter group: a checkbox per value with its count and a bar showing its share.
 * @param props The facet column, its title, its values with counts, the chosen values and what toggling does.
 * @returns The group, or nothing when the facet has no values.
 */
export function FacetGroup(props: FacetGroupProps) {
  const { column, title, values, chosen, onToggle } = props;
  const [expanded, setExpanded] = useState(false);
  if (values.length === 0) {
    return null;
  }
  let largest = 1;
  for (const entry of values) {
    largest = Math.max(largest, entry.count);
  }
  const chosenSet = new Set(chosen);
  const visible: FacetValue[] = [];
  for (const entry of values) {
    if (expanded || visible.length < COLLAPSED_SIZE || chosenSet.has(entry.value)) {
      visible.push(entry);
    }
  }
  return (
    <fieldset className="facet-group">
      <legend>{title}</legend>
      {visible.map((entry) => (
        <label key={entry.value} className={`facet-option ${chosenSet.has(entry.value) ? 'facet-option-chosen' : ''}`}>
          <input type="checkbox" checked={chosenSet.has(entry.value)} onChange={() => onToggle(column, entry.value)} />
          <span className="facet-label">{formatter.facetValue(column, entry.value)}</span>
          <span className="facet-count">{formatter.count(entry.count)}</span>
          <span className="facet-bar" style={{ width: `${(entry.count / largest) * 100}%` }} aria-hidden="true" />
        </label>
      ))}
      {values.length > COLLAPSED_SIZE ? (
        <button type="button" className="facet-more" onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Show fewer' : `Show all ${values.length}`}
        </button>
      ) : null}
    </fieldset>
  );
}
