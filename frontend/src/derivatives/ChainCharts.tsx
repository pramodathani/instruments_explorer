import Highcharts from 'highcharts/highstock';
import { HighchartsReact } from 'highcharts-react-official';
import { useMemo } from 'react';

import type { ChainRow, OptionChain } from '../api/types';
import { highchartsTheme } from '../charts/highchartsTheme';
import { useTheme } from '../components/useTheme';
import { formatter } from '../utilities/formatter';

/** Props for ChainCharts. */
interface ChainChartsProps {
  chain: OptionChain;
  rows: ChainRow[];
}

/**
 * Two charts of the chain: open interest by strike, and the implied volatility smile, with the forward and max pain marked.
 * @param props The chain and the rows to chart.
 * @returns The charts.
 */
export function ChainCharts(props: ChainChartsProps) {
  const { chain, rows } = props;
  const theme = useTheme();

  const options = useMemo(() => {
    highchartsTheme.apply();
    const colors = highchartsTheme.colors();
    const strikes: string[] = [];
    const callOi: (number | null)[] = [];
    const putOi: (number | null)[] = [];
    const callIv: (number | null)[] = [];
    const putIv: (number | null)[] = [];
    let forwardPosition: number | null = null;
    let maxPainPosition: number | null = null;
    rows.forEach((row, position) => {
      strikes.push(formatter.strike(row.strike));
      callOi.push(row.call?.oi ?? null);
      putOi.push(row.put?.oi ?? null);
      callIv.push(row.call?.iv ?? null);
      putIv.push(row.put?.iv ?? null);
      if (chain.forward !== null && forwardPosition === null && row.strike >= chain.forward) {
        forwardPosition = position;
      }
      if (row.strike === chain.max_pain) {
        maxPainPosition = position;
      }
    });
    const markers: Highcharts.XAxisPlotLinesOptions[] = [];
    if (forwardPosition !== null) {
      markers.push({
        value: forwardPosition - 0.5,
        color: colors.series[0],
        width: 2,
        dashStyle: 'Dash',
        zIndex: 4,
        label: {
          text: `Forward ${formatter.price(chain.forward)}`,
          style: {
            color: colors.series[0],
          },
        },
      });
    }
    if (maxPainPosition !== null) {
      markers.push({
        value: maxPainPosition,
        color: colors.muted,
        width: 1,
        dashStyle: 'ShortDot',
        zIndex: 4,
        label: {
          text: 'Max pain',
          y: 30,
          style: {
            color: colors.muted,
          },
        },
      });
    }
    const common: Highcharts.Options = {
      chart: {
        height: 300,
        backgroundColor: 'transparent',
      },
      xAxis: {
        categories: strikes,
        plotLines: markers,
        labels: {
          step: Math.max(1, Math.round(strikes.length / 12)),
          rotation: -40,
        },
      },
      legend: {
        enabled: true,
        align: 'left',
        verticalAlign: 'top',
      },
      tooltip: {
        shared: true,
      },
    };
    const openInterest: Highcharts.Options = {
      ...common,
      title: {
        text: 'Open interest by strike',
        align: 'left',
        style: {
          fontSize: '14px',
        },
      },
      yAxis: {
        title: {
          text: undefined,
        },
      },
      plotOptions: {
        column: {
          grouping: true,
          borderWidth: 0,
          pointPadding: 0.05,
          groupPadding: 0.1,
        },
      },
      series: [
        {
          type: 'column',
          name: 'Call OI',
          data: callOi,
          color: colors.down,
        },
        {
          type: 'column',
          name: 'Put OI',
          data: putOi,
          color: colors.up,
        },
      ],
    };
    const smile: Highcharts.Options = {
      ...common,
      title: {
        text: 'Implied volatility smile',
        align: 'left',
        style: {
          fontSize: '14px',
        },
      },
      yAxis: {
        title: {
          text: undefined,
        },
        labels: {
          format: '{value}%',
        },
      },
      series: [
        {
          type: 'line',
          name: 'Call IV',
          data: callIv,
          color: colors.series[0],
          connectNulls: true,
        },
        {
          type: 'line',
          name: 'Put IV',
          data: putIv,
          color: colors.series[1],
          connectNulls: true,
        },
      ],
    };
    return {
      openInterest,
      smile,
    };
  }, [chain, rows, theme]);

  return (
    <div className="chain-charts">
      <div className="chain-chart">
        <HighchartsReact key={`oi-${theme}`} highcharts={Highcharts} options={options.openInterest} />
      </div>
      <div className="chain-chart">
        <HighchartsReact key={`smile-${theme}`} highcharts={Highcharts} options={options.smile} />
      </div>
    </div>
  );
}
