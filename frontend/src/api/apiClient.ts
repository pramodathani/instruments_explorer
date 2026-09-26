import type {
  ChartResponse,
  ScreenerAnswer,
  ScreenerParameters,
  ScreenerRun,
  ScreenerSetup,
  CompanyProfile,
  FetchJob,
  InstrumentCompany,
  KnowledgeDocument,
  KnowledgeHit,
  KnowledgeOverview,
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
  UniverseMap,
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
   * Fetches the knowledge counts, sources and latest jobs.
   * @returns The overview.
   * @throws ApiError when the session has ended.
   */
  async fetchKnowledgeOverview(): Promise<KnowledgeOverview> {
    const response = await fetch('/api/knowledge/overview', {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as KnowledgeOverview;
  }

  /**
   * Imports NSE's list of listed equities again.
   * @returns How many companies were imported.
   * @throws ApiError when NSE could not be read.
   */
  async refreshListing(): Promise<number> {
    const response = await fetch('/api/knowledge/listing/refresh', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        [REQUESTED_WITH_HEADER]: REQUESTED_WITH_VALUE,
      },
    });
    const body = await this.readJson(response);
    return Number(body.companies);
  }

  /**
   * Finds companies by name or symbol, or lists the latest fetched.
   * @param text Typed text, or an empty string.
   * @returns Company documents.
   * @throws ApiError when the session has ended.
   */
  async fetchCompanies(text: string): Promise<CompanyProfile[]> {
    const query = new URLSearchParams();
    query.set('q', text);
    const response = await fetch(`/api/knowledge/companies?${query.toString()}`, {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as CompanyProfile[];
  }

  /**
   * Fetches the company an instrument belongs to, with what is stored about it.
   * @param instrumentId The instrument's id.
   * @returns The company, or a reason it is not one.
   * @throws ApiError with 404 for an unknown instrument.
   */
  async fetchInstrumentCompany(instrumentId: string): Promise<InstrumentCompany> {
    const response = await fetch(`/api/knowledge/instruments/${encodeURIComponent(instrumentId)}`, {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as InstrumentCompany;
  }

  /**
   * Starts fetching knowledge about an instrument's company.
   * @param instrumentId The instrument's id.
   * @param sources The source keys to run, or null for every available source.
   * @returns The queued job.
   * @throws ApiError when the instrument is not a company.
   */
  async startKnowledgeFetch(instrumentId: string, sources: string[] | null): Promise<FetchJob> {
    const response = await fetch(`/api/knowledge/instruments/${encodeURIComponent(instrumentId)}/fetch`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        [REQUESTED_WITH_HEADER]: REQUESTED_WITH_VALUE,
      },
      body: JSON.stringify({
        sources,
      }),
    });
    return (await this.readJson(response)) as unknown as FetchJob;
  }

  /**
   * Uploads a document about an instrument's company.
   * @param instrumentId The instrument's id.
   * @param file The PDF, HTML, Markdown or text file.
   * @returns How many characters and chunks were stored.
   * @throws ApiError when the file cannot be read.
   */
  async uploadKnowledgeDocument(instrumentId: string, file: File): Promise<{ title: string; characters: number; chunks: number }> {
    const form = new FormData();
    form.append('file', file);
    const response = await fetch(`/api/knowledge/instruments/${encodeURIComponent(instrumentId)}/documents`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        [REQUESTED_WITH_HEADER]: REQUESTED_WITH_VALUE,
      },
      body: form,
    });
    return (await this.readJson(response)) as unknown as { title: string; characters: number; chunks: number };
  }

  /**
   * Searches stored knowledge by meaning.
   * @param text The question or phrase.
   * @param companyKey Search only this company, or null for all.
   * @param signal Aborts the request when a newer search replaces it.
   * @returns Passages, best first.
   * @throws ApiError when ChromaDB cannot be searched.
   */
  async searchKnowledge(text: string, companyKey: string | null, signal: AbortSignal): Promise<KnowledgeHit[]> {
    const query = new URLSearchParams();
    query.set('q', text);
    if (companyKey !== null) {
      query.set('company_key', companyKey);
    }
    const response = await fetch(`/api/knowledge/search?${query.toString()}`, {
      credentials: 'same-origin',
      signal,
    });
    return (await this.readJson(response)) as unknown as KnowledgeHit[];
  }

  /**
   * Fetches one stored document with its full text.
   * @param documentId The document's id.
   * @returns The document.
   * @throws ApiError with 404 for an unknown document.
   */
  async fetchKnowledgeDocument(documentId: string): Promise<KnowledgeDocument> {
    const response = await fetch(`/api/knowledge/documents/${encodeURIComponent(documentId)}`, {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as KnowledgeDocument;
  }

  /**
   * Fetches the universe map.
   * @param includeOptions Whether to include options, which makes the map about five times larger.
   * @param signal Cancels the request.
   * @returns The laid-out instruments.
   * @throws ApiError with 503 while the instrument index is being built.
   */
  async fetchUniverse(includeOptions: boolean, signal: AbortSignal): Promise<UniverseMap> {
    const response = await fetch(`/api/universe?include_options=${includeOptions ? 'true' : 'false'}`, {
      credentials: 'same-origin',
      signal,
    });
    return (await this.readJson(response)) as unknown as UniverseMap;
  }

  /**
   * Fetches the screener's universes, conditions and runs.
   * @returns The setup.
   * @throws ApiError when the session has ended.
   */
  async fetchScreenerSetup(): Promise<ScreenerSetup> {
    const response = await fetch('/api/screener/setup', {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as ScreenerSetup;
  }

  /**
   * Starts computing a universe's screener figures.
   * @param universe The universe key.
   * @returns The run's state.
   * @throws ApiError when the index is not ready.
   */
  async refreshScreener(universe: string): Promise<ScreenerRun> {
    const response = await fetch('/api/screener/refresh', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        [REQUESTED_WITH_HEADER]: REQUESTED_WITH_VALUE,
      },
      body: JSON.stringify({
        universe,
      }),
    });
    return (await this.readJson(response)) as unknown as ScreenerRun;
  }

  /**
   * Runs a screen.
   * @param parameters The universe, conditions, sectors and order.
   * @param signal Aborts the request when a newer one replaces it.
   * @returns The matches and their sectors.
   * @throws ApiError for an invalid condition.
   */
  async runScreen(parameters: ScreenerParameters, signal: AbortSignal): Promise<ScreenerAnswer> {
    const query = new URLSearchParams();
    query.set('universe', parameters.universe);
    for (const condition of parameters.conditions) {
      query.append('condition', condition);
    }
    for (const sector of parameters.sectors) {
      query.append('sector', sector);
    }
    query.set('sort', parameters.sort);
    query.set('descending', parameters.descending ? 'true' : 'false');
    query.set('limit', '500');
    const response = await fetch(`/api/screener/run?${query.toString()}`, {
      credentials: 'same-origin',
      signal,
    });
    return (await this.readJson(response)) as unknown as ScreenerAnswer;
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
