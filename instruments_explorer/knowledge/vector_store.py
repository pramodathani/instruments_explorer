"""The ChromaDB collection that makes company documents searchable by meaning.

Every document is split into chunks, and each chunk is embedded by ChromaDB's default local model, all-MiniLM-L6-v2, running on this machine. The chromadb client is synchronous, so callers run these methods in a worker thread.

Typical usage example:

  store = VectorStore('127.0.0.1', 3004)
  store.add(document_id, chunks, metadata)
  hits = store.query('who makes solar panels', None, 10)
"""

from collections.abc import Mapping
from typing import Any

import chromadb
import chromadb.errors
import httpx

COLLECTION = 'company_documents'
VECTOR_STORE_ERRORS = (
    ValueError,
    chromadb.errors.ChromaError,
    httpx.HTTPError,
)


class VectorStore:
    """Adds, removes and searches document chunks in ChromaDB.

    Attributes:
        host: ChromaDB's host.
        port: ChromaDB's port.
    """

    def __init__(self, host: str, port: int):
        """Creates the store without connecting yet.

        Args:
            host (str): ChromaDB's host.
            port (int): ChromaDB's port.
        """
        self.host = host
        self.port = port
        self._collection = None

    def add(
        self,
        document_id: str,
        chunks: list[str],
        metadata: Mapping[str, Any],
    ) -> int:
        """Replaces a document's chunks with new ones.

        Args:
            document_id (str): The document's id; its chunks are stored as "<id>:<position>".
            chunks (list[str]): The chunks.
            metadata (Mapping[str, Any]): Fields stored with every chunk, such as "company_key", "source" and "title"; None values are left out.

        Returns:
            int: The number of chunks stored.

        Raises:
            chromadb.errors.ChromaError: ChromaDB refused the request.
            ValueError: ChromaDB could not be reached.
            httpx.HTTPError: The connection to ChromaDB failed part way.
        """
        collection = self._open()
        collection.delete(
            where={
                'document_id': document_id,
            }
        )
        if not chunks:
            return 0
        clean = {}
        for key, value in metadata.items():
            if value is not None:
                clean[key] = value
        clean['document_id'] = document_id
        ids = []
        metadatas = []
        for position in range(len(chunks)):
            ids.append(f'{document_id}:{position}')
            chunk_metadata = dict(clean)
            chunk_metadata['position'] = position
            metadatas.append(chunk_metadata)
        collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)
        return len(chunks)

    def query(
        self,
        text: str,
        company_key: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Finds the chunks closest in meaning to a question.

        Args:
            text (str): The question or phrase.
            company_key (str | None): Search only this company's chunks, or None for all.
            limit (int): The largest number of chunks.

        Returns:
            list[dict[str, Any]]: One {"text", "distance", "metadata"} per chunk, closest first; a smaller distance means closer in meaning.

        Raises:
            chromadb.errors.ChromaError: ChromaDB refused the request.
            ValueError: ChromaDB could not be reached.
            httpx.HTTPError: The connection to ChromaDB failed part way.
        """
        collection = self._open()
        where = None
        if company_key is not None:
            where = {
                'company_key': company_key,
            }
        answer = collection.query(
            query_texts=[
                text,
            ],
            n_results=limit,
            where=where,
        )
        hits = []
        documents = answer['documents'][0] if answer['documents'] else []
        for position, chunk in enumerate(documents):
            hits.append(
                {
                    'text': chunk,
                    'distance': answer['distances'][0][position],
                    'metadata': answer['metadatas'][0][position],
                }
            )
        return hits

    def count(self) -> int:
        """Counts the stored chunks.

        Returns:
            int: The number of chunks.

        Raises:
            chromadb.errors.ChromaError: ChromaDB refused the request.
            ValueError: ChromaDB could not be reached.
            httpx.HTTPError: The connection to ChromaDB failed part way.
        """
        return self._open().count()

    def _open(self) -> Any:
        """Connects on first use and creates the collection if needed.

        Returns:
            Any: The chromadb Collection.
        """
        if self._collection is None:
            client = chromadb.HttpClient(host=self.host, port=self.port)
            self._collection = client.get_or_create_collection(
                COLLECTION,
                metadata={
                    'hnsw:space': 'cosine',
                },
            )
        return self._collection
