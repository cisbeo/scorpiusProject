#!/usr/bin/env python3
"""
POC: Docling PDF Processor for Scorpius Project.
Utilise Docling d'IBM pour extraction avancée de documents marchés publics.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Résultat d'extraction Docling."""
    success: bool
    filename: str
    method: str  # 'docling_native' ou 'docling_ocr'
    confidence: float
    raw_text: str
    structured_data: Dict[str, Any]
    tables: List[Dict[str, Any]]
    requirements: List[str]
    metadata: Dict[str, Any]
    processing_time_ms: float
    errors: List[str]


class DoclingPDFProcessor:
    """
    Processeur PDF utilisant Docling pour extraction intelligente.
    Résout les problèmes de PDFs Word 2013 et améliore l'extraction.
    """

    def __init__(self,
                 export_format: str = "json",
                 ocr_engine: str = "tesseract",
                 ocr_lang: str = "fra+eng"):
        """
        Initialise le processeur Docling.

        Args:
            export_format: Format d'export (json, markdown, text)
            ocr_engine: Moteur OCR (tesseract, easyocr)
            ocr_lang: Langues OCR
        """
        self.export_format = export_format
        self.ocr_engine = ocr_engine
        self.ocr_lang = ocr_lang

        # Import Docling
        try:
            from docling.datamodel import ConversionResult
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
            from docling.backend.pypdfium2_backend import PyPdfium2DocumentBackend

            self.docling_available = True

            # Configuration pipeline
            pipeline_options = PdfFormatOption(
                pipeline_cls=DoclingParseDocumentBackend,
                do_ocr=False,  # On essaie d'abord sans OCR
                do_table_structure=True,
                do_layout_analysis=True
            )

            # Configuration OCR si échec
            ocr_options = PdfFormatOption(
                pipeline_cls=PyPdfium2DocumentBackend,
                do_ocr=True,
                ocr_engine=ocr_engine,
                ocr_lang=ocr_lang,
                do_table_structure=True
            )

            # Créer les convertisseurs
            self.converter = DocumentConverter(
                format_options={
                    "pdf": pipeline_options
                }
            )

            self.ocr_converter = DocumentConverter(
                format_options={
                    "pdf": ocr_options
                }
            )

            logger.info("✅ Docling initialisé avec succès")

        except ImportError as e:
            self.docling_available = False
            logger.error(f"❌ Docling non disponible: {e}")
            raise RuntimeError("Docling n'est pas installé. Utilisez le Dockerfile fourni.")

    def process_pdf(self, pdf_path: Path) -> ExtractionResult:
        """
        Traite un PDF avec Docling.

        Args:
            pdf_path: Chemin vers le PDF

        Returns:
            ExtractionResult avec données extraites
        """
        start_time = datetime.now()
        errors = []

        if not self.docling_available:
            return ExtractionResult(
                success=False,
                filename=pdf_path.name,
                method="none",
                confidence=0.0,
                raw_text="",
                structured_data={},
                tables=[],
                requirements=[],
                metadata={},
                processing_time_ms=0,
                errors=["Docling non disponible"]
            )

        try:
            # Étape 1: Tentative d'extraction standard
            logger.info(f"📄 Traitement de {pdf_path.name}...")

            result = self._try_standard_extraction(pdf_path)

            # Vérifier la qualité
            confidence = self._calculate_confidence(result)

            if confidence < 0.95:
                logger.info(f"⚠️ Confiance faible ({confidence:.2%}), bascule sur OCR...")
                result = self._try_ocr_extraction(pdf_path)
                method = "docling_ocr"
                confidence = self._calculate_confidence(result)
            else:
                method = "docling_native"

            # Extraction du contenu
            raw_text = self._extract_text(result)
            structured_data = self._extract_structured_data(result)
            tables = self._extract_tables(result)
            requirements = self._extract_requirements(structured_data, raw_text)
            metadata = self._extract_metadata(result)

            # Calcul du temps
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(f"✅ Extraction terminée en {processing_time:.0f}ms (confiance: {confidence:.2%})")

            return ExtractionResult(
                success=True,
                filename=pdf_path.name,
                method=method,
                confidence=confidence,
                raw_text=raw_text,
                structured_data=structured_data,
                tables=tables,
                requirements=requirements,
                metadata=metadata,
                processing_time_ms=processing_time,
                errors=errors
            )

        except Exception as e:
            logger.error(f"❌ Erreur lors du traitement: {e}")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ExtractionResult(
                success=False,
                filename=pdf_path.name,
                method="error",
                confidence=0.0,
                raw_text="",
                structured_data={},
                tables=[],
                requirements=[],
                metadata={},
                processing_time_ms=processing_time,
                errors=[str(e)]
            )

    def _try_standard_extraction(self, pdf_path: Path):
        """Extraction standard avec Docling."""
        return self.converter.convert(str(pdf_path))

    def _try_ocr_extraction(self, pdf_path: Path):
        """Extraction avec OCR."""
        return self.ocr_converter.convert(str(pdf_path))

    def _calculate_confidence(self, result) -> float:
        """
        Calcule le score de confiance de l'extraction.
        Détecte les problèmes comme "PR OGRAMME", "DI GITALE".
        """
        if not result or not result.document:
            return 0.0

        confidence = 1.0
        text_sample = ""

        # Extraire un échantillon de texte
        for element in result.document.iterate_items():
            if hasattr(element, 'text'):
                text_sample += str(element.text) + " "
                if len(text_sample) > 1000:
                    break

        # Vérifier les problèmes connus
        import re

        # Espaces dans les mots
        broken_words = re.findall(r'\b[A-Z]{1,2}\s+[A-Z]{2,}\b', text_sample)
        if broken_words:
            confidence -= 0.1 * len(broken_words)
            logger.debug(f"Mots cassés détectés: {broken_words[:5]}")

        # Patterns spécifiques Word 2013
        if "PR OGRAMME" in text_sample or "DI GITALE" in text_sample:
            confidence -= 0.3
            logger.debug("Problèmes Word 2013 détectés")

        # Vérifier la présence de contenu français
        french_words = re.findall(r'\b(le|la|les|de|des|un|une|pour|dans|sur|avec)\b', text_sample.lower())
        if len(french_words) < 5:
            confidence -= 0.2
            logger.debug("Peu de mots français détectés")

        return max(0.0, min(1.0, confidence))

    def _extract_text(self, result) -> str:
        """Extrait le texte brut du résultat Docling."""
        if not result or not result.document:
            return ""

        text_parts = []
        for element in result.document.iterate_items():
            if hasattr(element, 'text'):
                text_parts.append(str(element.text))

        return "\n".join(text_parts)

    def _extract_structured_data(self, result) -> Dict[str, Any]:
        """Extrait les données structurées."""
        if not result or not result.document:
            return {}

        structured = {
            "sections": {},
            "lists": [],
            "headings": [],
            "document_type": "unknown"
        }

        # Parcourir les éléments
        for element in result.document.iterate_items():
            # Headings
            if hasattr(element, 'level') and element.level:
                structured["headings"].append({
                    "level": element.level,
                    "text": str(element.text) if hasattr(element, 'text') else ""
                })

            # Lists
            if hasattr(element, 'type') and element.type == 'list_item':
                structured["lists"].append(str(element.text) if hasattr(element, 'text') else "")

        # Détecter le type de document
        full_text = self._extract_text(result).lower()
        if "cctp" in full_text or "clauses techniques" in full_text:
            structured["document_type"] = "CCTP"
        elif "ccap" in full_text or "clauses administratives" in full_text:
            structured["document_type"] = "CCAP"

        return structured

    def _extract_tables(self, result) -> List[Dict[str, Any]]:
        """Extrait les tableaux du document."""
        if not result or not result.document:
            return []

        tables = []

        for element in result.document.iterate_items():
            if hasattr(element, 'type') and element.type == 'table':
                # Extraire les données du tableau
                table_data = {
                    "rows": [],
                    "headers": [],
                    "caption": ""
                }

                if hasattr(element, 'data'):
                    # Convertir en format lisible
                    for row in element.data:
                        table_data["rows"].append([str(cell) for cell in row])

                tables.append(table_data)

        return tables

    def _extract_requirements(self, structured_data: Dict, raw_text: str) -> List[str]:
        """
        Extrait les requirements/exigences du document.
        Utilise la structure + patterns spécifiques.
        """
        requirements = []

        # Depuis les listes structurées
        for item in structured_data.get("lists", []):
            if any(keyword in item.lower() for keyword in ["doit", "devra", "obligatoire", "requis", "exigé"]):
                requirements.append(item)

        # Patterns dans le texte brut
        import re

        # Patterns pour requirements
        patterns = [
            r"(?:La partie [AB] comprend|comprend les prestations suivantes)[\s:]*([^\.]+(?:\.[^\.]+)*)",
            r"(?:prestations?[\s:]+)([^\n]+(?:\n(?![A-Z])[^\n]+)*)",
            r"(?:- )([^-\n]+)",  # Items de liste
            r"(?:\d+\.\s+)([^\.]+\.)",  # Items numérotés
        ]

        for pattern in patterns:
            matches = re.findall(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                cleaned = match.strip()
                if len(cleaned) > 20 and len(cleaned) < 500:
                    requirements.append(cleaned)

        # Dédupliquer
        seen = set()
        unique_requirements = []
        for req in requirements:
            req_lower = req.lower()
            if req_lower not in seen:
                seen.add(req_lower)
                unique_requirements.append(req)

        return unique_requirements

    def _extract_metadata(self, result) -> Dict[str, Any]:
        """Extrait les métadonnées du document."""
        metadata = {
            "page_count": 0,
            "language": "fr",
            "creation_date": None,
            "author": None
        }

        if result and hasattr(result, 'metadata'):
            # Extraire depuis Docling
            if hasattr(result.metadata, 'page_count'):
                metadata["page_count"] = result.metadata.page_count

            if hasattr(result.metadata, 'language'):
                metadata["language"] = result.metadata.language

        return metadata


class DoclingComparator:
    """Compare les résultats Docling avec l'extraction actuelle."""

    def __init__(self):
        self.processor = DoclingPDFProcessor()

    def compare_extraction(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Compare Docling vs extraction traditionnelle.

        Returns:
            Dictionnaire avec métriques de comparaison
        """
        # Extraction Docling
        docling_result = self.processor.process_pdf(pdf_path)

        # Extraction traditionnelle (simulée pour le POC)
        traditional_result = self._traditional_extraction(pdf_path)

        # Comparaison
        comparison = {
            "filename": pdf_path.name,
            "docling": {
                "method": docling_result.method,
                "confidence": docling_result.confidence,
                "text_length": len(docling_result.raw_text),
                "requirements_count": len(docling_result.requirements),
                "tables_count": len(docling_result.tables),
                "processing_time_ms": docling_result.processing_time_ms,
                "has_problems": self._check_problems(docling_result.raw_text)
            },
            "traditional": {
                "method": "pypdf2",
                "confidence": traditional_result.get("confidence", 0),
                "text_length": len(traditional_result.get("text", "")),
                "requirements_count": traditional_result.get("requirements_count", 0),
                "tables_count": 0,  # PyPDF2 ne détecte pas les tables
                "processing_time_ms": traditional_result.get("time_ms", 0),
                "has_problems": self._check_problems(traditional_result.get("text", ""))
            },
            "improvements": {}
        }

        # Calculer les améliorations
        improvements = comparison["improvements"]

        # Amélioration du texte
        if not comparison["docling"]["has_problems"] and comparison["traditional"]["has_problems"]:
            improvements["text_quality"] = "✅ Docling résout les problèmes d'espacement"

        # Amélioration des requirements
        req_improvement = comparison["docling"]["requirements_count"] - comparison["traditional"]["requirements_count"]
        if req_improvement > 0:
            improvements["requirements"] = f"+{req_improvement} requirements détectés"

        # Amélioration des tables
        if comparison["docling"]["tables_count"] > 0:
            improvements["tables"] = f"{comparison['docling']['tables_count']} tables extraites (vs 0)"

        # Performance
        if comparison["docling"]["processing_time_ms"] < comparison["traditional"]["processing_time_ms"]:
            speed_improvement = (1 - comparison["docling"]["processing_time_ms"] / comparison["traditional"]["processing_time_ms"]) * 100
            improvements["speed"] = f"{speed_improvement:.1f}% plus rapide"

        return comparison

    def _traditional_extraction(self, pdf_path: Path) -> Dict[str, Any]:
        """Simule l'extraction traditionnelle avec PyPDF2."""
        import time

        start = time.time()
        result = {
            "text": "",
            "confidence": 0.4,
            "requirements_count": 0
        }

        try:
            import PyPDF2

            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text_parts = []

                for page in reader.pages:
                    text_parts.append(page.extract_text())

                result["text"] = "\n".join(text_parts)

                # Simuler l'extraction de requirements (basique)
                import re
                requirements = re.findall(r'- ([^-\n]+)', result["text"])
                result["requirements_count"] = len(requirements)

        except Exception as e:
            logger.error(f"Erreur extraction traditionnelle: {e}")

        result["time_ms"] = (time.time() - start) * 1000
        return result

    def _check_problems(self, text: str) -> bool:
        """Vérifie si le texte a des problèmes connus."""
        problems = ["PR OGRAMME", "DI GITALE", "an imation"]
        return any(problem in text for problem in problems)


def main():
    """Fonction principale pour tester le POC."""

    # Chemins de test
    test_files = [
        Path("/app/data/examples/CCTP_HEC.pdf"),
        Path("/app/data/test/sample.pdf")
    ]

    # Initialiser le comparateur
    comparator = DoclingComparator()

    # Tester chaque fichier
    for pdf_path in test_files:
        if pdf_path.exists():
            logger.info(f"\n{'='*60}")
            logger.info(f"Test de {pdf_path.name}")
            logger.info(f"{'='*60}")

            # Comparer les extractions
            comparison = comparator.compare_extraction(pdf_path)

            # Afficher les résultats
            print(json.dumps(comparison, indent=2, ensure_ascii=False))

            # Sauvegarder les résultats
            output_path = Path(f"/app/output/{pdf_path.stem}_comparison.json")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(comparison, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Résultats sauvegardés dans {output_path}")
        else:
            logger.warning(f"❌ Fichier non trouvé: {pdf_path}")


if __name__ == "__main__":
    main()