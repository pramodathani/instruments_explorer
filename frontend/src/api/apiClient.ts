import type {
  ChartResponse,
  ExpiryDescription,
  OptionChain,
  Underlying,
  VolatilitySurface,
  IndexStatus,
  IndicatorDescription,
  InstrumentDocument,
  Quote,
  SearchParameters,
  SearchResponse,
  StatusDocument,
} from './types';

const REQUESTED_WITH_HEADER = 'X-Requested-With';
const REQUESTED_WITH_VALUE = 'instruments-explorer';

/** An error answer from the server, carrying its status code and message. */
export class ApiError extends Error {
  readonly statusCode: number;

  /**
   * Creates the error.
   * @param statusCode The HTTP status code.
   * @param message The server's explanation.
   */
  constructor(statusCode: number, message: string) {
    super(message);
    this.statusCode = statusCode;
  }
}

/** Calls the instruments_explorer server. */
export class ApiClient {
  /**
   * Asks whether this browser is logged in.
   * @returns True when the session is logged in.
   */
  async isLoggedIn(): Promise<boolean> {
    const response = await fetch('/api/auth/session', {
      credentials: 'same-origin',
    });
    const body = await this.readJson(response);
    return body.authenticated === true;
  }

  /**
   * Logs in with the password.
   * @param password The password typed in.
   * @throws ApiError when the password is wrong or the address is locked out.
   */
  async logIn(password: string): Promise<void> {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        [REQUESTED_WITH_HEADER]: REQUESTED_WITH_VALUE,
      },
      body: JSON.stringify({
        password,
      }),
    });
    await this.readJson(response);
  }

  /** Logs out. */
  async logOut(): Promise<void> {
    const response = await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        [REQUESTED_WITH_HEADER]: REQUESTED_WITH_VALUE,
      },
    });
    await this.readJson(response);
  }

  /**
   * Fetches whether the project's stores are reachable and whether the assistant is configured.
   * @returns The status document.
   * @throws ApiError when the session has ended.
   */
  async fetchStatus(): Promise<StatusDocument> {
    const response = await fetch('/api/status', {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as StatusDocument;
  }

  /**
   * Fetches the state of the instrument search index.
   * @returns The index status.
   * @throws ApiError when the session has ended.
   */
  async fetchIndexStatus(): Promise<IndexStatus> {
    const response = await fetch('/api/instruments/index-status', {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as IndexStatus;
  }

  /**
   * Searches and filters the instrument index.
   * @param parameters The text, filters, strike range, order and page.
   * @param signal Aborts the request when a newer search replaces it.
   * @returns One page of results with the total and the filter counts.
   * @throws ApiError with 503 while the index is being built, or 400 for an invalid request.
   */
  async searchInstruments(parameters: SearchParameters, signal: AbortSignal): Promise<SearchResponse> {
    const query = new URLSearchParams();
    query.set('q', parameters.text);
    for (const [column, values] of Object.entries(parameters.filters)) {
      for (const value of values ?? []) {
        query.append(column, value);
      }
    }
    if (parameters.strikeMinimum !== null) {
      query.set('strike_minimum', String(parameters.strikeMinimum));
    }
    if (parameters.strikeMaximum !== null) {
      query.set('strike_maximum', String(parameters.strikeMaximum));
    }
    query.set('sort', parameters.sort);
    query.set('limit', String(parameters.limit));
    query.set('offset', String(parameters.offset));
    const response = await fetch(`/api/instruments/search?${query.toString()}`, {
      credentials: 'same-origin',
      signal,
    });
    return (await this.readJson(response)) as unknown as SearchResponse;
  }

  /**
   * Fetches one instrument's index record, ubi details and broker attributes.
   * @param instrumentId The instrument's id.
   * @returns The instrument document.
   * @throws ApiError with 404 when the instrument is unknown.
   */
  async fetchInstrument(instrumentId: string): Promise<InstrumentDocument> {
    const response = await fetch(`/api/instruments/${encodeURIComponent(instrumentId)}`, {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as InstrumentDocument;
  }

  /**
   * Fetches one instrument's full quote from ubi.
   * @param instrumentId The instrument's id.
   * @returns The quote.
   * @throws ApiError when ubi has no quote or cannot be reached.
   */
  async fetchQuote(instrumentId: string): Promise<Quote> {
    const response = await fetch(`/api/instruments/${encodeURIComponent(instrumentId)}/quote`, {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as Quote;
  }

  /**
   * Fetches the indicators the chart can show.
   * @returns One description per indicator.
   * @throws ApiError when the session has ended.
   */
  async fetchIndicators(): Promise<IndicatorDescription[]> {
    const response = await fetch('/api/indicators', {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as IndicatorDescription[];
  }

  /**
   * Fetches an instrument's candles with the requested indicators.
   * @param instrumentId The instrument's id.
   * @param interval The candle interval, such as "day".
   * @param days How many days back to read.
   * @param adjusted Whether to correct an adjustable instrument for splits and bonuses.
   * @param indicators Indicator requests such as "rsi:14".
   * @param signal Aborts the request when a newer one replaces it.
   * @returns The candles and indicators.
   * @throws ApiError for an invalid range, an unknown instrument or when ubi cannot be reached.
   */
  async fetchChart(
    instrumentId: string,
    interval: string,
    days: number,
    adjusted: boolean,
    indicators: string[],
    signal: AbortSignal,
  ): Promise<ChartResponse> {
    const query = new URLSearchParams();
    query.set('interval', interval);
    query.set('days', String(days));
    query.set('adjusted', adjusted ? 'true' : 'false');
    for (const indicator of indicators) {
      query.append('indicator', indicator);
    }
    const response = await fetch(`/api/instruments/${encodeURIComponent(instrumentId)}/chart?${query.toString()}`, {
      credentials: 'same-origin',
      signal,
    });
    return (await this.readJson(response)) as unknown as ChartResponse;
  }

  /**
   * Lists underlyings that have futures or options.
   * @param text Typed text to match the start of the name.
   * @param signal Aborts the request when newer typing replaces it.
   * @returns One entry per exchange and underlying.
   * @throws ApiError with 503 while the index is being built.
   */
  async fetchUnderlyings(text: string, signal: AbortSignal): Promise<Underlying[]> {
    const query = new URLSearchParams();
    query.set('q', text);
    query.set('limit', '60');
    const response = await fetch(`/api/derivatives/underlyings?${query.toString()}`, {
      credentials: 'same-origin',
      signal,
    });
    return (await this.readJson(response)) as unknown as Underlying[];
  }

  /**
   * Fetches an underlying's cash price, futures and option expiries.
   * @param exchange The exchange.
   * @param underlying The underlying.
   * @returns The description.
   * @throws ApiError with 404 when the underlying has no derivatives.
   */
  async fetchExpiries(exchange: string, underlying: string): Promise<ExpiryDescription> {
    const query = new URLSearchParams();
    query.set('exchange', exchange);
    query.set('underlying', underlying);
    const response = await fetch(`/api/derivatives/expiries?${query.toString()}`, {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as ExpiryDescription;
  }

  /**
   * Fetches one expiry's option chain.
   * @param exchange The exchange.
   * @param underlying The underlying.
   * @param expiry The expiry as "YYYY-MM-DD".
   * @param signal Aborts the request when a newer one replaces it.
   * @returns The chain.
   * @throws ApiError with 404 when there are no options for that expiry.
   */
  async fetchChain(exchange: string, underlying: string, expiry: string, signal: AbortSignal): Promise<OptionChain> {
    const query = new URLSearchParams();
    query.set('exchange', exchange);
    query.set('underlying', underlying);
    query.set('expiry', expiry);
    const response = await fetch(`/api/derivatives/chain?${query.toString()}`, {
      credentials: 'same-origin',
      signal,
    });
    return (await this.readJson(response)) as unknown as OptionChain;
  }

  /**
   * Fetches an underlying's implied volatility surface.
   * @param exchange The exchange.
   * @param underlying The underlying.
   * @param signal Aborts the request when a newer one replaces it.
   * @returns The surface.
   * @throws ApiError with 404 when the underlying has no options.
   */
  async fetchSurface(exchange: string, underlying: string, signal: AbortSignal): Promise<VolatilitySurface> {
    const query = new URLSearchParams();
    query.set('exchange', exchange);
    query.set('underlying', underlying);
    const response = await fetch(`/api/derivatives/surface?${query.toString()}`, {
      credentials: 'same-origin',
      signal,
    });
    return (await this.readJson(response)) as unknown as VolatilitySurface;
  }

  /**
   * Reads a JSON answer, turning an error status into an ApiError.
   * @param response The fetch response.
   * @returns The parsed body.
   * @throws ApiError when the status is not OK.
   */
  private async readJson(response: Response): Promise<Record<string, unknown>> {
    let body: Record<string, unknown> = {};
    try {
      body = (await response.json()) as Record<string, unknown>;
    } catch {
      body = {};
    }
    if (!response.ok) {
      const detail = typeof body.detail === 'string' ? body.detail : response.statusText;
      throw new ApiError(response.status, detail);
    }
    return body;
  }
}

export const apiClient = new ApiClient();
