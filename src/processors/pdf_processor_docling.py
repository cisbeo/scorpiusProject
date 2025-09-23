"""
Processeur PDF utilisant Docling d'IBM Research.
Solution principale pour l'extraction de texte depuis les PDFs.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
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


class PDFProcessorDocling(DocumentProcessor):
    """
    Processeur PDF utilisant Docling pour une extraction de haute qualité.

    Docling offre:
    - Extraction de texte avec préservation de la structure
    - Export en Markdown avec formatage
    - Détection et extraction des tables
    - OCR intégré pour les documents scannés
    - Gestion des layouts complexes
    - Support des documents multilingues
    """

    def __init__(self):
        """Initialise le processeur Docling."""
        super().__init__()
        self.converter = None
        self._initialize_docling()

    def _initialize_docling(self):
        """Initialise Docling avec gestion des erreurs."""
        try:
            from docling.document_converter import DocumentConverter
            self.converter = DocumentConverter()
            logger.info("✅ Docling initialisé avec succès")
        except ImportError as e:
            logger.warning(f"⚠️ Docling non disponible: {e}")
            logger.info("Utilisez 'pip install docling' pour l'installer")
            self.converter = None
        except Exception as e:
            logger.error(f"❌ Erreur initialisation Docling: {e}")
            self.converter = None

    def can_process(self, file_path: Path) -> bool:
        """
        Vérifie si le fichier peut être traité par Docling.

        Args:
            file_path: Chemin vers le fichier

        Returns:
            True si le fichier peut être traité
        """
        if not self.converter:
            return False

        # Docling supporte PDF, DOCX, PPTX, XLSX, HTML, MD
        supported_extensions = {'.pdf', '.docx', '.pptx', '.xlsx', '.html', '.md'}
        return file_path.suffix.lower() in supported_extensions

    def extract_with_docling(self, file_path: Path) -> DoclingExtractionResult:
        """
        Extrait le contenu avec Docling.

        Args:
            file_path: Chemin vers le fichier

        Returns:
            Résultat de l'extraction Docling
        """
        if not self.converter:
            raise RuntimeError("Docling non initialisé")

        start_time = time.time()

        try:
            # Conversion avec Docling
            logger.info(f"🔍 Extraction Docling: {file_path.name}")
            result = self.converter.convert(str(file_path))

            # Extraire le texte et markdown
            text = ""
            markdown = ""
            tables = []
            sections = []

            if result:
                # Export en markdown (préserve la structure)
                try:
                    markdown = result.document.export_to_markdown()
                except:
                    pass

                # Export en texte brut
                try:
                    text = result.document.export_to_text()
                except:
                    # Fallback: itération manuelle
                    if hasattr(result, 'document') and result.document:
                        text_parts = []
                        for item in result.document.iterate_items():
                            if hasattr(item, 'text'):
                                text_parts.append(str(item.text))
                        text = "\n".join(text_parts)

                # Extraire les métadonnées
                metadata = {}
                if hasattr(result, 'metadata'):
                    metadata = result.metadata

                # Détecter les tables
                if hasattr(result.document, 'tables'):
                    for table in result.document.tables:
                        tables.append({
                            'content': str(table),
                            'rows': len(table.rows) if hasattr(table, 'rows') else 0,
                            'cols': len(table.columns) if hasattr(table, 'columns') else 0
                        })

                # Détecter les sections
                if markdown:
                    # Analyser le markdown pour extraire les sections
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

            # Si pas de texte du tout, lever une exception
            if not text and not markdown:
                raise ValueError("Aucun texte extrait par Docling")

            # Utiliser markdown si text est vide
            if not text and markdown:
                text = markdown

            extraction_time = time.time() - start_time

            # Calculer le score de confiance
            confidence = self._calculate_confidence(text, tables, sections)

            logger.info(f"✅ Extraction Docling réussie: {len(text)} caractères en {extraction_time:.2f}s")

            return DoclingExtractionResult(
                text=text,
                markdown=markdown,
                metadata=metadata,
                tables=tables,
                sections=sections,
                confidence=confidence,
                extraction_time=extraction_time,
                page_count=metadata.get('page_count', 0),
                has_ocr=metadata.get('has_ocr', False)
            )

        except Exception as e:
            logger.error(f"❌ Erreur extraction Docling: {e}")
            raise

    def _calculate_confidence(self, text: str, tables: List, sections: List) -> float:
        """
        Calcule un score de confiance pour l'extraction.

        Args:
            text: Texte extrait
            tables: Tables détectées
            sections: Sections détectées

        Returns:
            Score de confiance entre 0 et 1
        """
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

        # Pas d'espaces bizarres (problème Word 2013)
        if "PR OGRAMME" not in text and "DI GITALE" not in text:
            score += 0.3

        # Présence de mots français courants
        french_words = ["le", "la", "les", "de", "du", "des", "et", "ou", "à"]
        word_count = sum(1 for word in french_words if word in text.lower())
        if word_count >= 5:
            score += 0.1

        return min(1.0, score)

    def process_document(self, file_path: Path) -> ProcessingResult:
        """
        Traite un document PDF avec Docling.

        Args:
            file_path: Chemin vers le fichier PDF

        Returns:
            Résultat du traitement
        """
        if not self.can_process(file_path):
            # Fallback vers le processeur de base
            logger.warning("Docling non disponible, utilisation du processeur de base")
            from src.processors.pdf_multi_extractor import PDFMultiExtractor
            fallback = PDFMultiExtractor()
            return fallback.process_document(file_path)

        try:
            # Extraction avec Docling
            extraction = self.extract_with_docling(file_path)

            # Construire le contenu structuré
            structured_content = {
                "summary": {
                    "page_count": extraction.page_count,
                    "extraction_method": "Docling",
                    "confidence": extraction.confidence,
                    "has_tables": len(extraction.tables) > 0,
                    "has_sections": len(extraction.sections) > 0,
                    "has_ocr": extraction.has_ocr,
                    "extraction_time": extraction.extraction_time
                },
                "sections": extraction.sections,
                "tables": extraction.tables,
                "full_text": extraction.text,
                "markdown": extraction.markdown
            }

            # Métadonnées
            metadata = {
                "processor": "PDFProcessorDocling",
                "docling_version": self._get_docling_version(),
                "extraction_time": extraction.extraction_time,
                "confidence": extraction.confidence,
                **extraction.metadata
            }

            # Validation de base
            validation_errors = []
            if not extraction.text:
                validation_errors.append("Aucun texte extrait")
            if extraction.confidence < 0.5:
                validation_errors.append(f"Confiance faible: {extraction.confidence:.2%}")

            # Log des statistiques
            logger.info(f"📊 Extraction Docling terminée:")
            logger.info(f"   • Texte: {len(extraction.text)} caractères")
            logger.info(f"   • Tables: {len(extraction.tables)}")
            logger.info(f"   • Sections: {len(extraction.sections)}")
            logger.info(f"   • Confiance: {extraction.confidence:.2%}")
            logger.info(f"   • Temps: {extraction.extraction_time:.2f}s")

            return ProcessingResult(
                success=len(validation_errors) == 0,
                extracted_text=extraction.text,
                structured_content=structured_content,
                metadata=metadata,
                validation_errors=validation_errors
            )

        except Exception as e:
            logger.error(f"Erreur lors du traitement avec Docling: {e}")

            # Tentative de fallback
            try:
                logger.info("Tentative avec processeur de fallback...")
                from src.processors.pdf_multi_extractor import PDFMultiExtractor
                fallback = PDFMultiExtractor()
                return fallback.process_document(file_path)
            except Exception as fallback_error:
                logger.error(f"Échec du fallback: {fallback_error}")
                return ProcessingResult(
                    success=False,
                    extracted_text="",
                    structured_content={},
                    metadata={"error": str(e)},
                    validation_errors=[f"Erreur extraction: {str(e)}"]
                )

    def _get_docling_version(self) -> str:
        """Récupère la version de Docling."""
        try:
            import docling
            return getattr(docling, '__version__', 'unknown')
        except:
            return 'unknown'

    def extract_requirements(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrait les exigences du texte.
        Utilise la structure préservée par Docling pour une meilleure extraction.

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
                r'(?i)(?:compatible|conformité)\s+(?:avec\s+)?(.+?)(?:\.|;|$)',
            ],
            'functional': [
                r'(?i)(?:fonction|fonctionnalité)\s*:\s*(.+?)(?:\.|;|$)',
                r'(?i)(?:permet(?:tre)?|assure[r]?)\s+(?:de\s+)?(.+?)(?:\.|;|$)',
            ],
            'administrative': [
                r'(?i)(?:délai|échéance)\s*:\s*(.+?)(?:\.|;|$)',
                r'(?i)(?:garantie|assurance)\s+(.+?)(?:\.|;|$)',
                r'(?i)(?:livraison|livrable)\s+(.+?)(?:\.|;|$)',
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

    @property
    def name(self) -> str:
        """Nom du processeur."""
        return "PDFProcessorDocling"

    @property
    def version(self) -> str:
        """Version du processeur."""
        return "1.0.0"

    @property
    def supported_formats(self) -> List[str]:
        """Formats supportés."""
        return ["pdf", "docx", "pptx", "xlsx", "html", "md"]