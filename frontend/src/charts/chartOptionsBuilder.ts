import type Highcharts from 'highcharts/highstock';

import type { CandleRow, IndicatorResult } from '../api/types';
import type { ChartColors } from './highchartsTheme';

const PANEL_HEIGHT_PERCENT = 17;
const VOLUME_HEIGHT_PERCENT = 14;
const GAP_PERCENT = 2;

/** Everything a chart is built from. */
export interface ChartInput {
  candles: CandleRow[];
  indicators: IndicatorResult[];
  hasVolume: boolean;
  colors: ChartColors;
  animate: boolean;
  intraday: boolean;
}

/** Turns candles and indicator results into Highcharts Stock options: a price pane, a volume pane and one pane per panel indicator. */
export class ChartOptionsBuilder {
  /**
   * Counts the panes below the price pane, so the page can size the chart.
   * @param indicators The computed indicators.
   * @param hasVolume Whether a volume pane is shown.
   * @returns How many panes sit below the price.
   */
  lowerPaneCount(indicators: IndicatorResult[], hasVolume: boolean): number {
    let count = hasVolume ? 1 : 0;
    for (const indicator of indicators) {
      if (indicator.placement === 'panel') {
        count += 1;
      }
    }
    return count;
  }

  /**
   * Builds the chart's options.
   * @param input The candles, indicators and colours.
   * @returns The Highcharts Stock options.
   */
  build(input: ChartInput): Highcharts.Options {
    const { candles, indicators, hasVolume, colors } = input;
    const panels: IndicatorResult[] = [];
    for (const indicator of indicators) {
      if (indicator.placement === 'panel') {
        panels.push(indicator);
      }
    }
    const lowerHeights = (hasVolume ? VOLUME_HEIGHT_PERCENT + GAP_PERCENT : 0) + panels.length * (PANEL_HEIGHT_PERCENT + GAP_PERCENT);
    const priceHeight = 100 - lowerHeights;
    const yAxes: Highcharts.YAxisOptions[] = [
      {
        id: 'price-axis',
        height: `${priceHeight}%`,
        opposite: true,
        labels: {
          align: 'left',
          x: 6,
        },
        crosshair: {
          color: colors.muted,
          dashStyle: 'Dash',
        },
      },
    ];
    let top = priceHeight + GAP_PERCENT;
    const series: Highcharts.SeriesOptionsType[] = [
      {
        type: 'candlestick',
        id: 'price',
        name: 'Price',
        data: this.ohlc(candles),
        color: colors.down,
        lineColor: colors.down,
        upColor: colors.up,
        upLineColor: colors.up,
        yAxis: 'price-axis',
        dataGrouping: {
          enabled: false,
        },
      },
    ];
    if (hasVolume) {
      yAxes.push({
        id: 'volume-axis',
        top: `${top}%`,
        height: `${VOLUME_HEIGHT_PERCENT}%`,
        offset: 0,
        opposite: true,
        labels: {
          align: 'left',
          x: 6,
        },
        title: {
          text: 'Volume',
          align: 'high',
          rotation: 0,
          x: -40,
          y: 12,
        },
      });
      series.push({
        type: 'column',
        id: 'volume',
        name: 'Volume',
        data: this.volume(candles, colors),
        yAxis: 'volume-axis',
        borderWidth: 0,
        dataGrouping: {
          enabled: false,
        },
      });
      top += VOLUME_HEIGHT_PERCENT + GAP_PERCENT;
    }
    let colorIndex = 0;
    for (const indicator of indicators) {
      if (indicator.placement === 'price') {
        for (const output of indicator.outputs) {
          series.push({
            type: 'line',
            name: indicator.outputs.length > 1 ? `${indicator.title} ${output.label}` : indicator.title,
            data: output.points,
            yAxis: 'price-axis',
            color: colors.series[colorIndex % colors.series.length],
            lineWidth: indicator.key === 'sar' ? 0 : 1.5,
            marker: {
              enabled: indicator.key === 'sar',
              radius: 1.6,
              symbol: 'circle',
            },
            dashStyle: indicator.key === 'bbands' && output.key !== 'middle' ? 'ShortDash' : 'Solid',
            enableMouseTracking: true,
          });
        }
        colorIndex += 1;
      }
    }
    for (const indicator of panels) {
      const axisId = `panel-axis-${indicator.id}`;
      const plotLines: Highcharts.YAxisPlotLinesOptions[] = [];
      for (const level of indicator.reference_lines) {
        plotLines.push({
          value: level,
          color: colors.border,
          dashStyle: 'Dash',
          width: 1,
          zIndex: 3,
        });
      }
      yAxes.push({
        id: axisId,
        top: `${top}%`,
        height: `${PANEL_HEIGHT_PERCENT}%`,
        offset: 0,
        opposite: true,
        plotLines,
        labels: {
          align: 'left',
          x: 6,
        },
        title: {
          text: indicator.title,
          align: 'high',
          rotation: 0,
          x: -40,
          y: 12,
          style: {
            color: colors.series[colorIndex % colors.series.length],
          },
        },
      });
      top += PANEL_HEIGHT_PERCENT + GAP_PERCENT;
      let lineIndex = 0;
      for (const output of indicator.outputs) {
        const color = colors.series[(colorIndex + lineIndex) % colors.series.length];
        if (output.key === 'histogram') {
          series.push({
            type: 'column',
            name: `${indicator.title} ${output.label}`,
            data: output.points,
            yAxis: axisId,
            color: colors.up,
            negativeColor: colors.down,
            borderWidth: 0,
            dataGrouping: {
              enabled: false,
            },
          });
        } else {
          series.push({
            type: 'line',
            name: indicator.outputs.length > 1 ? `${indicator.title} ${output.label}` : indicator.title,
            data: output.points,
            yAxis: axisId,
            color,
            lineWidth: 1.5,
          });
        }
        lineIndex += 1;
      }
      colorIndex += 1;
    }
    for (const indicator of indicators) {
      if (indicator.placement === 'markers') {
        series.push(...this.flags(indicator, colors));
      }
    }
    return {
      chart: {
        animation: input.animate,
        spacing: [
          8,
          4,
          8,
          4,
        ],
      },
      legend: {
        enabled: indicators.length > 0,
        align: 'left',
        verticalAlign: 'top',
        floating: false,
      },
      navigator: {
        enabled: true,
        height: 34,
      },
      xAxis: {
        crosshair: {
          color: colors.muted,
          dashStyle: 'Dash',
        },
        ordinal: true,
      },
      yAxis: yAxes,
      tooltip: {
        split: true,
        valueDecimals: 2,
        xDateFormat: input.intraday ? '%a %e %b %Y, %H:%M' : '%a %e %b %Y',
      },
      plotOptions: {
        series: {
          animation: input.animate
            ? {
                duration: 600,
              }
            : false,
        },
      },
      series,
    };
  }

  /**
   * Picks the open, high, low and close of each candle.
   * @param candles The candle rows.
   * @returns [time, open, high, low, close] points.
   */
  private ohlc(candles: CandleRow[]): [number, number | null, number | null, number | null, number | null][] {
    const points: [number, number | null, number | null, number | null, number | null][] = [];
    for (const candle of candles) {
      points.push([candle[0], candle[1], candle[2], candle[3], candle[4]]);
    }
    return points;
  }

  /**
   * Colours each candle's volume bar by whether the candle closed up or down.
   * @param candles The candle rows.
   * @param colors The theme's colours.
   * @returns Volume points with their colours.
   */
  private volume(candles: CandleRow[], colors: ChartColors): Highcharts.PointOptionsObject[] {
    const points: Highcharts.PointOptionsObject[] = [];
    for (const candle of candles) {
      const rising = (candle[4] ?? 0) >= (candle[1] ?? 0);
      points.push({
        x: candle[0],
        y: candle[5],
        color: rising ? colors.upTint.replace(/[\d.]+\)$/, '0.55)') : colors.downTint.replace(/[\d.]+\)$/, '0.55)'),
      });
    }
    return points;
  }

  /**
   * Makes one flag series per pattern, so each pattern can be hidden from the legend.
   * @param indicator The patterns result.
   * @param colors The theme's colours.
   * @returns Flag series placed on the candles.
   */
  private flags(indicator: IndicatorResult, colors: ChartColors): Highcharts.SeriesOptionsType[] {
    const byPattern = new Map<string, Highcharts.PointOptionsObject[]>();
    const labels = new Map<string, string>();
    for (const marker of indicator.markers) {
      const points = byPattern.get(marker.pattern) ?? [];
      points.push({
        x: marker.time,
        title: marker.label.slice(0, 1),
        text: `${marker.label} (${marker.bullish ? 'bullish' : 'bearish'})`,
        fillColor: marker.bullish ? colors.upTint : colors.downTint,
        color: marker.bullish ? colors.up : colors.down,
      });
      byPattern.set(marker.pattern, points);
      labels.set(marker.pattern, marker.label);
    }
    const series: Highcharts.SeriesOptionsType[] = [];
    for (const [pattern, points] of byPattern) {
      series.push({
        type: 'flags',
        name: labels.get(pattern) ?? pattern,
        data: points,
        onSeries: 'price',
        shape: 'circlepin',
        width: 14,
        style: {
          color: colors.ink,
          fontSize: '9px',
        },
        visible: pattern !== 'doji' && pattern !== 'harami',
      });
    }
    return series;
  }
}

export const chartOptionsBuilder = new ChartOptionsBuilder();
