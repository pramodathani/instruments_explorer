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
export type FacetColumn = 'exchange' | 'asset_class' | 'shape' | 'segment' | 'option_type' | 'expiry_month';

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
