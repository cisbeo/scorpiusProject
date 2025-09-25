
"""LlamaIndex integration service for RAG capabilities."""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from llama_index import (Document, ServiceContext, StorageContext,
                         VectorStoreIndex, load_index_from_storage)
from llama_index.embeddings import HuggingFaceEmbedding
from llama_index.llms import OpenAI
from llama_index.node_parser import SimpleNodeParser
from llama_index.query_engine import RetrieverQueryEngine
from llama_index.response_synthesizers import get_response_synthesizer
from llama_index.retrievers import VectorIndexRetriever
from llama_index.storage.docstore import SimpleDocumentStore
from llama_index.storage.index_store import SimpleIndexStore
from llama_index.vector_stores import SimpleVectorStore

from src.core.config import get_settings
from src.processors.base import ProcessingResult

logger = logging.getLogger(__name__)
settings = get_settings()


class LlamaIndexService:
    """Service for document indexing and retrieval using LlamaIndex."""

    def __init__(self, persist_dir: Optional[str] = None):
        """
        Initialize LlamaIndex service.

        Args:
            persist_dir: Directory to persist the index
        """
        # Use /tmp as default if TEMP_PATH not configured
        temp_path = getattr(settings, 'TEMP_PATH', '/tmp/scorpius')
        self.persist_dir = persist_dir or str(Path(temp_path) / "llamaindex_storage")
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

        # Initialize embedding model (using local model for cost efficiency)
        self.embed_model = HuggingFaceEmbedding(
            model_name="sentence-transformers/all-MiniLM-L12-v2",
            cache_folder=str(Path(temp_path) / "embeddings_cache")
        )

        # Initialize service context (without LLM for now, pure retrieval)
        self.service_context = ServiceContext.from_defaults(
            embed_model=self.embed_model,
            chunk_size=512,
            chunk_overlap=50,
            llm=None  # No LLM for pure retrieval, can add later
        )

        # Storage components
        self.docstore = SimpleDocumentStore()
        self.index_store = SimpleIndexStore()
        self.vector_store = SimpleVectorStore()

        # Try to load existing index
        self.index = self._load_or_create_index()

        logger.info(f"LlamaIndex service initialized with persist_dir: {self.persist_dir}")

    def _load_or_create_index(self) -> VectorStoreIndex:
        """Load existing index or create a new one."""
        storage_context = StorageContext.from_defaults(
            docstore=self.docstore,
            index_store=self.index_store,
            vector_store=self.vector_store,
            persist_dir=self.persist_dir
        )

        try:
            # Try to load existing index
            index = load_index_from_storage(
                storage_context,
                service_context=self.service_context
            )
            logger.info("Loaded existing index from storage")
        except Exception as e:
            logger.info(f"Creating new index (no existing index found): {e}")
            # Create new index
            index = VectorStoreIndex.from_documents(
                [],
                service_context=self.service_context,
                storage_context=storage_context
            )

        return index

    def index_document(
        self,
        document_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Index a document for retrieval.

        Args:
            document_id: Unique identifier for the document
            content: Document content to index
            metadata: Additional metadata to store with document
            filename: Original filename

        Returns:
            Indexing result with statistics
        """
        try:
            # Create LlamaIndex document
            doc_metadata = metadata or {}
            doc_metadata.update({
                "document_id": document_id,
                "filename": filename or "unknown",
                "indexed_at": datetime.utcnow().isoformat()
            })

            # Create document with metadata
            document = Document(
                text=content,
                doc_id=document_id,
                metadata=doc_metadata
            )

            # Add to index
            self.index.insert(document)

            # Persist the index
            self.index.storage_context.persist(persist_dir=self.persist_dir)

            # Get statistics
            doc_info = self.index.docstore.get_document(document_id)
            num_nodes = len(self.index.docstore.get_nodes([document_id]))

            result = {
                "success": True,
                "document_id": document_id,
                "num_chunks": num_nodes,
                "content_length": len(content),
                "metadata": doc_metadata
            }

            logger.info(f"Document {document_id} indexed successfully with {num_nodes} chunks")
            return result

        except Exception as e:
            logger.error(f"Error indexing document {document_id}: {e}", exc_info=True)
            return {
                "success": False,
                "document_id": document_id,
                "error": str(e)
            }

    def index_from_processing_result(
        self,
        document_id: str,
        processing_result: ProcessingResult
    ) -> Dict[str, Any]:
        """
        Index a document from a ProcessingResult.

        Args:
            document_id: Document identifier
            processing_result: Result from document processor

        Returns:
            Indexing result
        """
        # Extract content
        content = processing_result.raw_text or ""

        # Build metadata from processing result
        metadata = {
            "processor": processing_result.processor_name,
            "page_count": processing_result.page_count,
            "word_count": processing_result.word_count,
            "processing_time_ms": processing_result.processing_time_ms,
            **processing_result.metadata
        }

        # Add structured content if available
        if processing_result.structured_content:
            # Store titles and sections as metadata
            if "titles" in processing_result.structured_content:
                metadata["titles"] = processing_result.structured_content["titles"]
            if "sections" in processing_result.structured_content:
                # Store section headers for better retrieval
                section_headers = [s.get("header", "") for s in processing_result.structured_content["sections"]]
                metadata["section_headers"] = section_headers

        return self.index_document(
            document_id=document_id,
            content=content,
            metadata=metadata,
            filename=processing_result.metadata.get("filename")
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search indexed documents.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of search results with scores
        """
        try:
            # Create retriever
            retriever = VectorIndexRetriever(
                index=self.index,
                similarity_top_k=top_k,
            )

            # Retrieve nodes
            nodes = retriever.retrieve(query)

            # Format results
            results = []
            for node in nodes:
                result = {
                    "score": node.score,
                    "text": node.node.text[:500],  # First 500 chars
                    "document_id": node.node.metadata.get("document_id"),
                    "filename": node.node.metadata.get("filename"),
                    "metadata": node.node.metadata
                }
                results.append(result)

            logger.info(f"Search for '{query}' returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}", exc_info=True)
            return []

    def query(
        self,
        question: str,
        top_k: int = 3,
        response_mode: str = "compact"
    ) -> Dict[str, Any]:
        """
        Query the index with a question (requires LLM configuration).

        Args:
            question: Question to answer
            top_k: Number of chunks to retrieve
            response_mode: Response synthesis mode

        Returns:
            Query response with answer and sources
        """
        try:
            # For now, return search results as we don't have LLM configured
            search_results = self.search(question, top_k=top_k)

            # Format as query response
            response = {
                "question": question,
                "answer": "LLM not configured. Returning relevant chunks:",
                "sources": search_results,
                "metadata": {
                    "top_k": top_k,
                    "num_results": len(search_results)
                }
            }

            return response

        except Exception as e:
            logger.error(f"Error querying for '{question}': {e}", exc_info=True)
            return {
                "question": question,
                "answer": f"Error: {str(e)}",
                "sources": [],
                "metadata": {"error": True}
            }

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the index."""
        try:
            # Get all document IDs
            doc_ids = list(self.index.docstore.docs.keys())

            stats = {
                "num_documents": len(doc_ids),
                "persist_dir": self.persist_dir,
                "embedding_model": self.embed_model.model_name,
                "chunk_size": self.service_context.chunk_size,
                "chunk_overlap": self.service_context.chunk_overlap,
                "document_ids": doc_ids[:10]  # First 10 IDs
            }

            return stats

        except Exception as e:
            logger.error(f"Error getting index stats: {e}", exc_info=True)
            return {"error": str(e)}

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the index.

        Args:
            document_id: Document to delete

        Returns:
            Success status
        """
        try:
            self.index.delete_ref_doc(document_id)
            self.index.storage_context.persist(persist_dir=self.persist_dir)
            logger.info(f"Document {document_id} deleted from index")
            return True
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}", exc_info=True)
            return False

    def clear_index(self) -> bool:
        """Clear all documents from the index."""
        try:
            # Create new empty index
            self.index = VectorStoreIndex.from_documents(
                [],
                service_context=self.service_context,
                storage_context=StorageContext.from_defaults(
                    docstore=SimpleDocumentStore(),
                    index_store=SimpleIndexStore(),
                    vector_store=SimpleVectorStore(),
                )
            )
            self.index.storage_context.persist(persist_dir=self.persist_dir)
            logger.info("Index cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Error clearing index: {e}", exc_info=True)
            return False
