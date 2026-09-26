import Highcharts from 'highcharts/highstock';
import 'highcharts/modules/treemap';
import { HighchartsReact } from 'highcharts-react-official';
import { useMemo } from 'react';
import { useNavigate } from 'react-router';

import type { ScreenerSector } from '../api/types';
import { highchartsTheme } from '../charts/highchartsTheme';
import { useTheme } from '../components/useTheme';
import { cssColor } from '../utilities/cssColor';

const STRONGEST_MOVE_PERCENT = 4;

/** Props for SectorHeatmap. */
interface SectorHeatmapProps {
  sectors: ScreenerSector[];
}

/**
 * A treemap of the matching stocks: one box per stock, grouped by sector, sized by traded value and coloured by the day's change.
 * @param props The matches grouped by sector.
 * @returns The heatmap.
 */
export function SectorHeatmap(props: SectorHeatmapProps) {
  const { sectors } = props;
  const theme = useTheme();
  const navigate = useNavigate();

  const options = useMemo((): Highcharts.Options => {
    highchartsTheme.apply();
    const colors = highchartsTheme.colors();
    const up = new Highcharts.Color(colors.up);
    const down = new Highcharts.Color(colors.down);
    const neutral = new Highcharts.Color(cssColor.read('--surface-hover', '#2e3340'));
    const colorFor = (change: number | null): string => {
      if (change === null) {
        return neutral.get('rgb') as string;
      }
      const share = Math.min(Math.abs(change) / STRONGEST_MOVE_PERCENT, 1);
      const target = change >= 0 ? up : down;
      return String(neutral.tweenTo(target, 0.25 + share * 0.75));
    };
    const points: Highcharts.PointOptionsObject[] = [];
    for (const sector of sectors) {
      const sectorId = `sector-${sector.sector}`;
      points.push({
        id: sectorId,
        name: `${sector.sector} (${sector.count})`,
      });
      for (const stock of sector.stocks) {
        points.push({
          id: stock.instrument_id,
          parent: sectorId,
          name: stock.symbol,
          value: Math.max(stock.traded_value ?? 0, 1),
          color: colorFor(stock.change_1d),
          custom: {
            change: stock.change_1d,
            company: stock.name,
          },
        });
      }
    }
    return {
      chart: {
        height: 520,
        backgroundColor: 'transparent',
      },
      title: {
        text: undefined,
      },
      legend: {
        enabled: false,
      },
      tooltip: {
        pointFormatter: function (this: Highcharts.Point) {
          const custom = (this.options.custom ?? {}) as { change?: number | null; company?: string | null };
          if (custom.change === undefined) {
            return `<b>${this.name}</b>`;
          }
          const change = custom.change === null ? '–' : `${custom.change > 0 ? '+' : ''}${custom.change.toFixed(2)}%`;
          return `<b>${this.name}</b> ${custom.company ?? ''}<br/>Today: ${change}`;
        },
      },
      series: [
        {
          type: 'treemap',
          layoutAlgorithm: 'squarified',
          allowTraversingTree: true,
          animationLimit: 1000,
          borderColor: colors.surface,
          borderWidth: 1,
          dataLabels: {
            enabled: false,
          },
          levels: [
            {
              level: 1,
              borderWidth: 3,
              borderColor: colors.surface,
              dataLabels: {
                enabled: true,
                align: 'left',
                verticalAlign: 'top',
                style: {
                  fontSize: '12px',
                  fontWeight: '600',
                  color: colors.ink,
                  textOutline: 'none',
                },
              },
            },
            {
              level: 2,
              dataLabels: {
                enabled: true,
                style: {
                  fontSize: '10px',
                  fontWeight: '500',
                  color: colors.ink,
                  textOutline: 'none',
                },
              },
            },
          ],
          data: points,
          point: {
            events: {
              click: function (this: Highcharts.Point) {
                const custom = (this.options.custom ?? {}) as { change?: number | null };
                if (custom.change !== undefined && this.options.id) {
                  navigate(`/instrument/${this.options.id}`);
                }
              },
            },
          },
        },
      ],
    };
  }, [sectors, theme, navigate]);

  if (sectors.length === 0) {
    return <p className="empty-state">No stocks to draw.</p>;
  }
  return <HighchartsReact key={theme} highcharts={Highcharts} options={options} />;
}
