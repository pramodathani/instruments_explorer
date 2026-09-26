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

## Headquarters and key people

Added on 2026-09-26 at the user's request: a satellite globe with a dot at each company's headquarters, and a "key people" section with the CEO, CFO, other chief officers and the board of directors.

### Where the data comes from

| Data | Source | Why |
|---|---|---|
| Headquarters address | Yahoo Finance (`address1`, `address2`, `city`, `zip`, `country`, `phone`) | Already fetched; complete for Indian listed companies, for example "3rd Floor 222 Nariman Point, Mumbai 400021" for Reliance. |
| Officers (CEO, CFO, other chief officers, executive directors, company secretary) | Yahoo Finance `companyOfficers`, with ages | Already fetched. Yahoo leaves out independent and non-executive directors. |
| Full board and key managerial personnel | Zaubacorp, which republishes the Ministry of Corporate Affairs registry, with DIN and appointment date | Checked on 2026-09-26. |
| People in uploaded documents | Claude reads the passages of an uploaded annual report that mention directors or officers | The user asked for uploads as a third source. |

Other board sources checked on 2026-09-26, and why they were not used:

- **Tofler** has the same registry data, and the user first chose it. But its company pages are addressed by the registration number (CIN), and its search endpoints (`/findcompany`, `/cnamesearch`, `/basicsearch`) are disallowed by its robots.txt; the `/search` page fills its results with JavaScript from those endpoints. Zaubacorp's search is allowed and returns the CIN, so it replaced Tofler.
- **Moneycontrol, BSE and Wikidata** answered 403 even to the robots.txt request without an identified agent.
- **MarketScreener** has executive and board tables, but its pages are addressed by an internal id: a guessed Reliance address served Kotak Mahindra Bank, so companies cannot be matched reliably.
- **Economic Times and Trendlyne** returned 404 for guessed addresses and were not pursued.

Neither Zaubacorp's nor Tofler's terms of use were read; the user accepted that caveat.

### Placing the dot

OpenStreetMap's Nominatim disallows automated use in its robots.txt. GeoNames publishes every Indian postcode with coordinates in IN.zip (1.7 MB), but download.geonames.org's robots.txt disallows everything, so the user downloads the file once by hand into `data/geonames/`. `PostcodeGeocoder` reads IN.zip or IN.txt, averages the places sharing a postcode, and falls back to the average of a city's postcodes, mapping old city names such as Bangalore to current ones. Coordinates are worked out when read rather than stored, so downloading the file later places every stored address at once.

### Matching people across sources

Yahoo writes "Mr. Panda Madhusudana Siva Prasad" and the registry "MADHUSUDANA SIVAPRASAD PANDA". `KeyPeopleBook` matches by the words of the names in any order, allowing two neighbouring words to be joined. Every word of the shorter name must match, and when the longer name has extra words, the first words must also match, because Indian names often carry the father's name and the surname: "Mukesh Ambani" must not merge with "Anant Mukesh Ambani", nor Anant with his brother Akash Mukesh Ambani.

Each source is stored under its own key (`key_people.yahoo`, `key_people.zaubacorp`, `key_people.upload`) so sources never overwrite each other, and the merged view is worked out when read.

### Search and the assistant

Whenever a fetch changes the headquarters or key people, `KnowledgeService` rewrites one "key people and headquarters" passage for the company in ChromaDB, under a fixed identity (`key_people:<company key>`) so it replaces the previous version instead of adding another. This lets knowledge search and the chat assistant answer questions such as "who is the CFO of Infosys".

### Reading uploads with Claude

`KeyPeopleExtractor` sends only the passages around mentions of directors, officers or the board, at most 40,000 characters, to the configured model at `low` effort with a JSON schema for the answer. Its tokens are added to the chat's daily usage, so the daily limit covers it too. It runs only when the user presses the button for a chosen document, never automatically on upload.

### Locating every index company

`HeadquartersSweep` fetches Yahoo's profile for each Nifty Total Market company that has no headquarters yet, one at a time with the polite interval between them, when the user presses the button on the Earth page. At two seconds apart, 750 companies take about 25 minutes. It also fills Yahoo's officers for each company.
