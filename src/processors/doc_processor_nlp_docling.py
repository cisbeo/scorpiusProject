"""
Processeur de documents avec pipeline NLP complet utilisant Docling - Version 2.
Combine l'extraction Docling avec l'analyse NLP avancée.
Compatible avec l'interface async.
Supporte PDF, DOCX, PPTX, XLSX, HTML et Markdown.
"""

import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
import time

from src.processors.base import ProcessingResult
from src.processors.doc_processor_docling import DocProcessorDocling, DoclingExtractionResult
from src.nlp.pipeline import NLPPipeline
from src.processors.document_chunker import SmartChunker

logger = logging.getLogger(__name__)


class DocProcessorNLPDocling(DocProcessorDocling):
    """
    Processeur de documents combinant Docling et le pipeline NLP complet.
    Version 2 - Compatible avec l'interface async.
    Supporte plusieurs formats: PDF, DOCX, PPTX, XLSX, HTML, Markdown.
    """

    def __init__(self):
        """Initialise le processeur avec Docling et NLP."""
        super().__init__()
        self.name = "DocProcessorNLPDocling"
        self.version = "2.0.0"
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

    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        processing_options: Optional[dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Traite un document avec Docling puis applique le pipeline NLP.

        Args:
            file_content: Contenu binaire du document
            filename: Nom du fichier
            mime_type: Type MIME
            processing_options: Options de traitement

        Returns:
            ProcessingResult avec extraction et analyse NLP
        """
        start_time = time.time()

        # Étape 1: Extraction avec Docling
        docling_result = await super().process_document(
            file_content,
            filename,
            mime_type,
            processing_options
        )

        # Si l'extraction Docling a échoué ou pas de NLP, retourner le résultat Docling
        if not docling_result.success or not self.nlp_pipeline:
            return docling_result

        # Exécuter l'analyse NLP dans un executor car elle n'est pas async
        nlp_result = await asyncio.get_event_loop().run_in_executor(
            None,
            self._process_nlp_sync,
            docling_result,
            filename
        )

        return nlp_result

    def _process_nlp_sync(
        self,
        docling_result: ProcessingResult,
        filename: str
    ) -> ProcessingResult:
        """
        Applique le pipeline NLP sur le résultat Docling.
        """
        start_time = time.time()

        try:
            # Récupérer les données de l'extraction Docling
            text = docling_result.raw_text
            structured_content = docling_result.structured_content

            # Étape 2: Chunking intelligent basé sur la structure
            chunks = self._smart_chunking(text, structured_content)
            logger.info(f"📊 Chunking: {len(chunks)} chunks créés")

            # Étape 3: Analyse NLP complète
            nlp_results = self.nlp_pipeline.process_document(
                text=text,
                file_path=filename,
                metadata={
                    'extraction_method': 'Docling',
                    'has_structure': len(structured_content.get('sections', [])) > 0,
                    'has_tables': len(structured_content.get('tables', [])) > 0
                }
            )

            # Étape 4: Extraction structurée des requirements
            requirements = self._extract_structured_requirements(
                text=text,
                structured_content=structured_content,
                nlp_results=nlp_results,
                chunks=chunks
            )

            # Étape 5: Construire le résultat enrichi
            processing_time = int((time.time() - start_time) * 1000)
            total_processing_time = docling_result.processing_time_ms + processing_time

            # Enrichir le contenu structuré avec l'analyse NLP
            enriched_content = {
                **structured_content,
                "nlp_analysis": {
                    "embeddings": nlp_results.embeddings if nlp_results else [],
                    "entities": nlp_results.entities if nlp_results else [],
                    "classification": nlp_results.classification if nlp_results else {},
                    "summary": nlp_results.summary if nlp_results else "",
                    "key_phrases": nlp_results.key_phrases if nlp_results else []
                },
                "requirements": requirements,
                "chunks": [
                    {
                        "id": i,
                        "text": chunk["text"],
                        "metadata": chunk.get("metadata", {}),
                        "embedding": nlp_results.embeddings[i] if nlp_results and i < len(nlp_results.embeddings) else None
                    }
                    for i, chunk in enumerate(chunks)
                ],
                "chunk_count": len(chunks),
                "requirement_count": len(requirements)
            }

            # Créer le résultat final
            result = ProcessingResult(
                raw_text=text,
                structured_content=enriched_content,
                success=True,
                processing_time_ms=total_processing_time,
                processor_name=self.name,
                processor_version=self.version,
                page_count=docling_result.page_count,
                word_count=docling_result.word_count,
                confidence_score=docling_result.confidence_score
            )

            # Ajouter des warnings si nécessaire
            if len(requirements) == 0:
                result.add_warning("Aucune exigence détectée")

            # Copier les erreurs et warnings de Docling
            if docling_result.errors:
                for error in docling_result.errors:
                    result.add_error(error)

            if docling_result.warnings:
                for warning in docling_result.warnings:
                    result.add_warning(warning)

            # Log des résultats
            logger.info(f"✅ Traitement Docling+NLP terminé en {total_processing_time}ms:")
            logger.info(f"   • Texte: {docling_result.word_count} mots")
            logger.info(f"   • Chunks: {len(chunks)}")
            logger.info(f"   • Requirements: {len(requirements)}")
            logger.info(f"   • Entities: {len(nlp_results.entities) if nlp_results else 0}")
            logger.info(f"   • Confiance: {docling_result.confidence_score:.2%}")

            return result

        except Exception as e:
            logger.error(f"❌ Erreur traitement NLP: {e}")
            # En cas d'erreur NLP, retourner le résultat Docling avec un warning
            docling_result.add_warning(f"Analyse NLP échouée: {str(e)}")
            return docling_result

    def _smart_chunking(
        self,
        text: str,
        structured_content: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Chunking intelligent basé sur la structure Docling.

        Args:
            text: Texte extrait
            structured_content: Contenu structuré de Docling

        Returns:
            Liste de chunks avec métadonnées
        """
        chunks = []

        # Si on a une structure de sections, l'utiliser
        sections = structured_content.get('sections', [])
        markdown = structured_content.get('markdown', '')

        if sections and markdown:
            logger.info("📝 Chunking basé sur la structure du document")
            chunks = self._chunk_by_sections(markdown, sections)

        # Si on a des tables, les ajouter comme chunks séparés
        tables = structured_content.get('tables', [])
        if tables:
            logger.info(f"📊 Ajout de {len(tables)} tables comme chunks")
            for i, table in enumerate(tables):
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
            text_chunks = self.chunker.chunk(text)
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
        text: str,
        structured_content: Dict[str, Any],
        nlp_results: Any,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extrait les requirements en utilisant la structure du document.

        Args:
            text: Texte extrait
            structured_content: Contenu structuré de Docling
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
        sections = structured_content.get('sections', [])
        if sections:
            # Rechercher les sections "Exigences", "Requirements", etc.
            for section in sections:
                title_lower = section.get('title', '').lower()
                if any(keyword in title_lower for keyword in ['exigence', 'requirement', 'obligation', 'contrainte']):
                    # Cette section contient probablement des requirements
                    section_reqs = self._extract_requirements_from_section(text, section)
                    requirements.extend(section_reqs)

        # Extraction depuis les tables
        tables = structured_content.get('tables', [])
        if tables:
            for table in tables:
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