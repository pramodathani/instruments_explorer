# universe/

## Why the layout is computed on the server

The layout needs every instrument's asset class, underlying, expiry, strike and option type, which live in the SQLite index. Sending those to the browser and laying out there would move more data than sending the finished positions. The server rounds positions to one decimal, which keeps the JSON small without visible loss.

## How clusters are packed

The first version used a fixed spiral step, which made the fixed income galaxy (about 21,000 bonds, each its own underlying) about 3,800 units wide, far larger than the ring, so galaxies overlapped. Each cluster now takes room in proportion to its footprint (its furthest instrument plus a gap), and its distance from the galaxy's centre is the radius of a disc holding every earlier cluster's room. This is the same packing as a sunflower head with seeds of different sizes. The ring's radius is then the smallest at which neighbouring galaxies, with a 15% margin, do not touch.

On the 2026-09-25 index the ring's radius came out at about 514 units without options and about 678 with them. The largest galaxy radius was fixed income at about 356.

## Sizes and timings

Measured on 2026-09-26 in the browser, through the check copy on port 8101:

| Map | Instruments | JSON before compression | Load time |
|---|---|---|---|
| Without options | 43,461 | 3.7 MB | 0.85 s |
| With options | 236,431 | 23 MB | 4.5 s |

Building the layout itself takes about 0.2 s without options and 0.8 s with them. The service caches it until the index file changes, and caches the quote changes for a minute, so repeated loads cost only the transfer.

## Cluster labels

Only the twelve largest underlyings of each galaxy are labelled, because a label is a texture and tens of thousands would be too heavy. Without options, many underlyings tie on size, so the labelled twelve are the alphabetically first among the largest.
