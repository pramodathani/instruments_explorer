# docker-compose.yml

## Own containers, own network

The project runs its own MongoDB and ChromaDB rather than sharing unified_broker_interface's containers. ubi deliberately removed its ChromaDB service because nothing there used it, and instruments_explorer must never write to ubi's stores, so sharing ubi's MongoDB would blur that line.

The user asked for the containers to sit on their own Docker network, `instruments_explorer_network`, separate from `unified_broker_interface_network`. The application reaches ubi only through ubi's published host ports, so it never needs to share a container network with it.

## Bound to 127.0.0.1

The sibling projects publish their store ports on 0.0.0.0. Here they are published on 127.0.0.1 only, because the only client is the application on the same machine, and a MongoDB or ChromaDB reachable from the local network would be an unnecessary exposure.

## Ports 3003 and 3004

ubi uses 1002–1004 and tradingmachine uses 2002–2004, so this project takes the 3000 range. There is no Redis or TimescaleDB, so 3002 is unused.

## Named volumes

The data lives in the named volumes `instruments_explorer_mongodb_volume` and `instruments_explorer_chromadb_volume`, following tradingmachine. ubi uses bind mounts under `/mnt/ubi`, but creating a directory under `/mnt` needs root, and named volumes need no setup.

## ChromaDB image pinned to the client version

The image tag `chromadb/chroma:1.5.9` matches the `chromadb` Python package in `requirements.txt`, so the client and server speak the same protocol. Upgrade both together. The server's `/api/v2/version` answers with its HTTP API version (`1.0.0`), not the package version.

## Health checks

The ChromaDB image has no curl or wget, so its health check opens the heartbeat URL through bash's `/dev/tcp`. The MongoDB check pings with `mongosh`, as in tradingmachine.
