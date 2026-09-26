import Highcharts from 'highcharts/highstock';

import { cssColor } from '../utilities/cssColor';

/** The colours a chart needs, read from the page's CSS tokens. */
export interface ChartColors {
  ink: string;
  muted: string;
  grid: string;
  border: string;
  surface: string;
  up: string;
  down: string;
  upTint: string;
  downTint: string;
  series: string[];
}

/** Makes Highcharts look like the rest of the page, in whichever theme is shown. */
export class HighchartsTheme {
  /**
   * Reads the current theme's chart colours.
   * @returns The colours.
   */
  colors(): ChartColors {
    return {
      ink: cssColor.read('--ink', '#e8eaed'),
      muted: cssColor.read('--ink-muted', '#9aa0a6'),
      grid: cssColor.read('--gridline', 'rgba(154, 160, 166, 0.14)'),
      border: cssColor.read('--border', 'rgba(154, 160, 166, 0.22)'),
      surface: cssColor.read('--surface-solid', '#262a34'),
      up: cssColor.read('--up', '#5bb974'),
      down: cssColor.read('--down', '#e25f5b'),
      upTint: cssColor.read('--up-tint', 'rgba(91, 185, 116, 0.15)'),
      downTint: cssColor.read('--down-tint', 'rgba(226, 95, 91, 0.15)'),
      series: [
        cssColor.read('--accent', '#ff8a65'),
        cssColor.read('--second', '#64b5f6'),
        cssColor.read('--series-3', '#b39ddb'),
        cssColor.read('--series-4', '#4dd0e1'),
        cssColor.read('--series-5', '#ffd54f'),
        cssColor.read('--series-6', '#f48fb1'),
        cssColor.read('--series-7', '#aed581'),
      ],
    };
  }

  /** Applies the current theme to every chart created from now on. */
  apply(): void {
    const colors = this.colors();
    const font = cssColor.read('--font-family', 'Roboto, sans-serif');
    Highcharts.setOptions({
      colors: colors.series,
      chart: {
        backgroundColor: 'transparent',
        style: {
          fontFamily: font,
        },
      },
      time: {
        timezone: 'Asia/Kolkata',
      },
      lang: {
        thousandsSep: ',',
      },
      credits: {
        enabled: false,
      },
      title: {
        style: {
          color: colors.ink,
        },
      },
      xAxis: {
        gridLineColor: colors.grid,
        lineColor: colors.border,
        tickColor: colors.border,
        labels: {
          style: {
            color: colors.muted,
          },
        },
      },
      yAxis: {
        gridLineColor: colors.grid,
        lineColor: colors.border,
        labels: {
          style: {
            color: colors.muted,
          },
        },
        title: {
          style: {
            color: colors.muted,
          },
        },
      },
      legend: {
        itemStyle: {
          color: colors.ink,
          fontWeight: '400',
        },
        itemHoverStyle: {
          color: colors.series[0],
        },
        itemHiddenStyle: {
          color: colors.muted,
        },
      },
      tooltip: {
        backgroundColor: colors.surface,
        borderColor: colors.border,
        style: {
          color: colors.ink,
        },
      },
      navigator: {
        maskFill: colors.upTint,
        outlineColor: colors.border,
        handles: {
          backgroundColor: colors.surface,
          borderColor: colors.muted,
        },
        series: {
          color: colors.series[1],
          lineColor: colors.series[1],
        },
        xAxis: {
          gridLineColor: colors.grid,
          labels: {
            style: {
              color: colors.muted,
            },
          },
        },
      },
      scrollbar: {
        enabled: false,
      },
      rangeSelector: {
        enabled: false,
      },
      plotOptions: {
        series: {
          animation: {
            duration: 600,
          },
        },
      },
    });
  }
}

export const highchartsTheme = new HighchartsTheme();
