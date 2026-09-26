import { apiClient } from '../api/apiClient';
import type { IndicatorDescription } from '../api/types';

/** Loads the indicator catalogue once per page load and shares it between charts. */
export class IndicatorCatalogueStore {
  private loading: Promise<IndicatorDescription[]> | null = null;

  /**
   * Gives the catalogue, asking the server only the first time.
   * @returns One description per indicator.
   * @throws ApiError when the catalogue could not be loaded; the next call tries again.
   */
  load(): Promise<IndicatorDescription[]> {
    if (this.loading === null) {
      this.loading = apiClient.fetchIndicators().catch((caught: unknown) => {
        this.loading = null;
        throw caught;
      });
    }
    return this.loading;
  }
}

export const indicatorCatalogueStore = new IndicatorCatalogueStore();
