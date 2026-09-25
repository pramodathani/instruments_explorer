# status_routes.py

The route checks every store at once with `asyncio.gather`, so a store that is down costs one timeout rather than one per store.

The checkers are described by a `Protocol` rather than a base class, because `MongoConnection` and `ChromaConnection` share no mechanism, only the shape of `check()`.

The assistant section reports only whether a key is set and which model is used, never the key itself.
