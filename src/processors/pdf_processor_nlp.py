#!/usr/bin/env python3
"""
Enhanced PDF processor with NLP integration.
Extends the base PDFProcessor with advanced NLP capabilities.
"""

import logging
from datetime import datetime
from typing import Any, Optional, Dict, List
import json

from src.processors.pdf_processor import PDFProcessor
from src.processors.base import ProcessingResult
from src.nlp.pipeline import NLPPipeline, ProcessedChunk
from src.nlp.extractors import ComprehensiveExtractor

logger = logging.getLogger(__name__)


class PDFProcessorNLP(PDFProcessor):
    """
    PDF processor with integrated NLP pipeline for advanced document analysis.
    
    This processor extends the base PDF processor with:
    - Smart document chunking
    - Named entity recognition
    - Requirement extraction
    - Budget and deadline detection
    - Semantic embeddings generation
    - Document classification
    """
    
    def __init__(self, nlp_config: Optional[Dict[str, Any]] = None):
        """
        Initialize enhanced PDF processor.
        
        Args:
            nlp_config: Configuration for NLP pipeline
        """
        super().__init__()
        self.name = "PDFProcessorNLP"
        self.version = "2.0.0"
        
        # Initialize NLP pipeline
        self.nlp_config = nlp_config or {
            'use_cache': True,
            'cache_ttl': 3600,
            'enable_cross_chunk_analysis': False,
            'base_model': 'camembert-base',
            'embedding_model': 'dangvantuan/sentence-camembert-base',
            'spacy_model': 'fr_core_news_sm'
        }
        
        try:
            self.nlp_pipeline = NLPPipeline(self.nlp_config)
            self.extractor = ComprehensiveExtractor()
            self.nlp_available = True
            logger.info("NLP pipeline initialized successfully")
        except Exception as e:
            logger.warning(f"NLP pipeline initialization failed: {e}")
            logger.warning("Falling back to basic PDF processing")
            self.nlp_pipeline = None
            self.extractor = None
            self.nlp_available = False
    
    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        processing_options: Optional[dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Process PDF document with NLP enhancement.
        
        Args:
            file_content: Binary content of the PDF
            filename: Original filename
            mime_type: MIME type
            processing_options: Processing configuration options
            
        Returns:
            ProcessingResult with enhanced NLP analysis
        """
        # First, perform base PDF processing
        result = await super().process_document(
            file_content, filename, mime_type, processing_options
        )
        
        # If base processing failed or NLP not available, return base result
        if not result.success or not self.nlp_available:
            return result
        
        # Enhance with NLP processing
        try:
            start_time = datetime.utcnow()
            
            # Process document through NLP pipeline
            document_id = processing_options.get('document_id', filename)
            processed_chunks = self.nlp_pipeline.process_document(
                text=result.raw_text,
                document_id=document_id
            )
            
            # Extract comprehensive information
            extraction_results = self.extractor.extract_from_chunks(processed_chunks)
            
            # Get document summary from NLP pipeline
            nlp_summary = self.nlp_pipeline.get_document_summary(processed_chunks)
            
            # Enhance structured content with NLP results
            result.structured_content['nlp_analysis'] = {
                'chunks_processed': len(processed_chunks),
                'extraction_results': self._serialize_extraction_results(extraction_results),
                'nlp_summary': nlp_summary,
                'embeddings_generated': nlp_summary.get('has_embeddings', False)
            }
            
            # Add extracted requirements to structured content
            if extraction_results['requirements']:
                result.structured_content['requirements'] = [
                    {
                        'id': req.id,
                        'category': req.category,
                        'text': req.text,
                        'priority': req.priority,
                        'metadata': req.metadata
                    }
                    for req in extraction_results['requirements']
                ]
            
            # Add budget information
            if extraction_results['budget']:
                budget = extraction_results['budget']
                result.structured_content['budget'] = {
                    'min_amount': budget.min_amount,
                    'max_amount': budget.max_amount,
                    'currency': budget.currency,
                    'vat_included': budget.vat_included,
                    'budget_type': budget.budget_type,
                    'payment_terms': budget.payment_terms
                }
            
            # Add deadlines
            if extraction_results['deadlines']:
                result.structured_content['deadlines'] = [
                    {
                        'date': deadline.date.isoformat() if deadline.date else None,
                        'description': deadline.description,
                        'type': deadline.type,
                        'is_strict': deadline.is_strict
                    }
                    for deadline in extraction_results['deadlines']
                ]
            
            # Add entities
            if extraction_results['entities']:
                result.structured_content['entities'] = [
                    {
                        'name': entity.name,
                        'type': entity.type,
                        'role': entity.role,
                        'metadata': entity.metadata
                    }
                    for entity in extraction_results['entities']
                ]
            
            # Store processed chunks for later use (e.g., vector search)
            result.structured_content['processed_chunks'] = self._serialize_chunks(processed_chunks)
            
            # Update metadata with NLP processing info
            nlp_processing_time = self.measure_processing_time(start_time)
            result.metadata['nlp_processing'] = {
                'enabled': True,
                'processing_time_ms': nlp_processing_time,
                'models_used': list(self.nlp_pipeline.models.keys()),
                'total_requirements': extraction_results['summary']['total_requirements'],
                'total_entities': extraction_results['summary']['total_entities'],
                'has_budget': extraction_results['summary']['has_budget'],
                'total_deadlines': extraction_results['summary']['total_deadlines']
            }
            
            # Update confidence score based on NLP analysis
            result.confidence_score = self._calculate_enhanced_confidence(
                result.confidence_score,
                extraction_results,
                nlp_summary
            )
            
            logger.info(f"NLP processing completed in {nlp_processing_time}ms")
            
        except Exception as e:
            logger.error(f"NLP enhancement failed: {e}")
            result.add_warning(f"NLP processing partially failed: {str(e)}")
            # Return result with base processing even if NLP fails
        
        return result
    
    def _serialize_extraction_results(self, extraction_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize extraction results for storage.
        
        Args:
            extraction_results: Raw extraction results
            
        Returns:
            Serialized results
        """
        return {
            'total_requirements': extraction_results['summary']['total_requirements'],
            'requirements_by_category': extraction_results['summary']['requirements_by_category'],
            'requirements_by_priority': extraction_results['summary']['requirements_by_priority'],
            'total_entities': extraction_results['summary']['total_entities'],
            'total_deadlines': extraction_results['summary']['total_deadlines'],
            'has_budget': extraction_results['summary']['has_budget']
        }
    
    def _serialize_chunks(self, chunks: List[ProcessedChunk]) -> List[Dict[str, Any]]:
        """
        Serialize processed chunks for storage.
        
        Args:
            chunks: List of processed chunks
            
        Returns:
            Serialized chunks (without embeddings for space)
        """
        serialized = []
        
        for chunk in chunks[:10]:  # Limit to first 10 chunks for space
            chunk_data = {
                'chunk_id': chunk.chunk_id,
                'content_preview': chunk.content[:200] if chunk.content else '',
                'entities_count': len(chunk.entities) if chunk.entities else 0,
                'keywords': chunk.keywords[:5] if chunk.keywords else [],
                'has_embeddings': chunk.embeddings is not None,
                'metadata': chunk.metadata
            }
            
            # Add top classification if available
            if chunk.classification:
                top_class = max(chunk.classification.items(), key=lambda x: x[1])
                chunk_data['primary_classification'] = {
                    'category': top_class[0],
                    'confidence': top_class[1]
                }
            
            serialized.append(chunk_data)
        
        return serialized
    
    def _calculate_enhanced_confidence(
        self,
        base_confidence: float,
        extraction_results: Dict[str, Any],
        nlp_summary: Dict[str, Any]
    ) -> float:
        """
        Calculate enhanced confidence score using NLP results.
        
        Args:
            base_confidence: Base confidence from PDF extraction
            extraction_results: Extraction results
            nlp_summary: NLP summary statistics
            
        Returns:
            Enhanced confidence score
        """
        confidence = base_confidence
        
        # Boost confidence if key information was extracted
        if extraction_results['summary']['total_requirements'] > 0:
            confidence += 0.1
        
        if extraction_results['summary']['has_budget']:
            confidence += 0.05
        
        if extraction_results['summary']['total_deadlines'] > 0:
            confidence += 0.05
        
        if extraction_results['summary']['total_entities'] > 0:
            confidence += 0.05
        
        # Boost if embeddings were successfully generated
        if nlp_summary.get('has_embeddings'):
            confidence += 0.05
        
        # Cap at 1.0
        return min(1.0, confidence)
    
    def get_processor_info(self) -> Dict[str, Any]:
        """
        Get processor information including NLP capabilities.
        
        Returns:
            Processor information dictionary
        """
        info = super().get_processor_info()
        
        info['nlp'] = {
            'available': self.nlp_available,
            'models': list(self.nlp_pipeline.models.keys()) if self.nlp_pipeline else [],
            'extractors': [
                'requirements',
                'budget',
                'deadlines',
                'entities'
            ],
            'features': [
                'chunking',
                'embeddings',
                'classification',
                'ner',
                'keyword_extraction'
            ]
        }
        
        return info