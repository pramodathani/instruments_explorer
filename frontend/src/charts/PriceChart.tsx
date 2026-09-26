import Highcharts from 'highcharts/highstock';
import { HighchartsReact } from 'highcharts-react-official';
import { useMemo } from 'react';

import type { CandleRow, IndicatorResult } from '../api/types';
import { useMotionLevel } from '../components/useMotionLevel';
import { useTheme } from '../components/useTheme';
import { chartOptionsBuilder } from './chartOptionsBuilder';
import { highchartsTheme } from './highchartsTheme';

const PRICE_PANE_PIXELS = 380;
const LOWER_PANE_PIXELS = 120;

/** Props for PriceChart. */
interface PriceChartProps {
  candles: CandleRow[];
  indicators: IndicatorResult[];
  hasVolume: boolean;
  intraday: boolean;
}

/**
 * The Highcharts Stock chart: candles, volume and indicators, rebuilt when the theme changes.
 * @param props The candles, indicators, whether volume exists, and whether the candles are intraday.
 * @returns The chart.
 */
export function PriceChart(props: PriceChartProps) {
  const { candles, indicators, hasVolume, intraday } = props;
  const theme = useTheme();
  const level = useMotionLevel();

  const options = useMemo(() => {
    highchartsTheme.apply();
    const lowerPanes = chartOptionsBuilder.lowerPaneCount(indicators, hasVolume);
    const built = chartOptionsBuilder.build({
      candles,
      indicators,
      hasVolume,
      colors: highchartsTheme.colors(),
      animate: level !== 'off',
      intraday,
    });
    built.chart = {
      ...built.chart,
      height: PRICE_PANE_PIXELS + lowerPanes * LOWER_PANE_PIXELS + 90,
    };
    return built;
  }, [candles, indicators, hasVolume, intraday, level, theme]);

  return <HighchartsReact key={theme} highcharts={Highcharts} constructorType="stockChart" options={options} />;
}
