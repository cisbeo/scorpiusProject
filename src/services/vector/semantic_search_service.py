"""Semantic search service using pgvector for document embeddings."""

import asyncio
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session

logger = logging.getLogger(__name__)


class SemanticSearchService:
    """
    Service for semantic search using vector embeddings.
    
    Features:
    - Store document chunks with embeddings
    - Semantic similarity search
    - Hybrid search (semantic + keyword)
    - Metadata filtering
    - French-optimized embeddings
    """
    
    def __init__(self):
        """Initialize semantic search service."""
        self.embedding_model = None
        self.embedding_dimension = 768  # For sentence-transformers
        self._initialize_embedding_model()
    
    def _initialize_embedding_model(self):
        """Initialize the embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
            # Use French-optimized model or multilingual
            self.embedding_model = SentenceTransformer('distiluse-base-multilingual-cased-v1')
            logger.info("Embedding model initialized successfully")
        except ImportError:
            logger.warning("sentence-transformers not installed. Install with: pip install sentence-transformers")
    
    async def ensure_vector_extension(self, db: AsyncSession):
        """Ensure pgvector extension is installed."""
        try:
            await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await db.commit()
            logger.info("pgvector extension ensured")
        except Exception as e:
            logger.error(f"Error ensuring pgvector extension: {e}")
            await db.rollback()
    
    async def create_chunks_table(self, db: AsyncSession):
        """
        Create table for document chunks with embeddings.
        
        Args:
            db: Database session
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS document_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID REFERENCES procurement_documents(id) ON DELETE CASCADE,
            
            -- Content
            content TEXT NOT NULL,
            embedding vector(768),
            
            -- Metadata
            page_number INTEGER,
            section_type VARCHAR(50),
            section_title TEXT,
            chunk_index INTEGER,
            chunk_size INTEGER,
            
            -- French entities (JSONB for flexibility)
            entities JSONB DEFAULT '[]',
            siret_numbers TEXT[],
            dates DATE[],
            amounts NUMERIC[],
            
            -- Search optimization
            tsv tsvector GENERATED ALWAYS AS (to_tsvector('french', content)) STORED,
            
            -- Timestamps
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
            ON document_chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        
        CREATE INDEX IF NOT EXISTS idx_chunks_tsv 
            ON document_chunks USING GIN(tsv);
        
        CREATE INDEX IF NOT EXISTS idx_chunks_document 
            ON document_chunks(document_id);
        
        CREATE INDEX IF NOT EXISTS idx_chunks_section 
            ON document_chunks(section_type);
        
        CREATE INDEX IF NOT EXISTS idx_chunks_entities 
            ON document_chunks USING GIN(entities);
        """
        
        try:
            await db.execute(text(create_table_sql))
            await db.commit()
            logger.info("Document chunks table created successfully")
        except Exception as e:
            logger.error(f"Error creating chunks table: {e}")
            await db.rollback()
    
    def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for a list of texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            List of embedding vectors
        """
        if not self.embedding_model:
            logger.warning("Embedding model not available, returning random embeddings")
            # Return random embeddings for testing
            return [np.random.randn(self.embedding_dimension).tolist() for _ in texts]
        
        try:
            embeddings = self.embedding_model.encode(texts)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error creating embeddings: {e}")
            return [np.zeros(self.embedding_dimension).tolist() for _ in texts]
    
    async def store_document_chunks(
        self,
        db: AsyncSession,
        document_id: str,
        chunks: List[Dict[str, Any]]
    ) -> int:
        """
        Store document chunks with embeddings.
        
        Args:
            db: Database session
            document_id: Document UUID
            chunks: List of chunk dictionaries
            
        Returns:
            Number of chunks stored
        """
        if not chunks:
            return 0
        
        # Extract texts for embedding
        texts = [chunk.get('content', '') for chunk in chunks]
        
        # Create embeddings
        embeddings = self.create_embeddings(texts)
        
        # Prepare insert data
        insert_sql = """
        INSERT INTO document_chunks (
            document_id, content, embedding, page_number, section_type,
            section_title, chunk_index, chunk_size, entities
        ) VALUES (
            :document_id, :content, :embedding, :page_number, :section_type,
            :section_title, :chunk_index, :chunk_size, :entities
        )
        """
        
        stored_count = 0
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            try:
                metadata = chunk.get('metadata', {})
                
                # Prepare parameters
                params = {
                    'document_id': document_id,
                    'content': chunk.get('content', ''),
                    'embedding': embedding,
                    'page_number': metadata.get('page'),
                    'section_type': metadata.get('section_type'),
                    'section_title': metadata.get('section_title'),
                    'chunk_index': i,
                    'chunk_size': len(chunk.get('content', '')),
                    'entities': chunk.get('entities', [])
                }
                
                await db.execute(text(insert_sql), params)
                stored_count += 1
                
            except Exception as e:
                logger.error(f"Error storing chunk {i}: {e}")
        
        await db.commit()
        logger.info(f"Stored {stored_count}/{len(chunks)} chunks for document {document_id}")
        
        return stored_count
    
    async def semantic_search(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 10,
        document_ids: Optional[List[str]] = None,
        section_types: Optional[List[str]] = None,
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search on document chunks.
        
        Args:
            db: Database session
            query: Search query
            limit: Maximum results
            document_ids: Filter by document IDs
            section_types: Filter by section types
            threshold: Similarity threshold (0-1)
            
        Returns:
            List of matching chunks with scores
        """
        # Create query embedding
        query_embedding = self.create_embeddings([query])[0]
        
        # Build search query
        search_sql = """
        SELECT
            id,
            document_id,
            content,
            page_number,
            section_type,
            section_title,
            entities,
            1 - (embedding <=> :query_embedding::vector) as similarity
        FROM document_chunks
        WHERE 1=1
        """
        
        params = {'query_embedding': query_embedding}
        
        # Add filters
        if document_ids:
            search_sql += " AND document_id = ANY(:document_ids)"
            params['document_ids'] = document_ids
        
        if section_types:
            search_sql += " AND section_type = ANY(:section_types)"
            params['section_types'] = section_types
        
        # Add similarity threshold
        search_sql += f" AND 1 - (embedding <=> :query_embedding::vector) > {threshold}"
        
        # Order and limit
        search_sql += f"""
        ORDER BY embedding <=> :query_embedding::vector
        LIMIT {limit}
        """
        
        try:
            result = await db.execute(text(search_sql), params)
            rows = result.fetchall()
            
            # Convert to dictionaries
            results = []
            for row in rows:
                results.append({
                    'id': str(row.id),
                    'document_id': str(row.document_id),
                    'content': row.content,
                    'page_number': row.page_number,
                    'section_type': row.section_type,
                    'section_title': row.section_title,
                    'entities': row.entities,
                    'similarity': float(row.similarity)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    async def hybrid_search(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 10,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining semantic and keyword search.
        
        Args:
            db: Database session
            query: Search query
            limit: Maximum results
            semantic_weight: Weight for semantic similarity
            keyword_weight: Weight for keyword match
            document_ids: Filter by document IDs
            
        Returns:
            List of matching chunks with combined scores
        """
        # Create query embedding
        query_embedding = self.create_embeddings([query])[0]
        
        # Build hybrid search query
        hybrid_sql = """
        WITH semantic_scores AS (
            SELECT
                id,
                1 - (embedding <=> :query_embedding::vector) as semantic_score
            FROM document_chunks
            WHERE embedding IS NOT NULL
        ),
        keyword_scores AS (
            SELECT
                id,
                ts_rank_cd(tsv, plainto_tsquery('french', :query)) as keyword_score
            FROM document_chunks
            WHERE tsv @@ plainto_tsquery('french', :query)
        ),
        combined_scores AS (
            SELECT
                c.id,
                c.document_id,
                c.content,
                c.page_number,
                c.section_type,
                c.section_title,
                c.entities,
                COALESCE(s.semantic_score * :semantic_weight, 0) +
                COALESCE(k.keyword_score * :keyword_weight, 0) as combined_score,
                s.semantic_score,
                k.keyword_score
            FROM document_chunks c
            LEFT JOIN semantic_scores s ON c.id = s.id
            LEFT JOIN keyword_scores k ON c.id = k.id
            WHERE (s.semantic_score IS NOT NULL OR k.keyword_score IS NOT NULL)
        )
        SELECT *
        FROM combined_scores
        WHERE combined_score > 0
        """
        
        params = {
            'query_embedding': query_embedding,
            'query': query,
            'semantic_weight': semantic_weight,
            'keyword_weight': keyword_weight
        }
        
        # Add document filter if provided
        if document_ids:
            hybrid_sql += " AND document_id = ANY(:document_ids)"
            params['document_ids'] = document_ids
        
        # Order and limit
        hybrid_sql += f"""
        ORDER BY combined_score DESC
        LIMIT {limit}
        """
        
        try:
            result = await db.execute(text(hybrid_sql), params)
            rows = result.fetchall()
            
            # Convert to dictionaries
            results = []
            for row in rows:
                results.append({
                    'id': str(row.id),
                    'document_id': str(row.document_id),
                    'content': row.content,
                    'page_number': row.page_number,
                    'section_type': row.section_type,
                    'section_title': row.section_title,
                    'entities': row.entities,
                    'combined_score': float(row.combined_score),
                    'semantic_score': float(row.semantic_score) if row.semantic_score else 0,
                    'keyword_score': float(row.keyword_score) if row.keyword_score else 0
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []
    
    async def find_similar_documents(
        self,
        db: AsyncSession,
        document_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find similar documents based on embeddings.
        
        Args:
            db: Database session
            document_id: Reference document ID
            limit: Maximum results
            
        Returns:
            List of similar documents with scores
        """
        # Get average embedding of the document
        avg_embedding_sql = """
        SELECT AVG(embedding)::vector as avg_embedding
        FROM document_chunks
        WHERE document_id = :document_id
        AND embedding IS NOT NULL
        """
        
        try:
            result = await db.execute(
                text(avg_embedding_sql),
                {'document_id': document_id}
            )
            row = result.fetchone()
            
            if not row or not row.avg_embedding:
                return []
            
            avg_embedding = row.avg_embedding
            
            # Find similar documents
            similar_sql = """
            WITH doc_embeddings AS (
                SELECT
                    document_id,
                    AVG(embedding)::vector as doc_embedding
                FROM document_chunks
                WHERE document_id != :document_id
                AND embedding IS NOT NULL
                GROUP BY document_id
            )
            SELECT
                de.document_id,
                pd.filename,
                pd.mime_type,
                pd.created_at,
                1 - (de.doc_embedding <=> :avg_embedding::vector) as similarity
            FROM doc_embeddings de
            JOIN procurement_documents pd ON de.document_id = pd.id
            ORDER BY de.doc_embedding <=> :avg_embedding::vector
            LIMIT :limit
            """
            
            result = await db.execute(
                text(similar_sql),
                {
                    'document_id': document_id,
                    'avg_embedding': avg_embedding,
                    'limit': limit
                }
            )
            
            rows = result.fetchall()
            
            # Convert to dictionaries
            results = []
            for row in rows:
                results.append({
                    'document_id': str(row.document_id),
                    'filename': row.filename,
                    'mime_type': row.mime_type,
                    'created_at': row.created_at.isoformat(),
                    'similarity': float(row.similarity)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error finding similar documents: {e}")
            return []
