# screener/ (frontend)

## Presets

Seven presets are one-click screens: oversold, overbought, golden cross, near 52-week high, volume spike, strong uptrend, and momentum turning up. Each sets the conditions and a sensible sort. They are only starting points, and every condition can be edited as a chip afterwards.

## The heatmap

`SectorHeatmap` is a two-level Highcharts treemap: sectors, then stocks. Box size is the average daily traded value, so large, liquid companies dominate as they do in the market. Colour blends from a neutral surface towards the theme's up or down colour, reaching full strength at a 4% move.

The colours are computed per point instead of through a colour axis, which avoids loading Highcharts' separate coloraxis module. `allowTraversingTree` lets a click on a sector zoom into it; a click on a stock opens its instrument page.

## The treemap module

`highcharts/modules/treemap` is a UMD module that attaches to the Highcharts instance on the shared `_Highcharts` global. Importing it after `highcharts/highstock` therefore registers the treemap type on the same instance the price chart uses; it was checked in the browser on 2026-09-26.
