#!/usr/bin/env python3
"""
Tests for NLP Pipeline and Document Processing.
"""

import pytest
import logging
from unittest.mock import Mock, patch, MagicMock

from src.processors.document_chunker import (
    SmartChunker,
    DocumentChunk,
    ChunkingStrategy,
    FixedSizeChunker,
    SemanticChunker,
    StructuralChunker
)

logger = logging.getLogger(__name__)


class TestDocumentChunking:
    """Test document chunking functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.chunker = SmartChunker()
        
        # Sample French procurement text
        self.sample_text = """
        CAHIER DES CHARGES
        
        Article 1: Objet du marché
        Le présent marché a pour objet la fourniture et l'installation d'un système
        informatique complet pour la gestion documentaire de la collectivité.
        
        Article 2: Spécifications techniques
        Le système devra comprendre les éléments suivants:
        - Serveur de base de données PostgreSQL
        - Application web développée en Python/FastAPI
        - Interface utilisateur moderne et responsive
        - Système de sauvegarde automatisée
        
        Le prestataire devra garantir une disponibilité de 99.9% du service.
        
        Article 3: Budget et financement
        Le montant maximum du marché est fixé à 150 000 € HT.
        Les paiements seront effectués selon l'échéancier suivant:
        - 30% à la commande
        - 50% à la livraison
        - 20% après réception définitive
        
        Article 4: Délais d'exécution
        La livraison complète devra être effectuée avant le 31 décembre 2025.
        Des pénalités de retard de 500 € par jour seront appliquées.
        """
    
    def test_smart_chunker_initialization(self):
        """Test SmartChunker initialization."""
        assert self.chunker is not None
        assert ChunkingStrategy.FIXED_SIZE in self.chunker.chunkers
        assert ChunkingStrategy.SEMANTIC in self.chunker.chunkers
        assert ChunkingStrategy.STRUCTURAL in self.chunker.chunkers
    
    def test_document_analysis(self):
        """Test document characteristic analysis."""
        analysis = self.chunker.analyze_document(self.sample_text)
        
        assert 'total_chars' in analysis
        assert 'total_words' in analysis
        assert 'estimated_pages' in analysis
        assert 'has_sections' in analysis
        assert 'paragraph_count' in analysis
        
        # Check values
        assert analysis['total_chars'] > 0
        assert analysis['total_words'] > 100
        assert analysis['has_sections'] == True  # Has "Article" headers
    
    def test_strategy_selection(self):
        """Test automatic strategy selection."""
        # Small document - should use FIXED_SIZE
        small_text = "Ceci est un court document de test."
        strategy = self.chunker.select_strategy(small_text)
        assert strategy == ChunkingStrategy.FIXED_SIZE
        
        # Structured document - should use STRUCTURAL
        strategy = self.chunker.select_strategy(self.sample_text)
        assert strategy == ChunkingStrategy.STRUCTURAL
    
    def test_fixed_size_chunking(self):
        """Test fixed-size chunking."""
        chunker = FixedSizeChunker(chunk_size=500, overlap=50)
        chunks = chunker.chunk(self.sample_text)
        
        assert len(chunks) > 0
        assert all(isinstance(c, DocumentChunk) for c in chunks)
        
        # Check chunk properties
        for chunk in chunks:
            assert chunk.char_count <= 600  # Allow some flexibility for sentence boundaries
            assert chunk.content.strip() != ""
            assert chunk.metadata['strategy'] == 'fixed_size'
    
    def test_semantic_chunking(self):
        """Test semantic chunking."""
        chunker = SemanticChunker(max_chunk_size=1000, min_chunk_size=200)
        chunks = chunker.chunk(self.sample_text)
        
        assert len(chunks) > 0
        
        for chunk in chunks:
            assert chunk.char_count >= 200 or chunk == chunks[-1]  # Last chunk can be smaller
            assert chunk.char_count <= 1500  # Some flexibility for paragraph boundaries
            assert chunk.metadata['strategy'] == 'semantic'
    
    def test_structural_chunking(self):
        """Test structural chunking."""
        chunker = StructuralChunker(max_chunk_size=2000)
        chunks = chunker.chunk(self.sample_text)
        
        assert len(chunks) > 0
        
        # Should detect Article sections
        sections_found = any(
            'Article' in chunk.section_title 
            for chunk in chunks 
            if chunk.section_title
        )
        assert sections_found
        
        for chunk in chunks:
            assert chunk.metadata['strategy'] == 'structural'
            if chunk.section_title:
                assert 'Article' in chunk.section_title or 'CAHIER' in chunk.section_title
    
    def test_chunk_metadata(self):
        """Test chunk metadata generation."""
        chunks = self.chunker.chunk(self.sample_text)
        
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_id == i
            assert chunk.start_char >= 0
            assert chunk.end_char > chunk.start_char
            assert 'strategy' in chunk.metadata
            assert 'total_chunks' in chunk.metadata
            assert chunk.metadata['total_chunks'] == len(chunks)
    
    def test_empty_document(self):
        """Test handling of empty document."""
        chunks = self.chunker.chunk("")
        assert len(chunks) == 0
    
    def test_very_large_document(self):
        """Test handling of very large document."""
        # Create a large document
        large_text = self.sample_text * 50  # Repeat to make it large
        
        chunks = self.chunker.chunk(large_text)
        assert len(chunks) > 1
        
        # Should use appropriate strategy for large docs
        strategy = self.chunker.select_strategy(large_text)
        assert strategy in [ChunkingStrategy.STRUCTURAL, ChunkingStrategy.SEMANTIC]


class TestNLPExtractors:
    """Test NLP extractors functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        from src.nlp.extractors import (
            RequirementExtractor,
            BudgetExtractor,
            DeadlineExtractor,
            ComprehensiveExtractor
        )
        
        self.req_extractor = RequirementExtractor()
        self.budget_extractor = BudgetExtractor()
        self.deadline_extractor = DeadlineExtractor()
        self.comprehensive = ComprehensiveExtractor()
        
        self.sample_requirement = """
        Le système doit permettre la gestion complète des documents.
        Il devra obligatoirement inclure une fonction de recherche avancée.
        La sauvegarde automatique est optionnelle mais souhaitée.
        """
        
        self.sample_budget = """
        Le budget maximum alloué est de 250 000 euros HT.
        Un acompte de 30% sera versé à la commande.
        """
        
        self.sample_deadline = """
        La date limite de dépôt des offres est fixée au 15 mars 2025.
        La livraison devra être effectuée avant le 31/12/2025.
        Un délai de 30 jours est accordé pour la phase de test.
        """
    
    def test_requirement_extraction(self):
        """Test requirement extraction."""
        requirements = self.req_extractor.extract(self.sample_requirement)
        
        assert len(requirements) > 0
        
        # Check for mandatory requirements
        mandatory = [r for r in requirements if r.priority == 'mandatory']
        assert len(mandatory) >= 1
        
        # Check requirement properties
        for req in requirements:
            assert req.id is not None
            assert req.category in ['technical', 'functional', 'administrative']
            assert req.priority in ['mandatory', 'optional', 'nice-to-have']
            assert req.text != ""
    
    def test_budget_extraction(self):
        """Test budget extraction."""
        budget = self.budget_extractor.extract(self.sample_budget)
        
        assert budget is not None
        assert budget.max_amount == 250000.0
        assert budget.currency == 'EUR'
        assert budget.vat_included == False  # HT mentioned
        assert '30%' in budget.payment_terms or 'acompte' in budget.payment_terms
    
    def test_deadline_extraction(self):
        """Test deadline extraction."""
        deadlines = self.deadline_extractor.extract(self.sample_deadline)
        
        assert len(deadlines) >= 2
        
        # Check for submission deadline
        submission_deadlines = [d for d in deadlines if d.type == 'submission']
        assert len(submission_deadlines) >= 1
        
        # Check date parsing
        for deadline in deadlines:
            if '31/12/2025' in deadline.description:
                assert deadline.date.year == 2025
                assert deadline.date.month == 12
                assert deadline.date.day == 31
    
    def test_comprehensive_extraction(self):
        """Test comprehensive extraction."""
        full_text = self.sample_requirement + self.sample_budget + self.sample_deadline
        
        results = self.comprehensive.extract_all(full_text)
        
        assert 'requirements' in results
        assert 'budget' in results
        assert 'deadlines' in results
        assert 'entities' in results
        
        assert len(results['requirements']) > 0
        assert results['budget'] is not None
        assert len(results['deadlines']) > 0


@pytest.mark.skip(reason="Requires ML dependencies")
class TestNLPPipeline:
    """Test NLP pipeline integration (requires ML dependencies)."""
    
    def setup_method(self):
        """Setup test fixtures."""
        try:
            from src.nlp.pipeline import NLPPipeline
            self.pipeline = NLPPipeline({
                'use_cache': False,
                'enable_cross_chunk_analysis': False
            })
            self.skip_tests = False
        except ImportError:
            self.pipeline = None
            self.skip_tests = True
    
    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        if self.skip_tests:
            pytest.skip("NLP dependencies not installed")
        
        assert self.pipeline is not None
        assert self.pipeline.chunker is not None
    
    def test_document_processing(self):
        """Test full document processing."""
        if self.skip_tests:
            pytest.skip("NLP dependencies not installed")
        
        sample_doc = """
        Marché public de fourniture de matériel informatique.
        
        Le présent marché concerne l'acquisition de 50 ordinateurs portables
        pour les services administratifs de la collectivité.
        
        Budget estimé: 75 000 euros HT.
        Date limite de livraison: 30 juin 2025.
        """
        
        chunks = self.pipeline.process_document(
            text=sample_doc,
            document_id="test-doc-001"
        )
        
        assert len(chunks) > 0
        
        for chunk in chunks:
            assert chunk.chunk_id is not None
            assert chunk.content != ""
            # Check if NLP features were applied
            if self.pipeline.models.get('embeddings'):
                assert chunk.embeddings is not None
            if self.pipeline.models.get('spacy'):
                assert chunk.keywords is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])