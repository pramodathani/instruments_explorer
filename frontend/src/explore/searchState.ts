import type { FacetColumn, SearchParameters } from '../api/types';

export const FACET_COLUMNS: FacetColumn[] = ['asset_class', 'exchange', 'shape', 'segment', 'option_type', 'expiry_month'];

export const FACET_TITLES: Record<FacetColumn, string> = {
  asset_class: 'Asset class',
  exchange: 'Exchange',
  shape: 'Kind',
  segment: 'Segment',
  option_type: 'Option type',
  expiry_month: 'Expiry month',
};

const SORTS: SearchParameters['sort'][] = ['relevance', 'name', 'expiry', 'strike'];

export const PAGE_SIZE = 100;

/** Reads and writes the explorer's search in the page address, so the back button, reloads and shared links keep it. */
export class SearchState {
  /**
   * Reads the search from the address's query string.
   * @param query The query string parameters.
   * @returns The search, starting at the first page.
   */
  read(query: URLSearchParams): SearchParameters {
    const filters: SearchParameters['filters'] = {};
    for (const column of FACET_COLUMNS) {
      const values = query.getAll(column);
      if (values.length > 0) {
        filters[column] = values;
      }
    }
    const sortText = query.get('sort') ?? 'relevance';
    const sort = SORTS.includes(sortText as SearchParameters['sort']) ? (sortText as SearchParameters['sort']) : 'relevance';
    return {
      text: query.get('q') ?? '',
      filters,
      strikeMinimum: this.readNumber(query.get('strike_minimum')),
      strikeMaximum: this.readNumber(query.get('strike_maximum')),
      sort,
      limit: PAGE_SIZE,
      offset: 0,
    };
  }

  /**
   * Writes a search into a query string.
   * @param parameters The search.
   * @returns The query string parameters, leaving out defaults.
   */
  write(parameters: SearchParameters): URLSearchParams {
    const query = new URLSearchParams();
    if (parameters.text !== '') {
      query.set('q', parameters.text);
    }
    for (const column of FACET_COLUMNS) {
      for (const value of parameters.filters[column] ?? []) {
        query.append(column, value);
      }
    }
    if (parameters.strikeMinimum !== null) {
      query.set('strike_minimum', String(parameters.strikeMinimum));
    }
    if (parameters.strikeMaximum !== null) {
      query.set('strike_maximum', String(parameters.strikeMaximum));
    }
    if (parameters.sort !== 'relevance') {
      query.set('sort', parameters.sort);
    }
    return query;
  }

  /**
   * Turns one filter value on or off.
   * @param parameters The current search.
   * @param column The facet column.
   * @param value The value to toggle.
   * @returns The new search.
   */
  toggle(parameters: SearchParameters, column: FacetColumn, value: string): SearchParameters {
    const chosen = new Set(parameters.filters[column] ?? []);
    if (chosen.has(value)) {
      chosen.delete(value);
    } else {
      chosen.add(value);
    }
    return {
      ...parameters,
      filters: {
        ...parameters.filters,
        [column]: [...chosen],
      },
    };
  }

  /**
   * Counts the filters in use.
   * @param parameters The search.
   * @returns How many values are chosen across all facets, plus one for each strike bound.
   */
  activeFilterCount(parameters: SearchParameters): number {
    let count = 0;
    for (const column of FACET_COLUMNS) {
      count += (parameters.filters[column] ?? []).length;
    }
    if (parameters.strikeMinimum !== null) {
      count += 1;
    }
    if (parameters.strikeMaximum !== null) {
      count += 1;
    }
    return count;
  }

  /**
   * Reads a number from the query string.
   * @param text The text, or null.
   * @returns The number, or null when absent or not a number.
   */
  private readNumber(text: string | null): number | null {
    if (text === null || text.trim() === '') {
      return null;
    }
    const value = Number(text);
    return Number.isFinite(value) ? value : null;
  }
}

export const searchState = new SearchState();
