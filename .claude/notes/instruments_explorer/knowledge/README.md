# knowledge/

## What was checked before building (2026-09-26)

Each planned source's robots.txt was read with Python's `urllib.robotparser` for the agent `instruments_explorer`, and every allowed address was fetched once. The results shaped the fetcher list:

| Source | Finding | Decision |
|---|---|---|
| NSE `EQUITY_L.csv` | Allowed, 183 kB, every listed equity with name and ISIN | Seeds `companies` and the index's company names |
| NSE corporate announcements API | Allowed, works without cookies | `nse_announcements` fetcher |
| NSE `quote-equity` API | Allowed by robots.txt, but refused (403) even with a session cookie: Akamai bot detection needs JavaScript | Not used; sector and industry come from Yahoo and Screener.in |
| BSE API | Answered with an HTML page instead of JSON | Not used |
| Screener.in company pages | Allowed and works | `screener` fetcher |
| Wikipedia API | 403 without contact details in the user agent, as its robot policy says | `wikipedia` fetcher, off until the user sets a contact |
| CNBC, Investing.com, Economist, Bloomberg, ET, Mint, Moneycontrol RSS | Allowed and work | `rss_news` fetcher |
| CNBC search feed, Google News RSS | Blocked by robots.txt | Not used |
| Bing News RSS search | Allowed and works | `bing_news` fetcher |
| Yahoo Finance via yfinance | 163 fields in 0.5 s | `yahoo` fetcher |

## User agents

Web requests send `Mozilla/5.0 (X11; Linux x86_64) instruments_explorer/0.1`. Several Indian sites refuse agents that do not start like a browser's, and the `instruments_explorer` part still names the tool honestly. robots.txt rules are checked against `instruments_explorer`.

The user's email address is never put in a user agent. Wikipedia's contact value is a setting the user fills in if they want that fetcher.

## Why one job at a time

Jobs run one after another in a single background task. Running them side by side would only queue them anyway behind the polite client's per-site spacing. One at a time also keeps the load on each site obvious: one company's worth of requests, two seconds apart.

## Matching news to a company

Feed headlines rarely use a registered name such as "Reliance Industries Limited". The feed matcher accepts the name without legal suffixes, or the trading symbol as a whole word when it is at least three letters. In the first trial RELIANCE matched nothing by name alone; with the symbol, INFY matched two headlines. The symbol sometimes catches a sister company (Reliance Power), which is acceptable for exploration.

## Embeddings

ChromaDB's default embedding function runs all-MiniLM-L6-v2 through onnxruntime on this machine. The 79 MB model downloads once to `~/.cache/chroma`; after that nothing about the documents leaves the machine. The collection uses cosine distance, and a search score is shown as 1 minus the distance. Chunks are about 900 characters with 150 characters of overlap, cut at sentence boundaries.

## First real run

On 2026-09-26 RELIANCE took 17 seconds end to end: 30 announcements, 16 Yahoo fundamentals, Screener's ratios and four-level classification, and 12 Bing articles. "What does the company do in telecom?" then found a Jio 5G article first, and "recent dividend or board meeting" found NSE filings.
