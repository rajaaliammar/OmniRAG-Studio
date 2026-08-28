"""Vector store adapters (embeddings, ChromaDB, retrieval)."""

from backend.vectorstore.chroma_db import (
    add_documents_to_vectorstore,
    delete_collection,
    get_chroma_client,
    get_or_create_collection,
    list_collections,
)
from backend.vectorstore.embeddings import embed_documents, embed_query, get_embeddings
from backend.vectorstore.errors import VectorStoreError
from backend.vectorstore.retriever import get_retriever, similarity_search

__all__ = [
    "VectorStoreError",
    "add_documents_to_vectorstore",
    "delete_collection",
    "embed_documents",
    "embed_query",
    "get_chroma_client",
    "get_embeddings",
    "get_or_create_collection",
    "get_retriever",
    "list_collections",
    "similarity_search",
]
