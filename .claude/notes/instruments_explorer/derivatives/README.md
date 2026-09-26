# derivatives/

## Why Black-76 on the forward

Indian index and stock options are European and settle against the underlying at expiry. The future of the same expiry is the market's own forward price for that day. Pricing on it with Black's 1976 model therefore needs no guess at dividends or financing costs, which Black-Scholes on the spot would need.

When no same-expiry future is priced, the spot is carried forward at the risk-free rate (6.5% by default), and failing that the nearest future is used as it is. `forward_source` says which, and the page shows it under the forward.

## Bisection, not Newton

Implied volatility is found by bisection between 0.1% and 500%. Newton's method is faster, but it jumps off when vega is tiny (deep in or out of the money, or on expiry day), exactly where a chain has many strikes. Option price rises strictly with volatility, so bisection always converges, and a few dozen steps per contract are cheap: a 538-contract NIFTY expiry takes well under a second.

A price at or below the discounted intrinsic value, or above what 500% volatility gives, has no answer and returns None.

## Which price to trust

On 2026-09-26 the 3 November NIFTY calls above the money showed implied volatility near 19% against 11% for their neighbours. Every one had zero volume that day. Its "last price" was the close of the last day it traded, when NIFTY stood higher, so it was far above today's value, and the bid and offer were too wide or one-sided to use instead.

The rule is therefore:

1. Use the mid of the best bid and offer when both exist and the offer is at most twice the bid.
2. Otherwise use the last price, but only when the contract traded today.
3. Otherwise show no implied volatility; the last price is still shown in the chain.

## Max pain

Max pain is the settlement price, among the listed strikes, at which option holders as a whole would collect the least at expiry. For each candidate strike it sums call payouts `OI × max(0, S − K)` and put payouts `OI × max(0, K − S)`. It is a popular talking point rather than a forecast, and the page describes it plainly.

## The surface

The surface's first version took only the strikes every expiry listed. The quarterly expiries list strikes only every 500 to 1,000 points, so the grid collapsed to 15 coarse, lopsided strikes. The grid now comes from the nearest expiry within 8% of its forward, thinned evenly to 31 strikes.

Each expiry fills a strike it does not list by straight-line interpolation between its nearest priced strikes, never beyond them. Expiries with fewer than five priced strikes in range are left out.

Each point uses the out-of-the-money option (a put below the forward, a call above), because those trade most. A spike filter drops points more than 30% or 3 volatility points from the median of their four nearest neighbours. The window slides inward at the edges; a first version shrank it there, and a spike next to the last strike then took the last strike out with it.
