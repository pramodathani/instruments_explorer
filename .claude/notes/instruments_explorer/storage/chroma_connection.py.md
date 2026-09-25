# chroma_connection.py

The status check uses plain httpx against ChromaDB's HTTP API rather than the `chromadb` client, because the client's `HttpClient` is synchronous and would block the event loop. The knowledge pipeline in phase 5 will use the `chromadb` client for collections, run in worker threads.

`/api/v2/version` returns the HTTP API version (`1.0.0` on server 1.5.9), not the package version, so the detail is labelled "API version".
