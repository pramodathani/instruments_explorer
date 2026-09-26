# derivatives/

## Layout

The layout follows the familiar option chain: calls on the left, strikes in the middle, puts on the right. Open interest sits at the outer edges with bars, so the biggest positions stand out at a glance. In-the-money cells are shaded: calls below the forward, puts above it. The at-the-money strike is filled with the accent colour and scrolled into view when the underlying or expiry changes.

By default only 15 strikes each side of the money are shown; a NIFTY weekly expiry lists about 270 strikes, most of them far out and untraded. A checkbox shows them all.

## Refreshing

The chain is fetched again every five seconds while the tab is visible. It reads ubi's live hash, which costs milliseconds, so polling is cheaper and simpler than subscribing several hundred contracts on the live WebSocket. The surface is fetched only when its tab is opened, because it builds up to 16 chains.

## Choosing the first underlying

With nothing in the address, the page selects the first underlying of the unfiltered list, which ranks equity indices first (SENSEX, NIFTY, BANKNIFTY and so on). The earliest expiry that has not yet passed is then selected.

## Charts and 3D

The open-interest and smile charts use the same Highcharts theme as the price chart, with the forward and max pain marked as plot lines. The 3D surface (`three/surfaceScene.ts`) triangulates only the quads whose four corners have a value, so gaps stay visibly empty instead of being faked. Labels are canvas-texture sprites that always face the camera.
