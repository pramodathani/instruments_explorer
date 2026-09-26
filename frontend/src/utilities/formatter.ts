const SEGMENT_WORDS: Record<string, string> = {
  equities: 'Equities',
  equity: 'Equity',
  indices: 'Indices',
  index: 'Index',
  futures: 'Futures',
  options: 'Options',
  fixed: 'Fixed',
  income: 'income',
  currencies: 'Currencies',
  currency: 'Currency',
  commodities: 'Commodities',
  commodity: 'Commodity',
  mutual: 'Mutual',
  funds: 'funds',
  exchange: 'Exchange',
  traded: 'traded',
  investment: 'Investment',
  trusts: 'trusts',
  uncategorised: 'Uncategorised',
};

const ASSET_CLASS_LABELS: Record<string, string> = {
  equity: 'Equity',
  funds: 'Funds',
  fixed_income: 'Fixed income',
  currency: 'Currency',
  commodity: 'Commodity',
  other: 'Other',
};

const SHAPE_LABELS: Record<string, string> = {
  security: 'Cash',
  future: 'Futures',
  option: 'Options',
};

const OPTION_TYPE_LABELS: Record<string, string> = {
  CE: 'Calls (CE)',
  PE: 'Puts (PE)',
};

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Formats numbers, prices, dates and ubi's names the way the pages show them. */
export class Formatter {
  /**
   * Formats a whole number with Indian digit grouping.
   * @param value The number, or null.
   * @returns The number such as "1,23,456", or a dash for null.
   */
  count(value: number | null | undefined): string {
    if (value === null || value === undefined) {
      return '–';
    }
    return value.toLocaleString('en-IN');
  }

  /**
   * Formats a price with two decimal places, or four for small currency prices.
   * @param value The price, or null.
   * @returns The price, or a dash for null.
   */
  price(value: number | null | undefined): string {
    if (value === null || value === undefined) {
      return '–';
    }
    const decimals = Math.abs(value) < 10 && value !== Math.round(value * 100) / 100 ? 4 : 2;
    return value.toLocaleString('en-IN', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }

  /**
   * Formats a change with its sign.
   * @param value The change, or null.
   * @returns The change such as "+12.50", or a dash for null.
   */
  signedPrice(value: number | null | undefined): string {
    if (value === null || value === undefined) {
      return '–';
    }
    const sign = value > 0 ? '+' : '';
    return `${sign}${this.price(value)}`;
  }

  /**
   * Formats a percentage change with its sign.
   * @param value The percentage, or null.
   * @returns The percentage such as "+1.25%", or a dash for null.
   */
  signedPercent(value: number | null | undefined): string {
    if (value === null || value === undefined) {
      return '–';
    }
    const sign = value > 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
  }

  /**
   * Formats an implied volatility.
   * @param value The volatility in percent, or null.
   * @returns The value such as "11.4%", or a dash for null.
   */
  volatility(value: number | null | undefined): string {
    if (value === null || value === undefined) {
      return '–';
    }
    return `${value.toFixed(1)}%`;
  }

  /**
   * Chooses the colour class for a change.
   * @param value The change, or null.
   * @returns "change-up", "change-down", or an empty string for no change.
   */
  changeClass(value: number | null | undefined): string {
    if (value === null || value === undefined || value === 0) {
      return '';
    }
    return value > 0 ? 'change-up' : 'change-down';
  }

  /**
   * Formats a strike without trailing zeros.
   * @param value The strike, or null.
   * @returns The strike such as "25000" or "82.25", or an empty string for null.
   */
  strike(value: number | null): string {
    if (value === null) {
      return '';
    }
    return value.toLocaleString('en-IN', {
      maximumFractionDigits: 4,
    });
  }

  /**
   * Formats a date written as "YYYY-MM-DD".
   * @param value The date, or null.
   * @returns The date such as "29 Sep 2026", or an empty string for null.
   */
  date(value: string | null): string {
    if (value === null) {
      return '';
    }
    const [year, month, day] = value.split('-');
    const monthIndex = Number(month) - 1;
    if (day === undefined || monthIndex < 0 || monthIndex > 11) {
      return value;
    }
    return `${day} ${MONTHS[monthIndex]} ${year}`;
  }

  /**
   * Formats a month written as "YYYY-MM".
   * @param value The month.
   * @returns The month such as "Sep 2026".
   */
  month(value: string): string {
    const [year, month] = value.split('-');
    const monthIndex = Number(month) - 1;
    if (monthIndex < 0 || monthIndex > 11) {
      return value;
    }
    return `${MONTHS[monthIndex]} ${year}`;
  }

  /**
   * Formats an epoch time as a local time of day.
   * @param epochSeconds The time in epoch seconds, or null.
   * @returns The time such as "14:32:05", or a dash for null.
   */
  time(epochSeconds: number | null | undefined): string {
    if (epochSeconds === null || epochSeconds === undefined) {
      return '–';
    }
    return new Date(epochSeconds * 1000).toLocaleTimeString('en-IN', {
      hour12: false,
    });
  }

  /**
   * Turns a segment name into words.
   * @param bareSegment The segment without its exchange, such as "equity_index_options".
   * @returns The words, such as "Equity index options".
   */
  segment(bareSegment: string): string {
    const words: string[] = [];
    for (const word of bareSegment.split('_')) {
      words.push((SEGMENT_WORDS[word] ?? word).toLowerCase());
    }
    const joined = words.join(' ');
    return joined.charAt(0).toUpperCase() + joined.slice(1);
  }

  /**
   * Names a value of a facet column for display.
   * @param column The facet column.
   * @param value The value.
   * @returns A readable label.
   */
  facetValue(column: string, value: string): string {
    if (column === 'exchange') {
      return value.toUpperCase();
    }
    if (column === 'asset_class') {
      return ASSET_CLASS_LABELS[value] ?? value;
    }
    if (column === 'shape') {
      return SHAPE_LABELS[value] ?? value;
    }
    if (column === 'option_type') {
      return OPTION_TYPE_LABELS[value] ?? value;
    }
    if (column === 'expiry_month') {
      return this.month(value);
    }
    if (column === 'segment') {
      const [exchange, ...rest] = value.split('_');
      if (rest.length === 0) {
        return this.segment(value);
      }
      return `${exchange.toUpperCase()} · ${this.segment(rest.join('_'))}`;
    }
    return value;
  }

  /**
   * Names a shape for display.
   * @param shape "security", "future" or "option".
   * @returns "Cash", "Futures" or "Options".
   */
  shape(shape: string): string {
    return SHAPE_LABELS[shape] ?? shape;
  }
}

export const formatter = new Formatter();
