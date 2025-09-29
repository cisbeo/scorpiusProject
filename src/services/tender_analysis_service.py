"""Tender analysis service for AI-powered multi-document analysis."""

import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document_type import DocumentType
from src.models.procurement_tender import ProcurementTender, TenderStatus
from src.models.document import ProcurementDocument, DocumentStatus
from src.models.requirements import ExtractedRequirements
from src.models.match import CapabilityMatch, MatchRecommendation
from src.repositories.tender_repository import TenderRepository
from src.repositories.document_repository import DocumentRepository
from src.services.tender_service import TenderService
from src.core.exceptions import NotFoundError, ProcessingError, BusinessLogicError


class TenderAnalysisService:
    """
    Service for AI-powered tender analysis and cross-document processing.

    Handles multi-document analysis, requirement extraction, capability matching,
    and consolidated tender scoring for French public procurement documents.
    """

    def __init__(self, db_session: AsyncSession):
        """Initialize analysis service with repositories."""
        self.db = db_session
        self.tender_repo = TenderRepository(db_session)
        self.document_repo = DocumentRepository(db_session)
# Note: The existing models have different structure - ExtractedRequirements is per document
        # and CapabilityMatch references ExtractedRequirements, not tender directly
        self.tender_service = TenderService(db_session)

    async def analyze_tender_documents(
        self,
        tender_id: UUID,
        force_reanalysis: bool = False,
        tenant_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive multi-document analysis of a tender.

        Args:
            tender_id: UUID of the tender to analyze
            force_reanalysis: Whether to force re-analysis of already analyzed documents
            tenant_id: Tenant ID for isolation

        Returns:
            Comprehensive analysis results

        Raises:
            NotFoundError: If tender not found
            ProcessingError: If analysis fails
        """
        # Get tender with documents
        tender = await self.tender_service.get_tender_with_documents(
            tender_id=tender_id,
            tenant_id=tenant_id
        )

        # Check tender completeness
        completeness = await self.tender_service.get_tender_completeness(
            tender_id=tender_id,
            tenant_id=tenant_id
        )

        if not completeness["can_analyze"]:
            raise ProcessingError(
                f"Tender {tender_id} is not ready for analysis. "
                f"Completeness: {completeness['completeness_score']}%"
            )

        # Update tender status to analyzing
        await self.tender_service.update_tender_status(
            tender_id=tender_id,
            new_status=TenderStatus.ANALYZING,
            tenant_id=tenant_id
        )

        try:
            # Step 1: Extract requirements from each document
            document_analyses = await self._analyze_individual_documents(
                tender.documents,
                force_reanalysis,
                tenant_id
            )

            # Step 2: Cross-reference analysis between documents
            cross_references = await self._analyze_cross_references(
                tender.documents,
                document_analyses,
                tenant_id
            )

            # Step 3: Consolidate global requirements
            global_requirements = await self._consolidate_requirements(
                document_analyses,
                cross_references,
                tender_id,
                tenant_id
            )

            # Step 4: Generate capability matches and recommendations (simplified)
            matches_and_score = await self._generate_simplified_matches(
                global_requirements,
                tender_id,
                tenant_id
            )

            # Step 5: Create final consolidated analysis
            global_analysis = {
                "tender_id": str(tender_id),
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "document_count": len(tender.documents),
                "completeness_score": completeness["completeness_score"],
                "document_analyses": document_analyses,
                "cross_references": cross_references,
                "global_requirements": global_requirements,
                "capability_matches": matches_and_score["matches"],
                "matching_score": matches_and_score["score"],
                "recommendations": matches_and_score["recommendations"],
                "risk_assessment": await self._assess_tender_risks(
                    tender, global_requirements, tenant_id
                ),
                "strategic_insights": await self._generate_strategic_insights(
                    tender, global_requirements, matches_and_score, tenant_id
                )
            }

            # Step 6: Update tender with analysis results
            await self.tender_repo.update_analysis(
                tender_id=tender_id,
                global_analysis=global_analysis,
                matching_score=matches_and_score["score"],
                tenant_id=tenant_id
            )

            # Step 7: Update tender status to ready
            await self.tender_service.update_tender_status(
                tender_id=tender_id,
                new_status=TenderStatus.READY,
                tenant_id=tenant_id
            )

            return global_analysis

        except Exception as e:
            # Revert tender status on failure
            await self.tender_service.update_tender_status(
                tender_id=tender_id,
                new_status=TenderStatus.DRAFT,
                tenant_id=tenant_id
            )
            raise ProcessingError(f"Tender analysis failed: {str(e)}")

    async def _analyze_individual_documents(
        self,
        documents: List[ProcurementDocument],
        force_reanalysis: bool,
        tenant_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """
        Analyze each document individually to extract requirements.

        Args:
            documents: List of tender documents
            force_reanalysis: Whether to force re-analysis
            tenant_id: Tenant ID for isolation

        Returns:
            Dictionary mapping document IDs to their analysis results
        """
        document_analyses = {}

        # Process documents in parallel where possible
        analysis_tasks = []
        for doc in documents:
            if doc.status != DocumentStatus.PROCESSED:
                continue  # Skip unprocessed documents

            # Check if document already has extracted requirements (simplified check)
            # In the current model, each document has one ExtractedRequirements record
            if hasattr(doc, 'extracted_requirements') and doc.extracted_requirements and not force_reanalysis:
                # Use existing analysis
                req = doc.extracted_requirements
                document_analyses[str(doc.id)] = {
                    "document_type": doc.document_type,
                    "filename": doc.original_filename,
                    "requirements": req.requirements_json,
                    "evaluation_criteria": req.evaluation_criteria_json,
                    "extracted_at": req.created_at.isoformat(),
                    "reused_existing": True
                }
            else:
                # Queue for new analysis
                task = self._analyze_single_document(doc, tenant_id)
                analysis_tasks.append((str(doc.id), task))

        # Execute new analyses
        if analysis_tasks:
            results = await asyncio.gather(
                *[task for _, task in analysis_tasks],
                return_exceptions=True
            )

            for i, (doc_id, _) in enumerate(analysis_tasks):
                result = results[i]
                if isinstance(result, Exception):
                    document_analyses[doc_id] = {
                        "error": str(result),
                        "analysis_failed": True
                    }
                else:
                    document_analyses[doc_id] = result

        return document_analyses

    async def _analyze_single_document(
        self,
        document: ProcurementDocument,
        tenant_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """
        Analyze a single document to extract structured requirements.

        Args:
            document: Document to analyze
            tenant_id: Tenant ID for isolation

        Returns:
            Analysis results for the document
        """
        # This would integrate with the AI/NLP pipeline
        # For now, we'll return a structured placeholder

        # Get document type-specific extraction logic
        doc_type = DocumentType(document.document_type) if document.document_type else None

        # Placeholder for AI extraction - would use Mistral/OpenAI here
        extracted_data = await self._extract_requirements_with_ai(
            document, doc_type, tenant_id
        )

        # Create ExtractedRequirements record for this document
        # Note: This is a simplified version - in production would integrate with actual AI

        # For now, simulate the extraction results structure
        requirements_json = {
            "technical": [req for req in extracted_data.get("requirements", []) if req.get("category") == "technical"],
            "administrative": [req for req in extracted_data.get("requirements", []) if req.get("category") == "administrative"],
            "financial": [req for req in extracted_data.get("requirements", []) if req.get("category") == "financial"]
        }

        evaluation_criteria = {
            "technical_weight": 60,
            "financial_weight": 30,
            "administrative_weight": 10,
            "criteria_details": extracted_data.get("evaluation_criteria", [])
        }

        return {
            "document_type": document.document_type,
            "filename": document.original_filename,
            "requirements": requirements_json,
            "evaluation_criteria": evaluation_criteria,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "ai_metadata": extracted_data.get("metadata", {}),
            "reused_existing": False
        }

    async def _extract_requirements_with_ai(
        self,
        document: ProcurementDocument,
        doc_type: Optional[DocumentType],
        tenant_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """
        Use AI to extract structured requirements from document.

        This is a placeholder for the actual AI integration.
        In production, this would call Mistral AI or other NLP services.
        """
        # Document type-specific extraction patterns
        extraction_patterns = {
            DocumentType.RC: {
                "focus_areas": ["submission_requirements", "evaluation_criteria", "deadlines"],
                "mandatory_sections": ["candidature", "offre_technique", "offre_financiere"]
            },
            DocumentType.CCAP: {
                "focus_areas": ["contractual_terms", "penalties", "payment_terms"],
                "mandatory_sections": ["execution", "garanties", "penalites"]
            },
            DocumentType.CCTP: {
                "focus_areas": ["technical_requirements", "performance_criteria", "deliverables"],
                "mandatory_sections": ["specifications", "livrables", "contraintes"]
            },
            DocumentType.BPU: {
                "focus_areas": ["pricing_structure", "unit_prices", "quantities"],
                "mandatory_sections": ["postes", "prix_unitaires", "quantites"]
            }
        }

        pattern = extraction_patterns.get(doc_type, {
            "focus_areas": ["general_requirements"],
            "mandatory_sections": ["requirements"]
        })

        # Simulate AI extraction results
        # In production, this would be actual AI processing
        simulated_requirements = []

        if doc_type == DocumentType.CCTP:
            simulated_requirements = [
                {
                    "category": "technical",
                    "description": "Développement d'application web responsive",
                    "importance": "high",
                    "is_mandatory": True,
                    "confidence": 0.92,
                    "source_text": "L'application devra être développée en mode responsive..."
                },
                {
                    "category": "technical",
                    "description": "Compatibilité navigateurs modernes",
                    "importance": "high",
                    "is_mandatory": True,
                    "confidence": 0.88,
                    "source_text": "Compatibilité requise avec Chrome, Firefox, Safari..."
                }
            ]
        elif doc_type == DocumentType.RC:
            simulated_requirements = [
                {
                    "category": "administrative",
                    "description": "Présentation des références clients",
                    "importance": "high",
                    "is_mandatory": True,
                    "confidence": 0.95,
                    "source_text": "Le candidat devra présenter au minimum 3 références..."
                }
            ]
        elif doc_type == DocumentType.CCAP:
            simulated_requirements = [
                {
                    "category": "administrative",
                    "description": "Conditions de paiement à 30 jours",
                    "importance": "medium",
                    "is_mandatory": True,
                    "confidence": 0.90,
                    "source_text": "Le paiement sera effectué dans un délai de 30 jours..."
                },
                {
                    "category": "financial",
                    "description": "Pénalités de retard applicables",
                    "importance": "high",
                    "is_mandatory": False,
                    "confidence": 0.85,
                    "source_text": "Des pénalités seront appliquées en cas de retard..."
                }
            ]

        return {
            "requirements": simulated_requirements,
            "metadata": {
                "extraction_method": "ai_simulation",
                "document_type": doc_type.value if doc_type else "unknown",
                "focus_areas": pattern["focus_areas"],
                "confidence_avg": 0.9
            }
        }

    async def _analyze_cross_references(
        self,
        documents: List[ProcurementDocument],
        document_analyses: Dict[str, Any],
        tenant_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """
        Analyze cross-references and relationships between documents.

        Args:
            documents: List of tender documents
            document_analyses: Individual document analyses
            tenant_id: Tenant ID for isolation

        Returns:
            Cross-reference analysis results
        """
        cross_refs = {
            "document_relationships": {},
            "requirement_overlaps": [],
            "consistency_checks": [],
            "missing_references": []
        }

        # Analyze relationships between document types
        doc_types_present = set()
        for doc in documents:
            if doc.document_type:
                doc_types_present.add(doc.document_type)

        # Expected relationships in French public procurement
        expected_relationships = {
            "rc_to_cctp": "RC should reference technical requirements in CCTP",
            "cctp_to_bpu": "CCTP deliverables should match BPU pricing structure",
            "ccap_to_all": "CCAP terms should be consistent across all documents"
        }

        # Check for requirement overlaps
        all_requirements = []
        for doc_id, analysis in document_analyses.items():
            if "requirements" in analysis:
                requirements = analysis["requirements"]
                # Handle both dict of categories and flat list
                if isinstance(requirements, dict):
                    # Requirements organized by category
                    for category, req_list in requirements.items():
                        if isinstance(req_list, list):
                            for req in req_list:
                                if isinstance(req, dict):
                                    req["source_document"] = doc_id
                                    all_requirements.append(req)
                elif isinstance(requirements, list):
                    # Flat list of requirements
                    for req in requirements:
                        if isinstance(req, dict):
                            req["source_document"] = doc_id
                            all_requirements.append(req)

        # Find similar requirements across documents
        for i, req1 in enumerate(all_requirements):
            for j, req2 in enumerate(all_requirements[i+1:], i+1):
                similarity = await self._calculate_requirement_similarity(req1, req2)
                if similarity > 0.7:  # High similarity threshold
                    cross_refs["requirement_overlaps"].append({
                        "requirement_1": req1,
                        "requirement_2": req2,
                        "similarity_score": similarity,
                        "type": "potential_duplicate" if similarity > 0.9 else "related"
                    })

        return cross_refs

    async def _calculate_requirement_similarity(
        self,
        req1: Dict[str, Any],
        req2: Dict[str, Any]
    ) -> float:
        """
        Calculate similarity between two requirements.

        This is a simplified implementation. In production,
        this would use semantic similarity models.
        """
        desc1 = req1.get("description", "").lower()
        desc2 = req2.get("description", "").lower()

        # Simple keyword overlap similarity
        words1 = set(desc1.split())
        words2 = set(desc2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    async def _consolidate_requirements(
        self,
        document_analyses: Dict[str, Any],
        cross_references: Dict[str, Any],
        tender_id: UUID,
        tenant_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """
        Consolidate requirements from all documents into global view.

        Args:
            document_analyses: Individual document analyses
            cross_references: Cross-reference analysis
            tender_id: Tender UUID
            tenant_id: Tenant ID for isolation

        Returns:
            Consolidated global requirements
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Starting consolidation for tender {tender_id}")
        logger.info(f"Document analyses: {list(document_analyses.keys())}")

        consolidated = {
            "categories": {},
            "mandatory_requirements": [],
            "optional_requirements": [],
            "requirements_by_priority": {
                "critical": [],
                "high": [],
                "medium": [],
                "low": []
            },
            "total_requirements": 0,
            "coverage_analysis": {}
        }

        # Process all requirements from all documents
        for doc_id, analysis in document_analyses.items():
            if "requirements" not in analysis or analysis.get("analysis_failed"):
                continue

            # Handle requirements as dict of categories with lists
            requirements = analysis.get("requirements", {})
            if not requirements:
                logger.info(f"No requirements for doc {doc_id}")
                continue

            logger.info(f"Processing doc {doc_id}, requirements type: {type(requirements)}")

            if isinstance(requirements, dict):
                # Requirements are grouped by category
                for category, req_list in requirements.items():
                    logger.info(f"Category {category}, req_list type: {type(req_list)}")
                    if not isinstance(req_list, list):
                        continue
                    for req in req_list:
                        if isinstance(req, dict):
                            req_category = req.get("category", category)
                            importance = req.get("importance", "medium")
                            is_mandatory = req.get("is_mandatory", False)
                            req_obj = req
                        else:
                            # Simple string requirement
                            req_category = category
                            importance = "medium"
                            is_mandatory = False
                            req_obj = {"description": str(req), "category": req_category}

                        # Add to category grouping
                        if req_category not in consolidated["categories"]:
                            consolidated["categories"][req_category] = []
                        consolidated["categories"][req_category].append(req_obj)

                        # Add to priority grouping
                        if importance in consolidated["requirements_by_priority"]:
                            consolidated["requirements_by_priority"][importance].append(req_obj)

                        # Add to mandatory/optional lists
                        if is_mandatory:
                            consolidated["mandatory_requirements"].append(req_obj)
                        else:
                            consolidated["optional_requirements"].append(req_obj)

                        consolidated["total_requirements"] += 1
            else:
                # Requirements as flat list (fallback)
                for req in requirements if isinstance(requirements, list) else []:
                    category = req.get("category", "general")
                    importance = req.get("importance", "medium")
                    is_mandatory = req.get("is_mandatory", False)

                    # Add to category grouping
                    if category not in consolidated["categories"]:
                        consolidated["categories"][category] = []
                    consolidated["categories"][category].append(req)

                    # Add to priority grouping
                    if importance in consolidated["requirements_by_priority"]:
                        consolidated["requirements_by_priority"][importance].append(req)

                    # Add to mandatory/optional lists
                    if is_mandatory:
                        consolidated["mandatory_requirements"].append(req)
                    else:
                        consolidated["optional_requirements"].append(req)

                    consolidated["total_requirements"] += 1

        # Analyze coverage by document type
        doc_type_coverage = {}
        for doc_id, analysis in document_analyses.items():
            doc_type = analysis.get("document_type", "unknown")
            req_count = len(analysis.get("requirements", []))
            doc_type_coverage[doc_type] = req_count

        consolidated["coverage_analysis"] = {
            "by_document_type": doc_type_coverage,
            "mandatory_percentage": (
                len(consolidated["mandatory_requirements"]) /
                max(consolidated["total_requirements"], 1) * 100
            ),
            "category_distribution": {
                cat: len(reqs) for cat, reqs in consolidated["categories"].items()
            }
        }

        return consolidated

    async def _generate_simplified_matches(
        self,
        global_requirements: Dict[str, Any],
        tender_id: UUID,
        tenant_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """
        Generate simplified capability matches and scoring for the tender.
        This is a simplified version that doesn't create database records.

        Args:
            global_requirements: Consolidated requirements
            tender_id: Tender UUID
            tenant_id: Tenant ID for isolation

        Returns:
            Capability matches, score, and recommendations
        """
        matches = []
        total_score = 0

        # Analyze each requirement category
        for category, requirements in global_requirements["categories"].items():
            category_score = await self._score_category_capability(
                category, requirements, tenant_id
            )

            # Create match data (not saved to DB in this simplified version)
            match_data = {
                "requirement_category": category,
                "our_capability_score": category_score["capability_score"],
                "market_competitiveness": category_score["competitiveness"],
                "risk_level": category_score["risk_level"],
                "effort_estimate": category_score["effort_estimate"],
                "confidence_score": category_score["confidence"]
            }

            matches.append(match_data)
            total_score += category_score["weighted_score"]

        # Generate overall matching score (0-100)
        overall_score = min(100, max(0, total_score))

        # Generate strategic recommendations
        recommendations = await self._generate_recommendations(
            global_requirements, matches, overall_score, tender_id, tenant_id
        )

        return {
            "matches": matches,
            "score": round(overall_score, 2),
            "recommendations": recommendations
        }

    async def _score_category_capability(
        self,
        category: str,
        requirements: List[Dict[str, Any]],
        tenant_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """
        Score our capability for a specific requirement category.

        This is a placeholder for the actual capability assessment.
        """
        # Simulate capability scoring based on category
        capability_scores = {
            "technical": {"base_score": 85, "confidence": 0.9},
            "administrative": {"base_score": 75, "confidence": 0.8},
            "financial": {"base_score": 70, "confidence": 0.85},
            "experience": {"base_score": 80, "confidence": 0.88}
        }

        base_data = capability_scores.get(category, {"base_score": 60, "confidence": 0.7})

        # Adjust based on requirement complexity
        mandatory_count = sum(1 for req in requirements if req.get("is_mandatory", False))
        complexity_factor = max(0.5, 1 - (mandatory_count * 0.05))

        capability_score = base_data["base_score"] * complexity_factor

        return {
            "capability_score": round(capability_score, 2),
            "competitiveness": "high" if capability_score > 80 else "medium" if capability_score > 60 else "low",
            "risk_level": "low" if capability_score > 80 else "medium" if capability_score > 60 else "high",
            "effort_estimate": len(requirements) * 2,  # Simplified effort estimation
            "confidence": base_data["confidence"],
            "weighted_score": capability_score * (len(requirements) / 10)
        }

    async def _generate_recommendations(
        self,
        global_requirements: Dict[str, Any],
        matches: List[Dict[str, Any]],
        overall_score: float,
        tender_id: UUID,
        tenant_id: Optional[UUID]
    ) -> List[Dict[str, Any]]:
        """
        Generate strategic recommendations for the tender.

        Args:
            global_requirements: Consolidated requirements
            matches: Capability matches
            overall_score: Overall matching score
            tender_id: Tender UUID
            tenant_id: Tenant ID for isolation

        Returns:
            List of strategic recommendations
        """
        recommendations = []

        # Overall bid recommendation
        if overall_score >= 80:
            recommendations.append({
                "type": "bid_decision",
                "priority": "high",
                "title": "Recommandation: Soumissionner",
                "description": f"Score de compatibilité élevé ({overall_score}%). Cette opportunité est alignée avec nos capacités.",
                "action_items": [
                    "Préparer une réponse complète",
                    "Mobiliser l'équipe projet",
                    "Valider les budgets et délais"
                ]
            })
        elif overall_score >= 60:
            recommendations.append({
                "type": "bid_decision",
                "priority": "medium",
                "title": "Recommandation: Évaluer attentivement",
                "description": f"Score de compatibilité modéré ({overall_score}%). Analyser les risques avant décision.",
                "action_items": [
                    "Identifier les axes d'amélioration",
                    "Évaluer la concurrence",
                    "Considérer les partenariats"
                ]
            })
        else:
            recommendations.append({
                "type": "bid_decision",
                "priority": "low",
                "title": "Recommandation: Ne pas soumissionner",
                "description": f"Score de compatibilité faible ({overall_score}%). Risques élevés pour cette opportunité.",
                "action_items": [
                    "Archiver pour référence future",
                    "Analyser les écarts de compétences",
                    "Chercher des opportunités plus adaptées"
                ]
            })

        # Specific improvement recommendations
        for match in matches:
            if match["our_capability_score"] < 70:
                recommendations.append({
                    "type": "improvement",
                    "priority": "medium",
                    "title": f"Améliorer: {match['requirement_category']}",
                    "description": f"Score faible dans la catégorie {match['requirement_category']} ({match['our_capability_score']}%)",
                    "action_items": [
                        "Identifier les compétences manquantes",
                        "Planifier des formations",
                        "Chercher des partenaires spécialisés"
                    ]
                })

        return recommendations

    async def _assess_tender_risks(
        self,
        tender: ProcurementTender,
        global_requirements: Dict[str, Any],
        tenant_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """
        Assess various risks associated with the tender.

        Args:
            tender: Tender object
            global_requirements: Consolidated requirements
            tenant_id: Tenant ID for isolation

        Returns:
            Risk assessment results
        """
        risks = {
            "overall_risk_level": "medium",
            "risk_factors": [],
            "mitigation_strategies": []
        }

        # Deadline risk
        if tender.deadline_date:
            days_to_deadline = (tender.deadline_date - datetime.now(timezone.utc)).days
            if days_to_deadline < 7:
                risks["risk_factors"].append({
                    "type": "timeline",
                    "severity": "high",
                    "description": f"Délai très court: {days_to_deadline} jours restants",
                    "impact": "Risque de réponse précipitée"
                })

        # Complexity risk
        total_mandatory = len(global_requirements.get("mandatory_requirements", []))
        if total_mandatory > 20:
            risks["risk_factors"].append({
                "type": "complexity",
                "severity": "medium",
                "description": f"Nombre élevé d'exigences obligatoires: {total_mandatory}",
                "impact": "Risque d'omission ou d'erreur"
            })

        # Budget risk (if available)
        if tender.budget_estimate and tender.budget_estimate > 1000000:
            risks["risk_factors"].append({
                "type": "financial",
                "severity": "high",
                "description": f"Budget important: {tender.budget_estimate:,.0f}€",
                "impact": "Risque financier élevé en cas d'échec"
            })

        return risks

    async def _generate_strategic_insights(
        self,
        tender: ProcurementTender,
        global_requirements: Dict[str, Any],
        matches_and_score: Dict[str, Any],
        tenant_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """
        Generate strategic insights for the tender opportunity.

        Args:
            tender: Tender object
            global_requirements: Consolidated requirements
            matches_and_score: Capability matches and scoring
            tenant_id: Tenant ID for isolation

        Returns:
            Strategic insights and market analysis
        """
        insights = {
            "market_opportunity": {},
            "competitive_position": {},
            "strategic_fit": {},
            "growth_potential": {}
        }

        # Market opportunity analysis
        category_distribution = global_requirements["coverage_analysis"].get("category_distribution", {})
        dominant_category = (
            max(category_distribution.items(), key=lambda x: x[1])[0]
            if category_distribution
            else "general"
        )

        insights["market_opportunity"] = {
            "primary_domain": dominant_category,
            "opportunity_size": "large" if tender.budget_estimate and tender.budget_estimate > 500000 else "medium",
            "client_type": tender.organization,
            "strategic_value": "high" if matches_and_score["score"] > 80 else "medium"
        }

        # Competitive positioning
        insights["competitive_position"] = {
            "our_strength_areas": [
                match["requirement_category"]
                for match in matches_and_score["matches"]
                if match["our_capability_score"] > 80
            ],
            "improvement_areas": [
                match["requirement_category"]
                for match in matches_and_score["matches"]
                if match["our_capability_score"] < 70
            ],
            "estimated_competition_level": "high" if matches_and_score["score"] > 85 else "medium"
        }

        return insights

    async def get_tender_analysis_summary(
        self,
        tender_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get existing analysis summary for a tender.

        Args:
            tender_id: Tender UUID
            tenant_id: Tenant ID for isolation

        Returns:
            Analysis summary if available, None otherwise
        """
        tender = await self.tender_repo.get_by_id(tender_id, tenant_id)
        if not tender or not tender.global_analysis:
            return None

        # Extract key summary information
        analysis = tender.global_analysis
        return {
            "tender_id": str(tender_id),
            "analysis_date": analysis.get("analysis_timestamp"),
            "matching_score": analysis.get("matching_score", 0),
            "document_count": analysis.get("document_count", 0),
            "completeness_score": analysis.get("completeness_score", 0),
            "primary_recommendation": (
                analysis.get("recommendations", [{}])[0].get("title", "Aucune recommandation")
                if analysis.get("recommendations") else "Aucune recommandation"
            ),
            "risk_level": analysis.get("risk_assessment", {}).get("overall_risk_level", "unknown"),
            "total_requirements": analysis.get("global_requirements", {}).get("total_requirements", 0),
            "status": tender.status
        }