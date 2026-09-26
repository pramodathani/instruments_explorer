# knowledge/ (frontend)

`CompanyPanel` sits on every instrument page, loaded lazily. For an index, commodity or currency it shows only the server's reason that the instrument is not a company.

When a fetch starts, the panel shows the job at once from the POST answer, then follows it through `LiveSocket.onFetchJob`, filtered to its own company. When the job finishes it reloads the company, so the profile, ratios and documents appear without a page refresh.

The source checkboxes start with every available source ticked; unavailable ones are greyed out with their reason as a tooltip. Yahoo's fundamentals are shown only for a curated set of fields, each with a formatter: market cap in crore, margins and growth as percentages, and ratios to one or two decimals.

Browser automation note: `form_input` plus Enter did not submit these forms on 2026-09-26, while real typing does. Click the submit button, or dispatch real key events, when testing.
