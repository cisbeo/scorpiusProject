#!/usr/bin/env python3
"""
Core NLP Pipeline for document processing.
Integrates chunking, embedding generation, and analysis.
"""

import hashlib
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np

try:
    from transformers import (
        AutoTokenizer,
        AutoModel,
        AutoModelForSequenceClassification,
        pipeline
    )
    from sentence_transformers import SentenceTransformer
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logging.warning("Transformers not available. Install with: pip install -r requirements-ml.txt")

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logging.warning("spaCy not available. Install with: pip install -r requirements-ml.txt")

from src.processors.document_chunker import SmartChunker, DocumentChunk, ChunkingStrategy

# Optional cache support
try:
    from src.core.cache import cache_manager
except ImportError:
    cache_manager = None
    logging.warning("Cache manager not available. Caching disabled.")

logger = logging.getLogger(__name__)


@dataclass
class ProcessedChunk:
    """Represents a processed chunk with NLP analysis."""
    chunk_id: int
    content: str
    embeddings: Optional[List[float]] = None
    entities: List[Dict[str, Any]] = None
    keywords: List[str] = None
    classification: Dict[str, float] = None
    sentiment: Optional[float] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert numpy arrays to lists if present
        if self.embeddings is not None and hasattr(self.embeddings, 'tolist'):
            data['embeddings'] = self.embeddings.tolist()
        return data


class NLPPipeline:
    """
    Main NLP processing pipeline for French procurement documents.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize NLP pipeline with models.
        
        Args:
            config: Configuration dictionary with model preferences
        """
        self.config = config or {}
        self.chunker = SmartChunker()
        
        # Initialize models
        self._init_models()
        
        # Cache configuration
        self.cache_ttl = self.config.get('cache_ttl', 3600)  # 1 hour default
        
        logger.info("NLP Pipeline initialized")

    def _init_models(self):
        """Initialize NLP models based on availability."""
        self.models = {}
        
        if TRANSFORMERS_AVAILABLE:
            try:
                # CamemBERT for French text understanding
                model_name = self.config.get('base_model', 'camembert-base')
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.base_model = AutoModel.from_pretrained(model_name)
                self.models['base'] = True
                logger.info(f"Loaded base model: {model_name}")
                
                # Sentence embeddings for semantic search
                embedding_model = self.config.get(
                    'embedding_model',
                    'dangvantuan/sentence-camembert-base'
                )
                self.sentence_model = SentenceTransformer(embedding_model)
                self.models['embeddings'] = True
                logger.info(f"Loaded embedding model: {embedding_model}")
                
                # Zero-shot classification for document categorization
                self.classifier = pipeline(
                    "zero-shot-classification",
                    model="BaptisteDoyen/camembert-base-xnli"
                )
                self.models['classifier'] = True
                logger.info("Loaded zero-shot classifier")
                
            except Exception as e:
                logger.error(f"Error loading transformers models: {e}")
                self.models['base'] = False
                self.models['embeddings'] = False
                self.models['classifier'] = False
        
        if SPACY_AVAILABLE:
            try:
                # Load French spaCy model for NER and POS tagging
                model_name = self.config.get('spacy_model', 'fr_core_news_sm')
                self.nlp = spacy.load(model_name)
                self.models['spacy'] = True
                logger.info(f"Loaded spaCy model: {model_name}")
            except Exception as e:
                logger.warning(f"Could not load spaCy model: {e}")
                logger.info("Try: python -m spacy download fr_core_news_sm")
                self.models['spacy'] = False

    def process_document(
        self,
        text: str,
        document_id: str,
        chunking_strategy: Optional[ChunkingStrategy] = None,
        **kwargs
    ) -> List[ProcessedChunk]:
        """
        Process a full document through the NLP pipeline.
        
        Args:
            text: Document text
            document_id: Unique document identifier
            chunking_strategy: Optional specific chunking strategy
            **kwargs: Additional parameters
            
        Returns:
            List of processed chunks with NLP analysis
        """
        logger.info(f"Processing document {document_id}")
        
        # Step 1: Chunk the document
        chunks = self.chunker.chunk(text, strategy=chunking_strategy, **kwargs)
        logger.info(f"Document split into {len(chunks)} chunks")
        
        # Step 2: Process each chunk
        processed_chunks = []
        for chunk in chunks:
            processed = self.process_chunk(
                chunk=chunk,
                document_id=document_id,
                total_chunks=len(chunks)
            )
            processed_chunks.append(processed)
        
        # Step 3: Cross-chunk analysis (optional)
        if self.config.get('enable_cross_chunk_analysis', False):
            self._analyze_cross_chunk_relations(processed_chunks)
        
        logger.info(f"Completed processing {len(processed_chunks)} chunks")
        return processed_chunks

    def process_chunk(
        self,
        chunk: DocumentChunk,
        document_id: str,
        total_chunks: int = 1
    ) -> ProcessedChunk:
        """
        Process a single chunk with caching.
        
        Args:
            chunk: Document chunk to process
            document_id: Document identifier for cache key
            total_chunks: Total number of chunks in document
            
        Returns:
            Processed chunk with NLP analysis
        """
        # Generate cache key
        cache_key = self._generate_cache_key(document_id, chunk.chunk_id, chunk.content)
        
        # Check cache
        if cache_manager and self.config.get('use_cache', True):
            cached = cache_manager.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for chunk {chunk.chunk_id}")
                return ProcessedChunk(**json.loads(cached))
        
        # Process chunk
        processed = ProcessedChunk(
            chunk_id=chunk.chunk_id,
            content=chunk.content,
            metadata={
                **chunk.metadata,
                'document_id': document_id,
                'total_chunks': total_chunks,
                'char_count': chunk.char_count,
                'word_count': chunk.word_count,
                'token_estimate': chunk.token_estimate
            }
        )
        
        # Generate embeddings
        if self.models.get('embeddings'):
            processed.embeddings = self._generate_embeddings(chunk.content)
        
        # Extract entities
        if self.models.get('spacy'):
            processed.entities = self._extract_entities(chunk.content)
            processed.keywords = self._extract_keywords(chunk.content)
        
        # Classify chunk type
        if self.models.get('classifier'):
            processed.classification = self._classify_chunk(chunk.content)
        
        # Cache result
        if cache_manager and self.config.get('use_cache', True):
            cache_manager.set(
                cache_key,
                json.dumps(processed.to_dict()),
                ttl=self.cache_ttl
            )
        
        return processed

    def _generate_embeddings(self, text: str) -> List[float]:
        """
        Generate sentence embeddings for text.
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector (768 dimensions for CamemBERT)
        """
        try:
            embeddings = self.sentence_model.encode(text)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return None

    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract named entities from text.
        
        Args:
            text: Input text
            
        Returns:
            List of entities with type and text
        """
        try:
            doc = self.nlp(text)
            entities = []
            
            for ent in doc.ents:
                entities.append({
                    'text': ent.text,
                    'type': ent.label_,
                    'start': ent.start_char,
                    'end': ent.end_char
                })
            
            return entities
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []

    def _extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        """
        Extract keywords from text using TF-IDF approach.
        
        Args:
            text: Input text
            top_n: Number of keywords to extract
            
        Returns:
            List of keywords
        """
        try:
            doc = self.nlp(text)
            
            # Extract noun phrases and important words
            keywords = []
            
            # Get noun phrases
            for chunk in doc.noun_chunks:
                if len(chunk.text.split()) <= 3:  # Limit phrase length
                    keywords.append(chunk.text.lower())
            
            # Get important individual tokens
            for token in doc:
                if (
                    not token.is_stop and
                    not token.is_punct and
                    len(token.text) > 2 and
                    token.pos_ in ['NOUN', 'PROPN', 'ADJ']
                ):
                    keywords.append(token.lemma_.lower())
            
            # Remove duplicates and return top N
            seen = set()
            unique_keywords = []
            for kw in keywords:
                if kw not in seen:
                    seen.add(kw)
                    unique_keywords.append(kw)
            
            return unique_keywords[:top_n]
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []

    def _classify_chunk(self, text: str) -> Dict[str, float]:
        """
        Classify chunk into procurement categories.
        
        Args:
            text: Input text
            
        Returns:
            Classification scores for each category
        """
        try:
            # Define procurement-specific labels
            labels = [
                "exigences techniques",
                "exigences fonctionnelles",
                "exigences administratives",
                "budget et financement",
                "délais et planning",
                "critères de sélection",
                "modalités de réponse"
            ]
            
            result = self.classifier(
                text[:512],  # Limit text length for classifier
                candidate_labels=labels,
                multi_label=True
            )
            
            # Convert to dictionary
            classification = {}
            for label, score in zip(result['labels'], result['scores']):
                classification[label] = float(score)
            
            return classification
            
        except Exception as e:
            logger.error(f"Error classifying chunk: {e}")
            return {}

    def _generate_cache_key(self, document_id: str, chunk_id: int, content: str) -> str:
        """
        Generate cache key for chunk.
        
        Args:
            document_id: Document identifier
            chunk_id: Chunk identifier
            content: Chunk content
            
        Returns:
            Cache key string
        """
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"nlp:chunk:{document_id}:{chunk_id}:{content_hash}"

    def _analyze_cross_chunk_relations(self, chunks: List[ProcessedChunk]):
        """
        Analyze relationships between chunks (co-reference, topic flow, etc.).
        
        Args:
            chunks: List of processed chunks
        """
        # TODO: Implement cross-chunk analysis
        # - Co-reference resolution
        # - Topic modeling across chunks
        # - Dependency tracking
        pass

    def get_document_summary(self, processed_chunks: List[ProcessedChunk]) -> Dict[str, Any]:
        """
        Generate summary statistics for processed document.
        
        Args:
            processed_chunks: List of processed chunks
            
        Returns:
            Summary dictionary with statistics and insights
        """
        summary = {
            'total_chunks': len(processed_chunks),
            'total_entities': 0,
            'entity_types': {},
            'top_keywords': {},
            'dominant_categories': {},
            'has_embeddings': False
        }
        
        # Aggregate entities
        all_entities = []
        for chunk in processed_chunks:
            if chunk.entities:
                all_entities.extend(chunk.entities)
                
        summary['total_entities'] = len(all_entities)
        
        # Count entity types
        entity_type_counts = {}
        for ent in all_entities:
            ent_type = ent.get('type', 'UNKNOWN')
            entity_type_counts[ent_type] = entity_type_counts.get(ent_type, 0) + 1
        summary['entity_types'] = entity_type_counts
        
        # Aggregate keywords
        keyword_counts = {}
        for chunk in processed_chunks:
            if chunk.keywords:
                for kw in chunk.keywords:
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        
        # Get top keywords
        top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        summary['top_keywords'] = dict(top_keywords)
        
        # Aggregate classifications
        category_scores = {}
        for chunk in processed_chunks:
            if chunk.classification:
                for category, score in chunk.classification.items():
                    if category not in category_scores:
                        category_scores[category] = []
                    category_scores[category].append(score)
        
        # Calculate average scores
        for category, scores in category_scores.items():
            summary['dominant_categories'][category] = np.mean(scores)
        
        # Sort by score
        summary['dominant_categories'] = dict(
            sorted(summary['dominant_categories'].items(), key=lambda x: x[1], reverse=True)
        )
        
        # Check embeddings
        summary['has_embeddings'] = any(chunk.embeddings for chunk in processed_chunks)
        
        return summary