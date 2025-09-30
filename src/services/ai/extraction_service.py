"""AI-powered requirement extraction service."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.models.document import ProcurementDocument, DocumentStatus
from src.models.extracted_requirement import ExtractedRequirement as ExtractedRequirementModel
from src.models.analysis import AnalysisHistory, AnalysisStatus
from src.repositories.document_repository import DocumentRepository
from src.repositories.requirements_repository import RequirementsRepository
from src.services.ai.mistral_service import MistralAIService
from src.api.v1.schemas.extraction import (
    RequirementCategory,
    RequirementPriority,
    ExtractedRequirement
)

logger = logging.getLogger(__name__)


class ExtractionService:
    """Service for extracting requirements from procurement documents using AI."""

    def __init__(
        self,
        db: AsyncSession,
        mistral_service: Optional[MistralAIService] = None
    ):
        """Initialize extraction service."""
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.req_repo = RequirementsRepository(db)
        self.mistral_service = mistral_service or MistralAIService()

    async def extract_requirements_from_tender(
        self,
        tender_id: UUID,
        document_types: Optional[List[str]] = None,
        force_reprocess: bool = False
    ) -> Dict[str, Any]:
        """
        Extract requirements from all documents in a tender.

        Args:
            tender_id: The tender UUID
            document_types: Specific document types to process (None = all)
            force_reprocess: Force reprocessing even if already extracted

        Returns:
            Dictionary with extraction results
        """
        try:
            # Create analysis record
            analysis_id = uuid4()
            analysis = AnalysisHistory(
                id=analysis_id,
                tender_id=tender_id,
                analysis_type="requirements_extraction",
                status=AnalysisStatus.PROCESSING,
                started_at=datetime.utcnow(),
                analysis_metadata={"document_types": document_types}
            )
            self.db.add(analysis)
            await self.db.commit()

            # Get documents for the tender
            documents = await self.doc_repo.get_by_tender(tender_id)

            if document_types:
                documents = [
                    doc for doc in documents
                    if doc.document_type in document_types
                ]

            if not documents:
                await self._update_analysis_status(
                    analysis_id,
                    AnalysisStatus.COMPLETED,
                    {"message": "No documents found"}
                )
                return {
                    "analysis_id": analysis_id,
                    "tender_id": tender_id,
                    "status": "completed",
                    "message": "No documents to process",
                    "documents_processed": 0,
                    "requirements_extracted": 0
                }

            # Check if already extracted (unless force_reprocess)
            if not force_reprocess:
                existing = await self.req_repo.get_by_tender(tender_id)
                if existing:
                    await self._update_analysis_status(
                        analysis_id,
                        AnalysisStatus.COMPLETED,
                        {"message": "Using existing extraction"}
                    )
                    return {
                        "analysis_id": analysis_id,
                        "tender_id": tender_id,
                        "status": "completed",
                        "message": "Requirements already extracted",
                        "documents_processed": len(documents),
                        "requirements_extracted": len(existing)
                    }

            # Process each document
            total_requirements = 0
            documents_processed = 0

            for doc in documents:
                if doc.status != DocumentStatus.PROCESSED:
                    logger.warning(f"Skipping unprocessed document {doc.id}")
                    continue

                try:
                    requirements = await self._extract_from_document(doc)

                    # Save requirements to database
                    for req in requirements:
                        db_requirement = ExtractedRequirementModel(
                            id=uuid4(),
                            tender_id=tender_id,
                            document_id=doc.id,
                            requirement_text=req.requirement_text,
                            category=req.category,
                            priority=req.priority,
                            is_mandatory=req.is_mandatory,
                            confidence_score=req.confidence_score,
                            source_document=doc.document_type or "UNKNOWN",
                            page_number=req.page_number,
                            extraction_metadata=req.metadata
                        )
                        self.db.add(db_requirement)
                        total_requirements += 1

                    documents_processed += 1
                    logger.info(f"Extracted {len(requirements)} requirements from {doc.id}")

                except Exception as e:
                    logger.error(f"Failed to extract from document {doc.id}: {e}")
                    continue

            # Commit all requirements
            await self.db.commit()

            # Update analysis status
            await self._update_analysis_status(
                analysis_id,
                AnalysisStatus.COMPLETED,
                {
                    "documents_processed": documents_processed,
                    "requirements_extracted": total_requirements
                }
            )

            return {
                "analysis_id": analysis_id,
                "tender_id": tender_id,
                "status": "completed",
                "message": f"Extracted {total_requirements} requirements",
                "documents_processed": documents_processed,
                "requirements_extracted": total_requirements
            }

        except Exception as e:
            logger.error(f"Extraction failed for tender {tender_id}: {e}")
            if 'analysis_id' in locals():
                await self._update_analysis_status(
                    analysis_id,
                    AnalysisStatus.FAILED,
                    {"error": str(e)}
                )
            raise

    async def _extract_from_document(
        self,
        document: ProcurementDocument
    ) -> List[ExtractedRequirement]:
        """Extract requirements from a single document."""

        # Get document content
        content = document.processed_content
        if not content:
            logger.warning(f"No processed content for document {document.id}")
            return []

        # Prepare extraction prompt
        prompt = self._create_extraction_prompt(
            content,
            document.document_type or "UNKNOWN"
        )

        # Call Mistral AI for extraction
        try:
            response = await self.mistral_service.generate_completion(
                prompt=prompt,
                max_tokens=4000,
                temperature=0.3  # Lower temperature for more consistent extraction
            )

            # Parse the response
            requirements = self._parse_extraction_response(
                response,
                document.document_type
            )

            return requirements

        except Exception as e:
            logger.error(f"Mistral extraction failed: {e}")
            # Fallback to simple extraction
            return self._simple_extraction_fallback(content, document.document_type)

    def _create_extraction_prompt(self, content: str, doc_type: str) -> str:
        """Create the prompt for Mistral AI extraction."""
        return f"""Analysez ce document de marché public ({doc_type}) et extrayez TOUS les requirements/exigences.

Pour CHAQUE requirement trouvé, fournissez:
1. Le texte exact de l'exigence
2. La catégorie (functional, technical, security, performance, compliance, financial, administrative, other)
3. La priorité (critical, high, medium, low)
4. Si c'est obligatoire (true/false)

Répondez UNIQUEMENT en JSON avec ce format exact:
{{
    "requirements": [
        {{
            "text": "...",
            "category": "...",
            "priority": "...",
            "is_mandatory": true/false
        }}
    ]
}}

Document à analyser:
{content[:8000]}  # Limité pour éviter de dépasser les limites de tokens

Extrayez maintenant TOUS les requirements:"""

    def _parse_extraction_response(
        self,
        response: str,
        doc_type: str
    ) -> List[ExtractedRequirement]:
        """Parse the AI response into ExtractedRequirement objects."""
        requirements = []

        try:
            # Try to parse as JSON
            data = json.loads(response)

            for req_data in data.get("requirements", []):
                try:
                    requirement = ExtractedRequirement(
                        requirement_text=req_data.get("text", ""),
                        category=RequirementCategory(
                            req_data.get("category", "other").lower()
                        ),
                        priority=RequirementPriority(
                            req_data.get("priority", "medium").lower()
                        ),
                        is_mandatory=req_data.get("is_mandatory", False),
                        source_document=doc_type,
                        confidence_score=0.9  # High confidence for AI extraction
                    )
                    requirements.append(requirement)
                except Exception as e:
                    logger.warning(f"Failed to parse requirement: {e}")
                    continue

        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON response, using fallback")
            # Fallback: extract lines that look like requirements
            lines = response.split('\n')
            for line in lines:
                if any(keyword in line.lower() for keyword in
                       ['doit', 'devra', 'obligatoire', 'requis', 'nécessaire']):
                    requirement = ExtractedRequirement(
                        requirement_text=line.strip(),
                        category=RequirementCategory.OTHER,
                        priority=RequirementPriority.MEDIUM,
                        is_mandatory=True,
                        source_document=doc_type,
                        confidence_score=0.5  # Lower confidence for fallback
                    )
                    requirements.append(requirement)

        return requirements

    def _simple_extraction_fallback(
        self,
        content: str,
        doc_type: str
    ) -> List[ExtractedRequirement]:
        """Simple rule-based extraction as fallback."""
        requirements = []

        # Keywords that indicate requirements
        requirement_keywords = [
            'doit', 'devra', 'devront', 'obligatoire', 'requis',
            'nécessaire', 'exigé', 'minimum', 'maximum', 'impératif'
        ]

        # Category detection patterns
        category_patterns = {
            RequirementCategory.TECHNICAL: ['technique', 'système', 'architecture', 'api'],
            RequirementCategory.SECURITY: ['sécurité', 'chiffrement', 'authentification', 'certificat'],
            RequirementCategory.PERFORMANCE: ['performance', 'temps de réponse', 'débit', 'latence'],
            RequirementCategory.FUNCTIONAL: ['fonctionnel', 'fonction', 'module', 'interface'],
            RequirementCategory.COMPLIANCE: ['norme', 'iso', 'rgpd', 'conformité'],
            RequirementCategory.FINANCIAL: ['prix', 'coût', 'budget', 'financier'],
            RequirementCategory.ADMINISTRATIVE: ['administratif', 'contrat', 'délai', 'livraison']
        }

        # Split into sentences
        sentences = content.replace('\n', ' ').split('.')

        for sentence in sentences:
            sentence_lower = sentence.lower().strip()

            # Check if sentence contains requirement keywords
            if any(keyword in sentence_lower for keyword in requirement_keywords):
                # Determine category
                category = RequirementCategory.OTHER
                for cat, patterns in category_patterns.items():
                    if any(pattern in sentence_lower for pattern in patterns):
                        category = cat
                        break

                # Determine priority
                priority = RequirementPriority.MEDIUM
                if 'obligatoire' in sentence_lower or 'impératif' in sentence_lower:
                    priority = RequirementPriority.HIGH
                elif 'critique' in sentence_lower or 'vital' in sentence_lower:
                    priority = RequirementPriority.CRITICAL

                requirement = ExtractedRequirement(
                    requirement_text=sentence.strip(),
                    category=category,
                    priority=priority,
                    is_mandatory='obligatoire' in sentence_lower,
                    source_document=doc_type,
                    confidence_score=0.3  # Low confidence for rule-based
                )
                requirements.append(requirement)

        return requirements

    async def _update_analysis_status(
        self,
        analysis_id: UUID,
        status: AnalysisStatus,
        metadata: Dict[str, Any]
    ):
        """Update the analysis record status."""
        try:
            result = await self.db.execute(
                select(AnalysisHistory).where(AnalysisHistory.id == analysis_id)
            )
            analysis = result.scalar_one_or_none()

            if analysis:
                analysis.status = status
                analysis.completed_at = datetime.utcnow() if status != AnalysisStatus.PROCESSING else None
                analysis.analysis_metadata = {**(analysis.analysis_metadata or {}), **metadata}
                await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update analysis status: {e}")

    async def get_analysis_status(self, analysis_id: UUID) -> Optional[Dict[str, Any]]:
        """Get the status of an analysis."""
        result = await self.db.execute(
            select(AnalysisHistory).where(AnalysisHistory.id == analysis_id)
        )
        analysis = result.scalar_one_or_none()

        if not analysis:
            return None

        # Calculate progress
        metadata = analysis.analysis_metadata or {}
        total_docs = metadata.get("total_documents", 0)
        processed_docs = metadata.get("documents_processed", 0)
        progress = (processed_docs / total_docs * 100) if total_docs > 0 else 0

        return {
            "analysis_id": analysis.id,
            "tender_id": analysis.tender_id,
            "status": analysis.status.value if hasattr(analysis.status, 'value') else analysis.status,
            "progress_percentage": int(progress),
            "documents_processed": processed_docs,
            "total_documents": total_docs,
            "requirements_extracted": metadata.get("requirements_extracted", 0),
            "started_at": analysis.started_at,
            "completed_at": analysis.completed_at,
            "error_message": metadata.get("error")
        }