/** One of the project's own stores, or ubi, and whether it answered. */
export interface StoreStatus {
  name: string;
  reachable: boolean;
  detail: string;
}

/** Whether the chat assistant has an API key, and which model it uses. */
export interface AssistantStatus {
  configured: boolean;
  model: string;
}

/** The state of the instrument search index. */
export interface IndexStatus {
  state: 'starting' | 'building' | 'ready' | 'unavailable';
  mapping_date: string | null;
  instrument_count: number;
  building_count: number | null;
  last_error: string | null;
}

/** The answer of /api/status. */
export interface StatusDocument {
  stores: StoreStatus[];
  index: IndexStatus;
  assistant: AssistantStatus;
}

/** The facet columns the explorer can filter by. */
export type FacetColumn = 'exchange' | 'asset_class' | 'shape' | 'segment' | 'option_type' | 'expiry_month' | 'sector';

/** One value of a facet and how many instruments have it. */
export interface FacetValue {
  value: string;
  count: number;
}

/** One instrument as the index stores it. */
export interface InstrumentRecord {
  instrument_id: string;
  exchange: string;
  segment: string;
  bare_segment: string;
  asset_class: string;
  shape: 'security' | 'future' | 'option';
  is_index: boolean;
  symbol: string | null;
  underlying_symbol: string | null;
  display_name: string;
  company_name: string | null;
  sector: string | null;
  expiry_date: string | null;
  strike_price: number | null;
  option_type: 'CE' | 'PE' | null;
}

/** The answer of /api/instruments/search. */
export interface SearchResponse {
  mapping_date: string;
  results: InstrumentRecord[];
  total: number;
  facets: Record<FacetColumn, FacetValue[]>;
}

/** What the explorer asks the search route for. */
export interface SearchParameters {
  text: string;
  filters: Partial<Record<FacetColumn, string[]>>;
  strikeMinimum: number | null;
  strikeMaximum: number | null;
  sort: 'relevance' | 'name' | 'expiry' | 'strike';
  limit: number;
  offset: number;
}

/** One broker's handle on an instrument, from ubi's details. */
export interface BrokerHandle {
  broker: string;
  broker_token: string;
  order_symbol: string;
  lot_size: string | null;
  tick_size: string | null;
}

/** Ubi's details of one instrument. */
export interface InstrumentDetails {
  mapping_date: string;
  first_seen_date: string | null;
  last_seen_date: string | null;
  lot_size: number | null;
  tick_size: string | null;
  carried_by: BrokerHandle[];
}

/** The answer of /api/instruments/{id}. */
export interface InstrumentDocument {
  instrument: InstrumentRecord | null;
  details: InstrumentDetails | null;
  attributes: Record<string, string>;
  ubi_error: string | null;
}

/** One level of market depth. */
export interface DepthLevel {
  price: number;
  quantity: number;
  orders: number | null;
}

/** A quote as the server encodes it, from the live feed or ubi's quote route. */
export interface Quote {
  instrument_id: string;
  lot_size: number | null;
  last_price: number | null;
  previous_close: number | null;
  change: number | null;
  change_percent: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  average_price: number | null;
  volume: number | null;
  last_quantity: number | null;
  last_trade_time: number | null;
  exchange_time: number | null;
  buy_quantity: number | null;
  sell_quantity: number | null;
  oi: number | null;
  oi_day_high: number | null;
  oi_day_low: number | null;
  received_at: number | null;
  depth: {
    buy: DepthLevel[];
    sell: DepthLevel[];
  };
  stale: boolean;
  source: string;
}

/** One number an indicator can be tuned by. */
export interface IndicatorParameterDescription {
  name: string;
  label: string;
  default: number;
  minimum: number;
  maximum: number;
  whole_number: boolean;
}

/** One indicator the chart can show, as /api/indicators describes it. */
export interface IndicatorDescription {
  key: string;
  short_label: string;
  label: string;
  family: string;
  description: string;
  placement: 'price' | 'panel' | 'markers';
  parameters: IndicatorParameterDescription[];
  outputs: {
    key: string;
    label: string;
  }[];
  reference_lines: number[];
  needs_volume: boolean;
}

/** One computed indicator in a chart answer. */
export interface IndicatorResult {
  id: string;
  key: string;
  title: string;
  placement: 'price' | 'panel' | 'markers';
  reference_lines: number[];
  outputs: {
    key: string;
    label: string;
    points: [number, number][];
  }[];
  markers: {
    time: number;
    pattern: string;
    label: string;
    bullish: boolean;
  }[];
}

/** A candle row: time in epoch milliseconds, open, high, low, close, volume and open interest. */
export type CandleRow = [number, number | null, number | null, number | null, number | null, number | null, number | null];

/** The answer of /api/instruments/{id}/chart. */
export interface ChartResponse {
  instrument_id: string;
  interval: string;
  days: number;
  price_basis: string | null;
  adjustable: boolean;
  source: string | null;
  has_volume: boolean;
  candles: CandleRow[];
  indicators: IndicatorResult[];
  errors: string[];
}

/** One underlying that has futures or options on an exchange. */
export interface Underlying {
  exchange: string;
  underlying_symbol: string;
  asset_class: string;
  is_index: boolean;
  futures: number;
  options: number;
  expiries: number;
  next_expiry: string | null;
}

/** An underlying's cash instrument with its latest price. */
export interface SpotPrice {
  instrument_id: string;
  display_name: string;
  last_price: number | null;
  change_percent: number | null;
}

/** The answer of /api/derivatives/expiries. */
export interface ExpiryDescription {
  exchange: string;
  underlying_symbol: string;
  spot: SpotPrice | null;
  futures: {
    instrument_id: string;
    display_name: string;
    expiry_date: string;
    last_price: number | null;
  }[];
  option_expiries: {
    expiry_date: string;
    contracts: number;
    strikes: number;
    days: number;
  }[];
}

/** One call or put in an option chain row. */
export interface ChainSide {
  instrument_id: string;
  last_price: number | null;
  change_percent: number | null;
  oi: number | null;
  volume: number | null;
  bid: number | null;
  offer: number | null;
  received_at: number | null;
  iv: number | null;
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
}

/** One strike of an option chain. */
export interface ChainRow {
  strike: number;
  call: ChainSide | null;
  put: ChainSide | null;
}

/** The answer of /api/derivatives/chain. */
export interface OptionChain {
  exchange: string;
  underlying_symbol: string;
  expiry_date: string;
  days: number;
  rate: number;
  spot: SpotPrice | null;
  forward: number | null;
  forward_source: 'future' | 'spot' | 'nearest_future' | null;
  atm_strike: number | null;
  max_pain: number | null;
  put_call_ratio: number | null;
  total_call_oi: number;
  total_put_oi: number;
  rows: ChainRow[];
}

/** The answer of /api/derivatives/surface. */
export interface VolatilitySurface {
  exchange: string;
  underlying_symbol: string;
  expiries: {
    expiry_date: string;
    days: number;
    forward: number | null;
  }[];
  strikes: number[];
  volatility: (number | null)[][];
}

/** One source of company knowledge and whether it can run. */
export interface KnowledgeSource {
  key: string;
  label: string;
  description: string;
  news: boolean;
  available: boolean;
  reason: string;
}

/** Who a company is. */
export interface CompanyIdentity {
  company_key: string;
  name: string;
  isin: string | null;
  exchange: string;
  symbol: string;
}

/** One step of a fetch job: one source's run. */
export interface FetchJobStep {
  source: string;
  label: string;
  status: 'queued' | 'running' | 'done' | 'failed' | 'skipped';
  message: string;
  documents: number;
  new: number;
}

/** One run of the knowledge fetchers for a company. */
export interface FetchJob {
  job_id: string;
  company: CompanyIdentity;
  reason: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  steps: FetchJobStep[];
  created_at: number;
  finished_at: number | null;
}

/** Everything stored about a company, merged from its sources. */
export interface CompanyProfile {
  company_key: string;
  name?: string;
  isin?: string;
  symbol?: string;
  exchange?: string;
  listed_on?: string | null;
  face_value?: number | null;
  sector?: string;
  industry?: string;
  classification?: string[];
  website?: string;
  employees?: number;
  city?: string;
  country?: string;
  about?: string;
  pros?: string[];
  cons?: string[];
  screener_ratios?: Record<string, string>;
  fundamentals?: Record<string, number>;
  wikipedia_title?: string;
  sources?: Record<string, { fetched_at: number; message: string }>;
  updated_at?: number;
}

/** A stored document, without its full text. */
export interface KnowledgeDocument {
  document_id: string;
  company_key: string;
  source: string;
  title: string;
  url: string;
  published_at: number | null;
  fetched_at: number;
  text?: string;
}

/** The answer of /api/knowledge/instruments/{id}. */
export interface InstrumentCompany {
  company: CompanyIdentity | null;
  reason: string | null;
  profile: CompanyProfile | null;
  documents: KnowledgeDocument[];
}

/** One passage found by meaning. */
export interface KnowledgeHit {
  text: string;
  score: number;
  document_id: string;
  company_key: string;
  symbol: string | null;
  source: string;
  title: string;
  url: string | null;
  published_at: number | null;
}

/** The answer of /api/knowledge/overview. */
export interface KnowledgeOverview {
  counts: {
    listed: number;
    fetched: number;
    documents: number;
    chunks: number | null;
  };
  sources: KnowledgeSource[];
  jobs: FetchJob[];
}

/** One screening condition the screener offers. */
export interface ScreenerCondition {
  key: string;
  label: string;
  description: string;
  parameters: IndicatorParameterDescription[];
}

/** A screener figures run: its universe and progress. */
export interface ScreenerRun {
  run_id: string;
  universe: string;
  status: 'running' | 'done' | 'cancelled';
  total: number;
  done: number;
  failed: number;
  started_at: number;
  finished_at: number | null;
}

/** The answer of /api/screener/setup. */
export interface ScreenerSetup {
  universes: {
    key: string;
    label: string;
  }[];
  conditions: ScreenerCondition[];
  sortable: string[];
  job: ScreenerRun | null;
  last_runs: Record<string, ScreenerRun | null>;
}

/** One stock's stored figures. */
export interface ScreenerRow {
  instrument_id: string;
  symbol: string;
  name: string;
  sector: string;
  close: number | null;
  change_1d: number | null;
  change_5d: number | null;
  change_21d: number | null;
  change_63d: number | null;
  change_252d: number | null;
  from_high: number | null;
  from_low: number | null;
  rsi_14: number | null;
  adx_14: number | null;
  natr_14: number | null;
  volume_ratio: number | null;
  traded_value: number | null;
  percent_b: number | null;
  last_candle_date: string;
}

/** One sector of a screen's matches, for the heatmap. */
export interface ScreenerSector {
  sector: string;
  count: number;
  average_change: number | null;
  stocks: {
    instrument_id: string;
    symbol: string;
    name: string | null;
    change_1d: number | null;
    traded_value: number | null;
  }[];
}

/** The answer of /api/screener/run. */
export interface ScreenerAnswer {
  universe: string;
  members: number;
  with_figures: number;
  matched: number;
  rows: ScreenerRow[];
  sectors: ScreenerSector[];
  sector_names: string[];
  last_run: ScreenerRun | null;
}

/** What a screen asks for. */
export interface ScreenerParameters {
  universe: string;
  conditions: string[];
  sectors: string[];
  sort: string;
  descending: boolean;
}

/** A label placed in the universe map: an asset class's galaxy or one of its biggest underlyings. */
export interface UniverseLabel {
  label: string;
  x: number;
  y: number;
  z: number;
  count: number;
  radius: number;
}

/** Every instrument laid out in 3D, as parallel arrays with one entry per point. */
export interface UniverseMap {
  ids: string[];
  names: string[];
  exchanges: string[];
  shapes: number[];
  asset_classes: number[];
  asset_class_names: string[];
  positions: number[];
  anchors: number[];
  changes: (number | null)[];
  galaxies: UniverseLabel[];
  clusters: UniverseLabel[];
  radius: number;
  quoted: number;
  mapping_date: string;
  include_options: boolean;
}

/** A chat conversation in the list. */
export interface ChatConversation {
  conversation_id: string;
  title: string;
  created_at: number;
  updated_at: number;
  message_count: number;
  input_tokens: number;
  output_tokens: number;
}

/** An instruction for the page that a tool gives: open a view, or offer to fetch company knowledge. */
export type ChatUiAction =
  | {
      kind: 'navigate';
      path: string;
      label: string;
    }
  | {
      kind: 'confirm_fetch';
      instrument_id: string;
      company_name: string | null;
      symbol: string | null;
      reason: string;
    };

/** One stored piece of a conversation, as the chat panel draws it. */
export type ChatStoredItem =
  | {
      kind: 'user';
      text: string;
      created_at: number | null;
    }
  | {
      kind: 'text' | 'thinking';
      text: string;
    }
  | {
      kind: 'tool_call';
      id: string;
      name: string;
      input: unknown;
    }
  | {
      kind: 'tool_result';
      id: string;
      summary: string;
      is_error: boolean;
      ui_action: ChatUiAction | null;
    };

/** A conversation with its items. */
export interface ChatTranscriptDocument {
  conversation: ChatConversation;
  items: ChatStoredItem[];
}

/** One event of a streamed answer. */
export type ChatStreamEvent =
  | {
      type: 'text_start' | 'thinking_start' | 'done';
    }
  | {
      type: 'text' | 'thinking' | 'error' | 'refusal';
      text: string;
    }
  | {
      type: 'title';
      title: string;
    }
  | {
      type: 'tool_call';
      id: string;
      name: string;
      input?: unknown;
    }
  | {
      type: 'tool_result';
      id: string;
      summary: string;
      is_error: boolean;
    }
  | {
      type: 'ui_action';
      id: string;
      action: ChatUiAction;
    }
  | ({
      type: 'usage';
      model: string;
      today: number;
      limit: number;
    } & ChatTokenCounts);

/** Token counts of one answer or one day. */
export interface ChatTokenCounts {
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens: number;
  cache_creation_input_tokens: number;
}

/** Today's token use against the daily limit. */
export interface ChatUsage extends ChatTokenCounts {
  day: string;
  responses: number;
  billable: number;
  limit: number;
  model: string;
  effort: string;
}
