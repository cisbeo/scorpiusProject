"""
Processeur de documents utilisant Docling d'IBM Research - Version 2.
Compatible avec l'interface async DocumentProcessor du projet.
Supporte PDF, DOCX, PPTX, XLSX, HTML et Markdown.
"""

import logging
import time
import tempfile
import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from src.processors.base import DocumentProcessor, ProcessingResult

logger = logging.getLogger(__name__)


@dataclass
class DoclingExtractionResult:
    """Résultat de l'extraction Docling."""
    text: str
    markdown: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    extraction_time: float = 0.0
    page_count: int = 0
    has_ocr: bool = False


class DocProcessorDocling(DocumentProcessor):
    """
    Processeur de documents utilisant Docling pour une extraction de haute qualité.
    Version 2 - Compatible avec l'interface async.
    Supporte plusieurs formats: PDF, DOCX, PPTX, XLSX, HTML, Markdown.
    """

    def __init__(self):
        """Initialise le processeur Docling."""
        super().__init__(name="DocProcessorDocling", version="2.0.0")
        self.converter = None
        self.supported_extensions = [".pdf", ".docx", ".pptx", ".xlsx", ".html", ".md"]
        self.supported_mime_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/html",
            "text/markdown"
        ]
        self._initialize_docling()

    def _initialize_docling(self):
        """Initialise Docling avec gestion des erreurs."""
        try:
            from docling.document_converter import DocumentConverter
            self.converter = DocumentConverter()
            logger.info("✅ Docling initialisé avec succès")
        except ImportError as e:
            logger.warning(f"⚠️ Docling non disponible: {e}")
            self.converter = None
        except Exception as e:
            logger.error(f"❌ Erreur initialisation Docling: {e}")
            self.converter = None

    def supports_file(self, filename: str, mime_type: Optional[str] = None) -> bool:
        """
        Vérifie si le processeur supporte le fichier.

        Args:
            filename: Nom du fichier
            mime_type: Type MIME du fichier

        Returns:
            True si le fichier est supporté
        """
        if not self.converter:
            return False

        # Vérifier l'extension
        extension = Path(filename).suffix.lower()
        if extension in self.supported_extensions:
            return True

        # Vérifier le type MIME
        if mime_type and mime_type in self.supported_mime_types:
            return True

        return False

    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        processing_options: Optional[dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Traite un document avec Docling de manière asynchrone.

        Args:
            file_content: Contenu binaire du document
            filename: Nom du fichier
            mime_type: Type MIME
            processing_options: Options de traitement

        Returns:
            ProcessingResult avec le contenu extrait
        """
        # Exécuter l'extraction dans un thread séparé car Docling n'est pas async
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self._process_document_sync,
            file_content,
            filename,
            mime_type,
            processing_options
        )

    def _process_document_sync(
        self,
        file_content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        processing_options: Optional[dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Version synchrone du traitement de document.
        """
        start_time = time.time()

        # Si Docling n'est pas disponible, retourner une erreur
        if not self.converter:
            result = ProcessingResult(
                raw_text="",
                structured_content={},
                success=False,
                processing_time_ms=0,
                processor_name=self.name,
                processor_version=self.version,
                page_count=0,
                word_count=0
            )
            result.add_error("Docling non disponible")
            return result

        try:
            # Sauvegarder temporairement le fichier (Docling a besoin d'un chemin)
            extension = Path(filename).suffix
            with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name

            try:
                # Extraction avec Docling
                logger.info(f"🔍 Extraction Docling: {filename}")
                extraction = self._extract_with_docling(tmp_path)

                # Calculer les statistiques
                processing_time = int((time.time() - start_time) * 1000)
                word_count = len(extraction.text.split()) if extraction.text else 0

                # Construire le contenu structuré
                structured_content = {
                    "sections": extraction.sections,
                    "tables": extraction.tables,
                    "markdown": extraction.markdown,
                    "extraction_method": "Docling",
                    "has_structure": len(extraction.sections) > 0,
                    "has_tables": len(extraction.tables) > 0,
                    "page_count": extraction.page_count,
                    "has_ocr": extraction.has_ocr
                }

                # Créer le résultat
                result = ProcessingResult(
                    raw_text=extraction.text,
                    structured_content=structured_content,
                    success=len(extraction.text) > 0,
                    processing_time_ms=processing_time,
                    processor_name=self.name,
                    processor_version=self.version,
                    page_count=extraction.page_count,
                    word_count=word_count,
                    confidence_score=extraction.confidence
                )

                if not extraction.text:
                    result.add_error("Aucun texte extrait")

                # Vérifier les problèmes d'espacement
                if "PR OGRAMME" in extraction.text or "DI GITALE" in extraction.text:
                    result.add_warning("Problèmes d'espacement détectés")

                logger.info(f"✅ Extraction réussie: {word_count} mots en {processing_time}ms")

            finally:
                # Nettoyer le fichier temporaire
                os.unlink(tmp_path)

            return result

        except Exception as e:
            logger.error(f"❌ Erreur extraction Docling: {e}")
            processing_time = int((time.time() - start_time) * 1000)

            result = ProcessingResult(
                raw_text="",
                structured_content={},
                success=False,
                processing_time_ms=processing_time,
                processor_name=self.name,
                processor_version=self.version,
                page_count=0,
                word_count=0
            )
            result.add_error(f"Erreur extraction: {str(e)}")
            return result

    def _extract_with_docling(self, file_path: str) -> DoclingExtractionResult:
        """
        Extrait le contenu avec Docling.

        Args:
            file_path: Chemin vers le fichier

        Returns:
            Résultat de l'extraction Docling
        """
        start_time = time.time()

        # Conversion avec Docling
        docling_result = self.converter.convert(file_path)

        # Extraire le texte et markdown
        text = ""
        markdown = ""
        tables = []
        sections = []
        metadata = {}

        if docling_result:
            # Export en markdown
            try:
                markdown = docling_result.document.export_to_markdown()
            except:
                pass

            # Export en texte brut
            try:
                text = docling_result.document.export_to_text()
            except:
                # Fallback: itération manuelle
                if hasattr(docling_result, 'document') and docling_result.document:
                    text_parts = []
                    for item in docling_result.document.iterate_items():
                        if hasattr(item, 'text'):
                            text_parts.append(str(item.text))
                    text = "\n".join(text_parts)

            # Si pas de texte du tout, utiliser le markdown
            if not text and markdown:
                text = markdown

            # Extraire les métadonnées
            if hasattr(docling_result, 'metadata'):
                metadata = docling_result.metadata

            # Détecter les tables
            if hasattr(docling_result.document, 'tables'):
                for table in docling_result.document.tables:
                    tables.append({
                        'content': str(table),
                        'rows': len(table.rows) if hasattr(table, 'rows') else 0,
                        'cols': len(table.columns) if hasattr(table, 'columns') else 0
                    })

            # Extraire les sections du markdown
            if markdown:
                import re
                section_pattern = r'^#{1,6}\s+(.+)$'
                for match in re.finditer(section_pattern, markdown, re.MULTILINE):
                    level = len(match.group(0).split()[0])
                    title = match.group(1)
                    sections.append({
                        'level': level,
                        'title': title,
                        'position': match.start()
                    })

        extraction_time = time.time() - start_time

        # Calculer le score de confiance
        confidence = self._calculate_confidence(text, tables, sections)

        # Estimer le nombre de pages
        page_count = len(sections) if sections else max(1, len(text) // 3000)

        return DoclingExtractionResult(
            text=text,
            markdown=markdown,
            metadata=metadata,
            tables=tables,
            sections=sections,
            confidence=confidence,
            extraction_time=extraction_time,
            page_count=page_count,
            has_ocr=metadata.get('has_ocr', False)
        )

    def _calculate_confidence(self, text: str, tables: List, sections: List) -> float:
        """Calcule un score de confiance pour l'extraction."""
        score = 0.0

        # Longueur du texte
        if len(text) > 1000:
            score += 0.3
        elif len(text) > 100:
            score += 0.1

        # Structure détectée
        if sections:
            score += 0.2

        # Tables détectées
        if tables:
            score += 0.1

        # Pas d'espaces bizarres
        if text and "PR OGRAMME" not in text and "DI GITALE" not in text:
            score += 0.3

        # Présence de mots français
        if text:
            french_words = ["le", "la", "les", "de", "du", "des", "et", "ou", "à"]
            word_count = sum(1 for word in french_words if word in text.lower())
            if word_count >= 5:
                score += 0.2

        return min(1.0, score)

    def extract_requirements(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrait les exigences du texte.

        Args:
            text: Texte à analyser

        Returns:
            Liste des exigences extraites
        """
        requirements = []

        # Patterns pour les exigences
        patterns = {
            'technical': [
                r'(?i)(?:doit|devra|devront)\s+(?:pouvoir\s+)?(.+?)(?:\.|;|$)',
                r'(?i)(?:capacité|capable)\s+(?:de\s+)?(.+?)(?:\.|;|$)',
            ],
            'functional': [
                r'(?i)(?:fonction|fonctionnalité)\s*:\s*(.+?)(?:\.|;|$)',
                r'(?i)(?:permet(?:tre)?|assure[r]?)\s+(?:de\s+)?(.+?)(?:\.|;|$)',
            ],
            'administrative': [
                r'(?i)(?:délai|échéance)\s*:\s*(.+?)(?:\.|;|$)',
                r'(?i)(?:garantie|assurance)\s+(.+?)(?:\.|;|$)',
            ]
        }

        import re

        for req_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                for match in re.finditer(pattern, text):
                    requirement = match.group(1).strip()
                    if len(requirement) > 10:  # Filtre les matches trop courts
                        requirements.append({
                            'type': req_type,
                            'text': requirement,
                            'confidence': 0.8
                        })

        return requirements