# explore/

## The search lives in the address

The whole search (text, filters, strike range and order) is kept in the page's query string through `SearchState`. The back button, reloading and sharing a link therefore all keep it, and there is no second copy of the state to fall out of step. Updates use `replace`, so each keystroke does not add a history entry.

## Typing and requests

The text box writes to the address 250 ms after the last keystroke. Every new search aborts the previous request, so a slow answer can never overwrite a newer one.

## Loading more

The results table loads the next 100 rows when a sentinel under the table scrolls into view (IntersectionObserver). The table itself is not virtualised. Rows are light, and a person rarely scrolls past a few hundred before refining the search.

## While the index builds

A 503 from the search route means the index is being built, which happens after the first start and once each morning. The page then shows the build progress from `/api/instruments/index-status` and retries every two seconds until the index is ready.

## Animation

Result rows enter with a short 3D tilt, staggered by position. Filter counts carry a thin bar showing each value's share, which animates as the counts change. Both are switched off at the reduced and off animation levels.
