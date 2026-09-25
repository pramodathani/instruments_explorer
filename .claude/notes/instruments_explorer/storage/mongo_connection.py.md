# mongo_connection.py

This uses pymongo's own asynchronous client (`pymongo.AsyncMongoClient`) rather than Motor, which is being retired in favour of it. There is one client for the whole process, because a MongoDB client holds a connection pool and is meant to be shared.

The server-selection and connect timeouts come from `store_timeout_seconds`, so the status route answers within a few seconds when the container is down instead of waiting pymongo's default thirty seconds. The error detail keeps only the text before the first comma, because pymongo's full message lists its whole topology description.
