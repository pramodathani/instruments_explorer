# storage/ repositories

There is one repository class per MongoDB collection: `companies`, `documents` and `fetch_jobs`. Each takes the database object in its constructor, so tests pass `tests/fakes.FakeDatabase`, which implements only the operations these classes use. When a repository needs a new MongoDB feature, add it to the fake as well.

`companies` is keyed by ISIN where one is known. Sources merge their fields with `$set`, and each source records its run under `sources.<key>`, so Yahoo's sector and Screener's classification sit side by side and neither can remove the other's. `name_key` is a lower-case, punctuation-free copy of the name for prefix search.

`documents` is keyed by `FetchedDocument.document_id`, a SHA-1 of the source and the address (or the text when there is no address). Fetching again therefore replaces a document instead of duplicating it, and its chunks are replaced in ChromaDB under the same id.
