"""
Processeur PDF avec pipeline NLP complet utilisant Docling.
Combine l'extraction Docling avec l'analyse NLP avancée.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import time

from src.processors.base import ProcessingResult
from src.processors.pdf_processor_docling import PDFProcessorDocling, DoclingExtractionResult
from src.nlp.pipeline import NLPPipeline
from src.processors.document_chunker import SmartChunker

logger = logging.getLogger(__name__)


class PDFProcessorNLPDocling(PDFProcessorDocling):
    """
    Processeur PDF combinant Docling et le pipeline NLP complet.

    Cette classe:
    1. Utilise Docling pour l'extraction de texte de haute qualité
    2. Applique le pipeline NLP complet sur le texte extrait
    3. Génère des embeddings et extrait des requirements structurés
    4. Utilise la structure du document pour un chunking intelligent
    """

    def __init__(self):
        """Initialise le processeur avec Docling et NLP."""
        super().__init__()
        self.nlp_pipeline = None
        self.chunker = SmartChunker()
        self._initialize_nlp()

    def _initialize_nlp(self):
        """Initialise le pipeline NLP."""
        try:
            self.nlp_pipeline = NLPPipeline()
            logger.info("✅ Pipeline NLP initialisé")
        except Exception as e:
            logger.warning(f"⚠️ Erreur initialisation NLP: {e}")
            self.nlp_pipeline = None

    def process_document(self, file_path: Path) -> ProcessingResult:
        """
        Traite un document avec Docling puis applique le pipeline NLP.

        Args:
            file_path: Chemin vers le fichier

        Returns:
            Résultat du traitement complet
        """
        start_time = time.time()

        # Étape 1: Extraction avec Docling
        if not self.can_process(file_path):
            logger.warning("Docling non disponible, fallback vers PDFProcessorNLP standard")
            from src.processors.pdf_processor_nlp import PDFProcessorNLP
            fallback = PDFProcessorNLP()
            return fallback.process_document(file_path)

        try:
            # Extraction Docling
            logger.info(f"📄 Traitement Docling+NLP: {file_path.name}")
            extraction = self.extract_with_docling(file_path)

            # Si pas de pipeline NLP, retourner juste l'extraction Docling
            if not self.nlp_pipeline:
                return super().process_document(file_path)

            # Étape 2: Chunking intelligent basé sur la structure
            chunks = self._smart_chunking(extraction)
            logger.info(f"📊 Chunking: {len(chunks)} chunks créés")

            # Étape 3: Analyse NLP complète
            nlp_results = self.nlp_pipeline.process_document(
                text=extraction.text,
                file_path=str(file_path),
                metadata={
                    'extraction_method': 'Docling',
                    'has_structure': len(extraction.sections) > 0,
                    'has_tables': len(extraction.tables) > 0
                }
            )

            # Étape 4: Extraction structurée des requirements
            requirements = self._extract_structured_requirements(
                extraction=extraction,
                nlp_results=nlp_results,
                chunks=chunks
            )

            # Étape 5: Construire le résultat complet
            processing_time = time.time() - start_time

            structured_content = {
                # Métadonnées du document
                "summary": {
                    "page_count": extraction.page_count,
                    "extraction_method": "Docling+NLP",
                    "processing_time": processing_time,
                    "chunk_count": len(chunks),
                    "requirement_count": len(requirements),
                    "has_tables": len(extraction.tables) > 0,
                    "has_sections": len(extraction.sections) > 0,
                    "confidence": extraction.confidence
                },

                # Structure du document (de Docling)
                "document_structure": {
                    "sections": extraction.sections,
                    "tables": extraction.tables,
                    "markdown": extraction.markdown
                },

                # Analyse NLP
                "nlp_analysis": {
                    "embeddings": nlp_results.embeddings if nlp_results else [],
                    "entities": nlp_results.entities if nlp_results else [],
                    "classification": nlp_results.classification if nlp_results else {},
                    "summary": nlp_results.summary if nlp_results else "",
                    "key_phrases": nlp_results.key_phrases if nlp_results else []
                },

                # Requirements extraits
                "requirements": requirements,

                # Chunks pour recherche
                "chunks": [
                    {
                        "id": i,
                        "text": chunk["text"],
                        "metadata": chunk.get("metadata", {}),
                        "embedding": nlp_results.embeddings[i] if nlp_results and i < len(nlp_results.embeddings) else None
                    }
                    for i, chunk in enumerate(chunks)
                ],

                # Texte complet
                "full_text": extraction.text
            }

            # Métadonnées complètes
            metadata = {
                "processor": "PDFProcessorNLPDocling",
                "docling_version": self._get_docling_version(),
                "extraction_time": extraction.extraction_time,
                "nlp_processing_time": nlp_results.processing_time if nlp_results else 0,
                "total_processing_time": processing_time,
                "confidence": extraction.confidence,
                **extraction.metadata
            }

            # Validation
            validation_errors = []
            if not extraction.text:
                validation_errors.append("Aucun texte extrait")
            if len(requirements) == 0:
                validation_errors.append("Aucune exigence détectée")
            if extraction.confidence < 0.5:
                validation_errors.append(f"Confiance faible: {extraction.confidence:.2%}")

            # Log des résultats
            logger.info(f"✅ Traitement Docling+NLP terminé en {processing_time:.2f}s:")
            logger.info(f"   • Texte: {len(extraction.text)} caractères")
            logger.info(f"   • Chunks: {len(chunks)}")
            logger.info(f"   • Requirements: {len(requirements)}")
            logger.info(f"   • Entities: {len(nlp_results.entities) if nlp_results else 0}")
            logger.info(f"   • Tables: {len(extraction.tables)}")
            logger.info(f"   • Confiance: {extraction.confidence:.2%}")

            return ProcessingResult(
                success=len(validation_errors) == 0,
                extracted_text=extraction.text,
                structured_content=structured_content,
                metadata=metadata,
                validation_errors=validation_errors
            )

        except Exception as e:
            logger.error(f"❌ Erreur traitement Docling+NLP: {e}")
            import traceback
            traceback.print_exc()

            # Fallback vers processeur standard
            try:
                from src.processors.pdf_processor_nlp import PDFProcessorNLP
                fallback = PDFProcessorNLP()
                return fallback.process_document(file_path)
            except Exception as fallback_error:
                logger.error(f"Échec du fallback: {fallback_error}")
                return ProcessingResult(
                    success=False,
                    extracted_text="",
                    structured_content={},
                    metadata={"error": str(e)},
                    validation_errors=[f"Erreur traitement: {str(e)}"]
                )

    def _smart_chunking(self, extraction: DoclingExtractionResult) -> List[Dict[str, Any]]:
        """
        Chunking intelligent basé sur la structure Docling.

        Args:
            extraction: Résultat de l'extraction Docling

        Returns:
            Liste de chunks avec métadonnées
        """
        chunks = []

        # Si on a une structure de sections, l'utiliser
        if extraction.sections and extraction.markdown:
            logger.info("📝 Chunking basé sur la structure du document")
            chunks = self._chunk_by_sections(extraction.markdown, extraction.sections)

        # Si on a des tables, les ajouter comme chunks séparés
        if extraction.tables:
            logger.info(f"📊 Ajout de {len(extraction.tables)} tables comme chunks")
            for i, table in enumerate(extraction.tables):
                chunks.append({
                    "text": table.get('content', ''),
                    "metadata": {
                        "type": "table",
                        "table_index": i,
                        "rows": table.get('rows', 0),
                        "cols": table.get('cols', 0)
                    }
                })

        # Fallback: chunking standard si pas de structure
        if not chunks:
            logger.info("📄 Chunking standard (pas de structure détectée)")
            text_chunks = self.chunker.chunk(extraction.text)
            chunks = [{"text": chunk, "metadata": {"type": "text"}} for chunk in text_chunks]

        return chunks

    def _chunk_by_sections(self, markdown: str, sections: List[Dict]) -> List[Dict[str, Any]]:
        """
        Découpe le document en chunks basés sur les sections.

        Args:
            markdown: Texte markdown du document
            sections: Liste des sections détectées

        Returns:
            Liste de chunks
        """
        chunks = []

        # Trier les sections par position
        sorted_sections = sorted(sections, key=lambda x: x.get('position', 0))

        for i, section in enumerate(sorted_sections):
            # Déterminer le début et la fin de la section
            start_pos = section.get('position', 0)
            end_pos = sorted_sections[i + 1].get('position', len(markdown)) if i + 1 < len(sorted_sections) else len(markdown)

            # Extraire le texte de la section
            section_text = markdown[start_pos:end_pos].strip()

            if section_text and len(section_text) > 50:  # Ignorer les sections trop courtes
                chunks.append({
                    "text": section_text,
                    "metadata": {
                        "type": "section",
                        "section_title": section.get('title', ''),
                        "section_level": section.get('level', 0),
                        "section_index": i
                    }
                })

        return chunks

    def _extract_structured_requirements(
        self,
        extraction: DoclingExtractionResult,
        nlp_results: Any,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extrait les requirements en utilisant la structure du document.

        Args:
            extraction: Résultat Docling
            nlp_results: Résultats de l'analyse NLP
            chunks: Chunks du document

        Returns:
            Liste des requirements structurés
        """
        requirements = []

        # Utiliser les extracteurs NLP si disponibles
        if nlp_results and hasattr(nlp_results, 'requirements'):
            requirements.extend(nlp_results.requirements)

        # Extraction supplémentaire basée sur la structure
        if extraction.sections:
            # Rechercher les sections "Exigences", "Requirements", etc.
            for section in extraction.sections:
                title_lower = section.get('title', '').lower()
                if any(keyword in title_lower for keyword in ['exigence', 'requirement', 'obligation', 'contrainte']):
                    # Cette section contient probablement des requirements
                    section_reqs = self._extract_requirements_from_section(extraction.text, section)
                    requirements.extend(section_reqs)

        # Extraction depuis les tables
        if extraction.tables:
            for table in extraction.tables:
                table_reqs = self._extract_requirements_from_table(table)
                requirements.extend(table_reqs)

        # Dédupliquer et scorer
        unique_requirements = self._deduplicate_requirements(requirements)

        return unique_requirements

    def _extract_requirements_from_section(self, text: str, section: Dict) -> List[Dict[str, Any]]:
        """Extrait les requirements d'une section spécifique."""
        requirements = []

        # Patterns spécifiques pour les requirements
        import re
        patterns = [
            r'(?:^|\n)\s*[-•]\s*(.+?)(?:\n|$)',  # Listes à puces
            r'(?:^|\n)\s*\d+[.)]\s*(.+?)(?:\n|$)',  # Listes numérotées
            r'(?i)(?:doit|devra|devront)\s+(.+?)(?:\.|;|\n|$)',  # Obligations
        ]

        section_title = section.get('title', '')

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                req_text = match.group(1).strip()
                if len(req_text) > 20:  # Filtre les textes trop courts
                    requirements.append({
                        'text': req_text,
                        'type': self._classify_requirement(req_text),
                        'source': 'section',
                        'section': section_title,
                        'confidence': 0.85
                    })

        return requirements

    def _extract_requirements_from_table(self, table: Dict) -> List[Dict[str, Any]]:
        """Extrait les requirements d'une table."""
        requirements = []

        # Analyser le contenu de la table
        content = table.get('content', '')
        if 'exigence' in content.lower() or 'requirement' in content.lower():
            # Cette table contient probablement des requirements
            lines = content.split('\n')
            for line in lines:
                if len(line) > 30 and not line.startswith('|---'):  # Ignorer les séparateurs
                    requirements.append({
                        'text': line.strip(),
                        'type': 'technical',  # Par défaut
                        'source': 'table',
                        'confidence': 0.75
                    })

        return requirements

    def _classify_requirement(self, text: str) -> str:
        """Classifie le type d'une exigence."""
        text_lower = text.lower()

        if any(word in text_lower for word in ['technique', 'compatible', 'format', 'protocole']):
            return 'technical'
        elif any(word in text_lower for word in ['fonction', 'permet', 'assure', 'gestion']):
            return 'functional'
        elif any(word in text_lower for word in ['délai', 'livraison', 'garantie', 'document']):
            return 'administrative'
        else:
            return 'general'

    def _deduplicate_requirements(self, requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Déduplique et consolide les requirements."""
        seen = set()
        unique = []

        for req in requirements:
            # Créer une clé unique basée sur le texte normalisé
            key = req['text'].lower().strip()[:100]  # Premiers 100 caractères

            if key not in seen:
                seen.add(key)
                unique.append(req)

        # Trier par confiance décroissante
        unique.sort(key=lambda x: x.get('confidence', 0), reverse=True)

        return unique

    @property
    def name(self) -> str:
        """Nom du processeur."""
        return "PDFProcessorNLPDocling"

    @property
    def version(self) -> str:
        """Version du processeur."""
        return "1.0.0"