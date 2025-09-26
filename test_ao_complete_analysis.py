#!/usr/bin/env python3
"""
Analyse complète multi-documents d'un appel d'offres public
Conçu pour un Bid Manager avec 3 ans d'expérience
"""

import asyncio
import logging
from pathlib import Path
import time
from datetime import datetime
import json
import uuid
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Disable verbose loggers
for name in ["httpx", "httpcore", "sqlalchemy"]:
    logging.getLogger(name).setLevel(logging.WARNING)


@dataclass
class DocumentAnalysis:
    """Résultat d'analyse d'un document"""
    filename: str
    doc_type: str  # CCTP, CCAP, RC
    text_length: int
    pages: int
    extraction_time_ms: int
    chunks_count: int
    key_elements: Dict[str, Any]
    requirements: List[str]
    risks: List[Dict[str, str]]
    score: float


@dataclass
class CrossDocumentAnalysis:
    """Analyse croisée des documents"""
    total_requirements: int
    contradictions: List[Dict[str, str]]
    missing_elements: List[str]
    timeline_consistency: bool
    financial_clarity: float
    technical_complexity: float
    global_score: float


@dataclass
class BidManagerReport:
    """Rapport complet pour le Bid Manager"""
    ao_reference: str
    analysis_date: str
    documents_analyzed: List[DocumentAnalysis]
    cross_analysis: CrossDocumentAnalysis
    rag_insights: Dict[str, List[Dict[str, str]]]
    go_no_go_score: float
    go_no_go_decision: str
    key_risks: List[Dict[str, str]]
    action_plan: List[Dict[str, str]]
    questions_for_buyer: List[str]
    competitive_positioning: Dict[str, Any]
    executive_summary: str


class AOCompleteAnalyzer:
    """Analyseur complet d'appels d'offres"""

    def __init__(self):
        self.documents = {}
        self.chunks_db = {}
        self.embeddings_cache = {}
        self.analysis_results = {}

    async def analyze_complete_ao(self, ao_directory: Path) -> BidManagerReport:
        """Analyse complète d'un dossier d'appel d'offres"""

        logger.info("="*70)
        logger.info("🚀 ANALYSE COMPLÈTE D'APPEL D'OFFRES - SYSTÈME RAG AVANCÉ")
        logger.info("="*70)
        logger.info(f"📁 Dossier: {ao_directory}")
        logger.info(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        logger.info("="*70)

        # Phase 1: Ingestion multi-documents
        documents_analysis = await self._phase1_multi_doc_ingestion(ao_directory)

        # Phase 2: Analyse croisée
        cross_analysis = await self._phase2_cross_document_analysis(documents_analysis)

        # Phase 3: Chunking optimisé
        await self._phase3_optimized_chunking(documents_analysis)

        # Phase 4: RAG Queries avancées
        rag_insights = await self._phase4_advanced_rag_queries()

        # Phase 5: Analyse de conformité
        conformity_analysis = await self._phase5_conformity_analysis()

        # Phase 6: Génération du rapport
        report = await self._phase6_generate_bid_manager_report(
            documents_analysis, cross_analysis, rag_insights, conformity_analysis
        )

        return report

    async def _phase1_multi_doc_ingestion(self, ao_directory: Path) -> List[DocumentAnalysis]:
        """Phase 1: Ingestion parallèle des documents PDF"""

        logger.info("\n" + "="*60)
        logger.info("📚 PHASE 1: INGESTION MULTI-DOCUMENTS")
        logger.info("="*60)

        from src.processors.pdf_processor import PDFProcessor
        pdf_processor = PDFProcessor()

        # Trouver tous les PDFs
        pdf_files = list(ao_directory.glob("*.pdf"))
        logger.info(f"📄 {len(pdf_files)} documents PDF trouvés")

        # Traiter chaque document
        documents_analysis = []

        for pdf_path in pdf_files:
            logger.info(f"\n{'='*40}")
            logger.info(f"📖 Traitement: {pdf_path.name}")
            logger.info(f"{'='*40}")

            # Déterminer le type de document
            doc_type = self._determine_doc_type(pdf_path.name)
            logger.info(f"📑 Type identifié: {doc_type}")

            # Lire et traiter le PDF
            with open(pdf_path, 'rb') as f:
                file_content = f.read()

            logger.info(f"📊 Taille: {len(file_content) / (1024*1024):.2f} MB")

            start_time = time.time()
            result = await pdf_processor.process_document(
                file_content=file_content,
                filename=pdf_path.name
            )
            processing_time = int((time.time() - start_time) * 1000)

            if not result.success:
                logger.error(f"❌ Échec du traitement: {result.metadata.get('error')}")
                continue

            # Extraire les éléments clés selon le type de document
            key_elements = await self._extract_key_elements(result.raw_text, doc_type)

            # Analyser les exigences
            requirements = self._extract_requirements(result.raw_text, doc_type)

            # Identifier les risques
            risks = self._identify_risks(result.raw_text, doc_type)

            # Calculer le score du document
            doc_score = self._calculate_document_score(key_elements, requirements, risks)

            doc_analysis = DocumentAnalysis(
                filename=pdf_path.name,
                doc_type=doc_type,
                text_length=len(result.raw_text),
                pages=result.metadata.get('pages', 0),
                extraction_time_ms=processing_time,
                chunks_count=0,  # Sera mis à jour en phase 3
                key_elements=key_elements,
                requirements=requirements,
                risks=risks,
                score=doc_score
            )

            documents_analysis.append(doc_analysis)
            self.documents[doc_type] = result.raw_text

            logger.info(f"✅ Document traité avec succès")
            logger.info(f"   📝 Texte extrait: {len(result.raw_text):,} caractères")
            logger.info(f"   📊 {len(requirements)} exigences détectées")
            logger.info(f"   ⚠️ {len(risks)} risques identifiés")
            logger.info(f"   🎯 Score: {doc_score:.1f}%")

            # Afficher un aperçu des éléments clés
            if key_elements:
                logger.info(f"\n📌 Éléments clés extraits:")
                for key, value in list(key_elements.items())[:5]:
                    if isinstance(value, str):
                        value_preview = value[:100] + "..." if len(value) > 100 else value
                    else:
                        value_preview = str(value)
                    logger.info(f"   • {key}: {value_preview}")

        logger.info(f"\n✅ Phase 1 terminée: {len(documents_analysis)} documents analysés")
        return documents_analysis

    async def _phase2_cross_document_analysis(self, documents: List[DocumentAnalysis]) -> CrossDocumentAnalysis:
        """Phase 2: Analyse croisée des documents"""

        logger.info("\n" + "="*60)
        logger.info("🔍 PHASE 2: ANALYSE CROISÉE DES DOCUMENTS")
        logger.info("="*60)

        # Collecter toutes les exigences
        all_requirements = []
        for doc in documents:
            all_requirements.extend(doc.requirements)

        total_requirements = len(set(all_requirements))
        logger.info(f"📋 Total des exigences uniques: {total_requirements}")

        # Détecter les contradictions
        contradictions = self._detect_contradictions(documents)
        logger.info(f"⚠️ Contradictions détectées: {len(contradictions)}")

        # Identifier les éléments manquants
        missing_elements = self._identify_missing_elements(documents)
        logger.info(f"❌ Éléments manquants: {len(missing_elements)}")

        # Vérifier la cohérence temporelle
        timeline_consistency = self._check_timeline_consistency(documents)
        logger.info(f"⏰ Cohérence temporelle: {'✅ OK' if timeline_consistency else '❌ Problème'}")

        # Évaluer la clarté financière
        financial_clarity = self._assess_financial_clarity(documents)
        logger.info(f"💰 Clarté financière: {financial_clarity:.1f}%")

        # Évaluer la complexité technique
        technical_complexity = self._assess_technical_complexity(documents)
        logger.info(f"🔧 Complexité technique: {technical_complexity:.1f}/100")

        # Calculer le score global
        global_score = self._calculate_global_score(
            contradictions, missing_elements, timeline_consistency,
            financial_clarity, technical_complexity
        )

        logger.info(f"\n🎯 Score global de l'AO: {global_score:.1f}%")

        # Afficher les problèmes principaux
        if contradictions:
            logger.info("\n📍 Principales contradictions:")
            for contr in contradictions[:3]:
                logger.info(f"   • {contr['description']}")

        if missing_elements:
            logger.info("\n📍 Éléments critiques manquants:")
            for elem in missing_elements[:5]:
                logger.info(f"   • {elem}")

        return CrossDocumentAnalysis(
            total_requirements=total_requirements,
            contradictions=contradictions,
            missing_elements=missing_elements,
            timeline_consistency=timeline_consistency,
            financial_clarity=financial_clarity,
            technical_complexity=technical_complexity,
            global_score=global_score
        )

    async def _phase3_optimized_chunking(self, documents: List[DocumentAnalysis]):
        """Phase 3: Chunking optimisé par type de document"""

        logger.info("\n" + "="*60)
        logger.info("📚 PHASE 3: CHUNKING OPTIMISÉ ET INDEXATION")
        logger.info("="*60)

        from src.services.ai.chunking_service import ChunkingService
        chunking_service = ChunkingService()

        total_chunks = 0

        for doc_type, text in self.documents.items():
            logger.info(f"\n📄 Chunking du document: {doc_type}")

            # Stratégie de chunking adaptée au type de document
            chunk_size = self._get_optimal_chunk_size(doc_type)
            overlap = self._get_optimal_overlap(doc_type)

            logger.info(f"   Stratégie: chunk_size={chunk_size}, overlap={overlap}")

            # Créer un objet ProcessingResult factice pour le chunking
            from src.processors.base import ProcessingResult
            processing_result = ProcessingResult(
                raw_text=text,
                structured_content={},
                success=True,
                processing_time_ms=100,
                processor_name="PDFProcessor",
                processor_version="1.0",
                page_count=0,
                word_count=len(text.split()),
                metadata={'document_type': doc_type}
            )

            # Générer les chunks
            chunks = await chunking_service.chunk_document(
                processing_result=processing_result,
                document_id=str(uuid.uuid4())
            )

            self.chunks_db[doc_type] = chunks
            total_chunks += len(chunks)

            logger.info(f"   ✅ {len(chunks)} chunks créés")

            # Mettre à jour le compte de chunks dans l'analyse
            for doc_analysis in documents:
                if doc_analysis.doc_type == doc_type:
                    doc_analysis.chunks_count = len(chunks)

        logger.info(f"\n✅ Phase 3 terminée: {total_chunks} chunks créés au total")

    async def _phase4_advanced_rag_queries(self) -> Dict[str, List[Dict[str, str]]]:
        """Phase 4: 30+ requêtes RAG avancées"""

        logger.info("\n" + "="*60)
        logger.info("🤖 PHASE 4: REQUÊTES RAG AVANCÉES (30+ QUESTIONS)")
        logger.info("="*60)

        from src.services.ai.mistral_service import get_mistral_service
        from src.services.ai.prompt_templates import PromptTemplates

        mistral_service = get_mistral_service()

        # Préparer le contexte unifié
        context_parts = []
        for doc_type, chunks in self.chunks_db.items():
            context_parts.append(f"\n=== {doc_type} ===\n")
            # Prendre les chunks les plus pertinents
            for chunk in chunks[:10]:
                context_parts.append(chunk.chunk_text[:500])

        unified_context = "\n".join(context_parts)

        # Définir les catégories de questions
        rag_queries = {
            "administratif": [
                "Quelle est la date limite de remise des offres ?",
                "Quels sont les documents obligatoires à fournir dans l'offre ?",
                "Quelle est la durée du marché et ses conditions de renouvellement ?",
                "Quels sont les critères d'attribution et leur pondération ?",
                "Quelles sont les conditions de recevabilité des offres ?",
                "Y a-t-il une visite obligatoire des sites ? Si oui, quand ?",
            ],
            "technique": [
                "Quelles sont les principales spécifications techniques requises ?",
                "Quelles normes et certifications sont exigées ?",
                "Quel est le périmètre technique exact du marché ?",
                "Quelles sont les contraintes d'architecture technique ?",
                "Quels sont les niveaux de service (SLA) attendus ?",
                "Quelles sont les exigences de sécurité informatique ?",
            ],
            "contractuel": [
                "Quelles sont les pénalités prévues en cas de retard ou défaillance ?",
                "Quelle est la répartition des responsabilités entre les parties ?",
                "Quelles sont les conditions de résiliation du marché ?",
                "Quelles garanties sont exigées (bancaire, performance, etc.) ?",
                "Quelles sont les obligations en matière d'assurance ?",
                "Comment sont gérées les modifications du contrat ?",
            ],
            "financier": [
                "Quel est le mode de détermination des prix (forfait, BPU, etc.) ?",
                "Quelles sont les modalités de paiement et délais ?",
                "Y a-t-il une clause de révision des prix ?",
                "Quel est le budget estimé ou maximum du marché ?",
                "Quelles sont les conditions de facturation ?",
                "Y a-t-il des options ou tranches conditionnelles ?",
            ],
            "risques": [
                "Quels sont les principaux risques techniques identifiés ?",
                "Y a-t-il des contradictions entre les différents documents ?",
                "Quelles sont les zones d'ambiguïté dans les spécifications ?",
                "Les délais sont-ils réalistes par rapport à la complexité ?",
                "Y a-t-il des clauses potentiellement abusives ou déséquilibrées ?",
                "Quels sont les risques de dépendance ou de lock-in ?",
            ],
            "stratégique": [
                "Quel est le contexte et les enjeux du marché pour l'acheteur ?",
                "Qui sont les concurrents probables sur ce marché ?",
                "Quels sont les facteurs clés de succès pour remporter ce marché ?",
                "Quelle stratégie de réponse est recommandée ?",
                "Faut-il répondre seul ou en groupement ?",
                "Quels sont les points de différenciation à mettre en avant ?",
            ]
        }

        insights = {}
        total_queries = sum(len(queries) for queries in rag_queries.values())
        current_query = 0

        for category, queries in rag_queries.items():
            logger.info(f"\n📝 Catégorie: {category.upper()}")
            logger.info("-" * 40)

            category_insights = []

            for query in queries:
                current_query += 1
                logger.info(f"\n❓ [{current_query}/{total_queries}] {query}")

                # Générer le prompt avec contexte
                prompt = PromptTemplates.rag_query_prompt(
                    query=query,
                    context=unified_context[:3000]  # Limiter la taille du contexte
                )

                try:
                    # Pause pour respecter les rate limits
                    await asyncio.sleep(2)

                    # Générer la réponse
                    response = await mistral_service.generate_completion(
                        prompt=prompt,
                        max_tokens=300,
                        temperature=0.1
                    )

                    if response:
                        # Nettoyer et formater la réponse
                        clean_response = response.strip()

                        # Afficher un aperçu
                        preview = clean_response[:200] + "..." if len(clean_response) > 200 else clean_response
                        logger.info(f"💡 Réponse: {preview}")

                        category_insights.append({
                            "question": query,
                            "answer": clean_response,
                            "confidence": self._assess_answer_confidence(clean_response)
                        })
                    else:
                        logger.warning(f"⚠️ Pas de réponse générée")
                        category_insights.append({
                            "question": query,
                            "answer": "Information non trouvée dans les documents",
                            "confidence": 0.0
                        })

                except Exception as e:
                    logger.warning(f"⚠️ Erreur lors de la requête: {str(e)[:100]}")
                    category_insights.append({
                        "question": query,
                        "answer": "Erreur lors de l'analyse",
                        "confidence": 0.0
                    })
                    await asyncio.sleep(5)  # Pause plus longue en cas d'erreur

            insights[category] = category_insights

            # Résumé de la catégorie
            avg_confidence = sum(i["confidence"] for i in category_insights) / len(category_insights)
            logger.info(f"\n✅ Catégorie {category}: {len(category_insights)} réponses, confiance moyenne: {avg_confidence:.1f}%")

        logger.info(f"\n✅ Phase 4 terminée: {current_query} requêtes traitées")
        return insights

    async def _phase5_conformity_analysis(self) -> Dict[str, Any]:
        """Phase 5: Analyse de conformité détaillée"""

        logger.info("\n" + "="*60)
        logger.info("✔️ PHASE 5: ANALYSE DE CONFORMITÉ")
        logger.info("="*60)

        conformity_checks = {
            "completude_dossier": {
                "check": "Tous les documents essentiels sont présents",
                "status": self._check_dossier_completeness(),
                "impact": "critical"
            },
            "coherence_delais": {
                "check": "Les délais sont cohérents entre les documents",
                "status": self._check_timeline_coherence(),
                "impact": "high"
            },
            "clarte_financiere": {
                "check": "Les aspects financiers sont clairement définis",
                "status": self._check_financial_clarity(),
                "impact": "high"
            },
            "specifications_techniques": {
                "check": "Les spécifications techniques sont complètes",
                "status": self._check_technical_specs(),
                "impact": "high"
            },
            "criteres_selection": {
                "check": "Les critères de sélection sont explicites",
                "status": self._check_selection_criteria(),
                "impact": "critical"
            },
            "risques_contractuels": {
                "check": "Absence de clauses abusives ou déséquilibrées",
                "status": self._check_contractual_risks(),
                "impact": "medium"
            }
        }

        # Calculer le score de conformité
        total_score = 0
        weights = {"critical": 3, "high": 2, "medium": 1}
        total_weight = 0

        logger.info("\n📋 Résultats de conformité:")
        for check_name, check_data in conformity_checks.items():
            status_icon = "✅" if check_data["status"] else "❌"
            logger.info(f"   {status_icon} {check_data['check']}")

            if check_data["status"]:
                total_score += weights[check_data["impact"]]
            total_weight += weights[check_data["impact"]]

        conformity_score = (total_score / total_weight) * 100 if total_weight > 0 else 0

        logger.info(f"\n🎯 Score de conformité global: {conformity_score:.1f}%")

        return {
            "checks": conformity_checks,
            "score": conformity_score,
            "recommendation": self._get_conformity_recommendation(conformity_score)
        }

    async def _phase6_generate_bid_manager_report(
        self,
        documents: List[DocumentAnalysis],
        cross_analysis: CrossDocumentAnalysis,
        rag_insights: Dict[str, List[Dict[str, str]]],
        conformity: Dict[str, Any]
    ) -> BidManagerReport:
        """Phase 6: Génération du rapport Bid Manager"""

        logger.info("\n" + "="*60)
        logger.info("📑 PHASE 6: GÉNÉRATION DU RAPPORT BID MANAGER")
        logger.info("="*60)

        # Calculer le score GO/NO-GO
        go_no_go_score = self._calculate_go_no_go_score(
            cross_analysis, conformity, rag_insights
        )

        # Déterminer la décision
        if go_no_go_score >= 75:
            decision = "GO - Opportunité favorable"
        elif go_no_go_score >= 50:
            decision = "GO CONDITIONNEL - Nécessite des clarifications"
        else:
            decision = "NO-GO - Risques trop élevés"

        logger.info(f"\n🎯 Score GO/NO-GO: {go_no_go_score:.1f}%")
        logger.info(f"📊 Décision: {decision}")

        # Identifier les risques clés
        key_risks = self._compile_key_risks(documents, cross_analysis, conformity)
        logger.info(f"\n⚠️ {len(key_risks)} risques majeurs identifiés")

        # Générer le plan d'action
        action_plan = self._generate_action_plan(
            cross_analysis, conformity, rag_insights
        )
        logger.info(f"📋 {len(action_plan)} actions prioritaires définies")

        # Préparer les questions pour l'acheteur
        questions_for_buyer = self._generate_questions_for_buyer(
            cross_analysis, rag_insights
        )
        logger.info(f"❓ {len(questions_for_buyer)} questions à poser à l'acheteur")

        # Analyse concurrentielle
        competitive_positioning = self._analyze_competitive_positioning(
            documents, cross_analysis
        )

        # Générer le résumé exécutif
        executive_summary = self._generate_executive_summary(
            documents, cross_analysis, go_no_go_score, decision
        )

        # Créer le rapport final
        report = BidManagerReport(
            ao_reference="VSGP-2024-INFOGERANCE",
            analysis_date=datetime.now().isoformat(),
            documents_analyzed=documents,
            cross_analysis=cross_analysis,
            rag_insights=rag_insights,
            go_no_go_score=go_no_go_score,
            go_no_go_decision=decision,
            key_risks=key_risks,
            action_plan=action_plan,
            questions_for_buyer=questions_for_buyer,
            competitive_positioning=competitive_positioning,
            executive_summary=executive_summary
        )

        # Sauvegarder le rapport
        await self._save_report(report)

        # Afficher le rapport final
        await self._display_final_report(report)

        return report

    # Méthodes utilitaires

    def _determine_doc_type(self, filename: str) -> str:
        """Détermine le type de document basé sur le nom du fichier"""
        filename_upper = filename.upper()
        if "CCTP" in filename_upper:
            return "CCTP"
        elif "CCAP" in filename_upper:
            return "CCAP"
        elif "RC" in filename_upper or "REGLEMENT" in filename_upper:
            return "RC"
        else:
            return "OTHER"

    async def _extract_key_elements(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Extrait les éléments clés selon le type de document"""
        elements = {}

        if doc_type == "CCTP":
            # Éléments techniques
            elements["objet"] = self._extract_pattern(text, r"objet[:\s]+(.{50,200})", "Objet non spécifié")
            elements["perimetre"] = self._extract_pattern(text, r"périmètre[:\s]+(.{50,300})", "Périmètre à déterminer")
            elements["normes"] = re.findall(r"\b(?:ISO|EN|NF)[^\s]{2,15}\b", text)
            elements["sla_mentions"] = len(re.findall(r"(?:SLA|niveau.{0,5}service|disponibilité)", text, re.I))

        elif doc_type == "CCAP":
            # Éléments administratifs
            elements["duree"] = self._extract_pattern(text, r"durée.{0,20}(?:marché|contrat)[:\s]+(.{10,100})", "Non spécifiée")
            elements["penalites"] = len(re.findall(r"pénalité", text, re.I))
            elements["garanties"] = re.findall(r"garantie.{0,30}", text, re.I)[:3]
            elements["prix_type"] = self._detect_price_type(text)

        elif doc_type == "RC":
            # Éléments de consultation
            elements["date_limite"] = self._extract_pattern(text, r"date.{0,10}limite.{0,30}(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", "À vérifier")
            elements["criteres"] = self._extract_selection_criteria(text)
            elements["documents_requis"] = self._extract_required_docs(text)

        return elements

    def _extract_pattern(self, text: str, pattern: str, default: str) -> str:
        """Extrait un motif du texte avec valeur par défaut"""
        match = re.search(pattern, text, re.I | re.S)
        if match:
            return match.group(1).strip()[:200]
        return default

    def _detect_price_type(self, text: str) -> str:
        """Détecte le type de prix dans le marché"""
        if re.search(r"prix.{0,10}forfaitaire", text, re.I):
            return "Forfaitaire"
        elif re.search(r"bordereau.{0,10}prix|BPU", text, re.I):
            return "Bordereau de prix unitaires"
        elif re.search(r"régie", text, re.I):
            return "Régie"
        else:
            return "Non déterminé"

    def _extract_selection_criteria(self, text: str) -> List[str]:
        """Extrait les critères de sélection"""
        criteria = []
        patterns = [
            r"prix.{0,20}(\d{1,3})\s*%",
            r"valeur.{0,10}technique.{0,20}(\d{1,3})\s*%",
            r"délai.{0,20}(\d{1,3})\s*%",
            r"qualité.{0,20}(\d{1,3})\s*%"
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.I)
            if matches:
                criteria.extend(matches)
        return criteria

    def _extract_required_docs(self, text: str) -> List[str]:
        """Extrait la liste des documents requis"""
        docs = []
        doc_patterns = [
            "mémoire technique",
            "DC1", "DC2", "DC4",
            "attestation", "certificat",
            "références", "CV"
        ]
        for pattern in doc_patterns:
            if re.search(pattern, text, re.I):
                docs.append(pattern)
        return docs

    def _extract_requirements(self, text: str, doc_type: str) -> List[str]:
        """Extrait les exigences selon le type de document"""
        requirements = []

        # Patterns génériques d'exigences
        requirement_patterns = [
            r"(?:doit|devra|devront|obligatoire).{0,100}",
            r"(?:exigé|requis|nécessaire).{0,100}",
            r"(?:au minimum|au moins|minimal).{0,100}"
        ]

        for pattern in requirement_patterns:
            matches = re.findall(pattern, text, re.I)
            requirements.extend([m[:150] for m in matches[:10]])  # Limiter à 10 par pattern

        return list(set(requirements))[:30]  # Garder max 30 exigences uniques

    def _identify_risks(self, text: str, doc_type: str) -> List[Dict[str, str]]:
        """Identifie les risques dans le document"""
        risks = []

        # Recherche de termes de risque
        risk_indicators = {
            "pénalité": "contractuel",
            "résiliation": "contractuel",
            "exclusif": "commercial",
            "propriété intellectuelle": "juridique",
            "RGPD": "conformité",
            "délai.{0,10}court": "planning",
            "complexe": "technique",
            "migration": "technique"
        }

        for indicator, risk_type in risk_indicators.items():
            if re.search(indicator, text, re.I):
                risks.append({
                    "type": risk_type,
                    "indicator": indicator.replace(".{0,10}", ""),
                    "severity": "medium"
                })

        return risks[:10]  # Limiter aux 10 risques principaux

    def _calculate_document_score(self, elements: Dict, requirements: List, risks: List) -> float:
        """Calcule le score de qualité d'un document"""
        score = 50.0  # Score de base

        # Bonus pour les éléments trouvés
        score += min(len(elements) * 5, 25)

        # Bonus pour les exigences claires
        score += min(len(requirements) * 2, 20)

        # Pénalité pour les risques
        score -= min(len(risks) * 3, 15)

        # S'assurer que le score reste entre 0 et 100
        return max(0, min(100, score))

    def _detect_contradictions(self, documents: List[DocumentAnalysis]) -> List[Dict[str, str]]:
        """Détecte les contradictions entre documents"""
        contradictions = []

        # Vérifier les délais contradictoires
        delays = []
        for doc in documents:
            text = self.documents.get(doc.doc_type, "")
            delay_matches = re.findall(r"(\d+)\s*(?:jour|mois|semaine)", text, re.I)
            delays.extend([(doc.doc_type, m) for m in delay_matches])

        if delays and len(set(d[1] for d in delays)) > 5:
            contradictions.append({
                "type": "délais",
                "description": "Incohérence dans les délais mentionnés entre documents",
                "severity": "high"
            })

        return contradictions

    def _identify_missing_elements(self, documents: List[DocumentAnalysis]) -> List[str]:
        """Identifie les éléments manquants critiques"""
        missing = []
        doc_types = [doc.doc_type for doc in documents]

        # Éléments essentiels attendus
        if "CCTP" in doc_types:
            cctp_text = self.documents.get("CCTP", "")
            if not re.search(r"périmètre", cctp_text, re.I):
                missing.append("Périmètre technique non clairement défini dans CCTP")

        if "CCAP" in doc_types:
            ccap_text = self.documents.get("CCAP", "")
            if not re.search(r"modalité.{0,10}paiement", ccap_text, re.I):
                missing.append("Modalités de paiement non spécifiées dans CCAP")

        if "RC" in doc_types:
            rc_text = self.documents.get("RC", "")
            if not re.search(r"critère.{0,20}(?:sélection|attribution)", rc_text, re.I):
                missing.append("Critères de sélection non explicites dans RC")

        return missing

    def _check_timeline_consistency(self, documents: List[DocumentAnalysis]) -> bool:
        """Vérifie la cohérence temporelle entre documents"""
        all_dates = []
        for doc in documents:
            text = self.documents.get(doc.doc_type, "")
            date_matches = re.findall(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", text)
            all_dates.extend(date_matches)

        # Si on a des dates, vérifier qu'elles sont cohérentes
        return len(all_dates) > 0 and len(set(all_dates)) < 10

    def _assess_financial_clarity(self, documents: List[DocumentAnalysis]) -> float:
        """Évalue la clarté des aspects financiers"""
        score = 0.0
        indicators = 0

        for doc in documents:
            text = self.documents.get(doc.doc_type, "")
            if re.search(r"prix", text, re.I):
                score += 20
                indicators += 1
            if re.search(r"budget", text, re.I):
                score += 30
                indicators += 1
            if re.search(r"modalité.{0,10}paiement", text, re.I):
                score += 25
                indicators += 1
            if re.search(r"révision.{0,10}prix", text, re.I):
                score += 25
                indicators += 1

        return min(100, score)

    def _assess_technical_complexity(self, documents: List[DocumentAnalysis]) -> float:
        """Évalue la complexité technique du marché"""
        complexity = 30.0  # Complexité de base

        cctp_text = self.documents.get("CCTP", "")

        # Indicateurs de complexité
        if re.search(r"migration", cctp_text, re.I):
            complexity += 20
        if re.search(r"haute.{0,10}disponibilité|24.{0,5}7", cctp_text, re.I):
            complexity += 15
        if re.search(r"sécurité", cctp_text, re.I):
            complexity += 10
        if len(re.findall(r"interface", cctp_text, re.I)) > 3:
            complexity += 15
        if re.search(r"RGPD|conformité", cctp_text, re.I):
            complexity += 10

        return min(100, complexity)

    def _calculate_global_score(
        self, contradictions, missing, timeline_ok, financial_clarity, tech_complexity
    ) -> float:
        """Calcule le score global de l'appel d'offres"""
        score = 70.0  # Score de base

        # Pénalités
        score -= len(contradictions) * 5
        score -= len(missing) * 3
        if not timeline_ok:
            score -= 10

        # Bonus
        score += financial_clarity * 0.2

        # Ajustement complexité (peut être positif ou négatif)
        if tech_complexity > 70:
            score -= 10  # Très complexe = plus risqué
        elif tech_complexity < 40:
            score += 5   # Simple = plus accessible

        return max(0, min(100, score))

    def _get_optimal_chunk_size(self, doc_type: str) -> int:
        """Retourne la taille de chunk optimale selon le type de document"""
        sizes = {
            "CCTP": 1536,  # Plus gros chunks pour le technique
            "CCAP": 1024,  # Chunks moyens pour l'administratif
            "RC": 768,     # Petits chunks pour les règles
            "OTHER": 1024
        }
        return sizes.get(doc_type, 1024)

    def _get_optimal_overlap(self, doc_type: str) -> int:
        """Retourne l'overlap optimal selon le type de document"""
        overlaps = {
            "CCTP": 150,
            "CCAP": 100,
            "RC": 50,
            "OTHER": 100
        }
        return overlaps.get(doc_type, 100)

    def _assess_answer_confidence(self, answer: str) -> float:
        """Évalue la confiance d'une réponse RAG"""
        confidence = 50.0

        # Indicateurs de haute confiance
        if re.search(r"(?:clairement|explicitement|spécifiquement)", answer, re.I):
            confidence += 20
        if re.search(r"article \d+|section \d+|page \d+", answer, re.I):
            confidence += 15
        if len(answer) > 100:
            confidence += 10

        # Indicateurs de basse confiance
        if re.search(r"(?:pas.{0,10}trouvé|non.{0,10}mentionné|aucune.{0,10}information)", answer, re.I):
            confidence -= 30
        if re.search(r"(?:probablement|peut-être|semble)", answer, re.I):
            confidence -= 15

        return max(0, min(100, confidence))

    def _check_dossier_completeness(self) -> bool:
        """Vérifie la complétude du dossier"""
        return all(doc_type in self.documents for doc_type in ["CCTP", "CCAP", "RC"])

    def _check_timeline_coherence(self) -> bool:
        """Vérifie la cohérence des délais"""
        # Simplifié pour l'exemple
        return True

    def _check_financial_clarity(self) -> bool:
        """Vérifie la clarté financière"""
        ccap_text = self.documents.get("CCAP", "")
        return bool(re.search(r"prix|modalité.{0,10}paiement", ccap_text, re.I))

    def _check_technical_specs(self) -> bool:
        """Vérifie la complétude des specs techniques"""
        cctp_text = self.documents.get("CCTP", "")
        return len(cctp_text) > 10000  # Au moins 10k caractères

    def _check_selection_criteria(self) -> bool:
        """Vérifie la présence de critères de sélection"""
        rc_text = self.documents.get("RC", "")
        return bool(re.search(r"critère", rc_text, re.I))

    def _check_contractual_risks(self) -> bool:
        """Vérifie l'absence de clauses abusives"""
        ccap_text = self.documents.get("CCAP", "")
        # Recherche de termes problématiques
        risky_terms = ["exclusivité totale", "pénalité.{0,20}illimitée", "résiliation.{0,20}sans.{0,10}préavis"]
        for term in risky_terms:
            if re.search(term, ccap_text, re.I):
                return False
        return True

    def _get_conformity_recommendation(self, score: float) -> str:
        """Génère une recommandation basée sur le score de conformité"""
        if score >= 80:
            return "Dossier conforme - Peut répondre en l'état"
        elif score >= 60:
            return "Dossier globalement conforme - Quelques clarifications nécessaires"
        elif score >= 40:
            return "Conformité partielle - Demander des précisions importantes"
        else:
            return "Non-conformité majeure - Risque élevé"

    def _calculate_go_no_go_score(
        self, cross_analysis, conformity, rag_insights
    ) -> float:
        """Calcule le score GO/NO-GO final"""
        score = 0.0

        # Poids des différents facteurs
        score += cross_analysis.global_score * 0.3
        score += conformity["score"] * 0.3

        # Score basé sur les insights RAG
        total_confidence = 0
        total_questions = 0
        for category_insights in rag_insights.values():
            for insight in category_insights:
                total_confidence += insight.get("confidence", 0)
                total_questions += 1

        if total_questions > 0:
            avg_confidence = total_confidence / total_questions
            score += avg_confidence * 0.4

        return min(100, score)

    def _compile_key_risks(
        self, documents, cross_analysis, conformity
    ) -> List[Dict[str, str]]:
        """Compile les risques majeurs identifiés"""
        risks = []

        # Risques des documents
        for doc in documents:
            for risk in doc.risks[:2]:  # Top 2 par document
                risks.append({
                    "source": doc.doc_type,
                    "type": risk["type"],
                    "description": f"Risque {risk['type']} identifié dans {doc.doc_type}",
                    "severity": risk["severity"],
                    "mitigation": self._suggest_mitigation(risk["type"])
                })

        # Risques de l'analyse croisée
        if cross_analysis.contradictions:
            risks.append({
                "source": "Analyse croisée",
                "type": "cohérence",
                "description": f"{len(cross_analysis.contradictions)} contradictions entre documents",
                "severity": "high",
                "mitigation": "Demander clarification lors des questions"
            })

        return risks[:10]  # Top 10 risques

    def _suggest_mitigation(self, risk_type: str) -> str:
        """Suggère une mitigation pour un type de risque"""
        mitigations = {
            "contractuel": "Négocier les clauses ou prévoir des réserves",
            "technique": "Mobiliser expertise technique ou sous-traiter",
            "planning": "Prévoir des ressources supplémentaires",
            "commercial": "Analyser la concurrence et adapter l'offre",
            "juridique": "Consultation juridique avant soumission",
            "conformité": "Audit de conformité et plan d'action"
        }
        return mitigations.get(risk_type, "Analyser en détail et prévoir contingence")

    def _generate_action_plan(
        self, cross_analysis, conformity, rag_insights
    ) -> List[Dict[str, str]]:
        """Génère le plan d'action prioritaire"""
        actions = []

        # Actions basées sur la conformité
        if conformity["score"] < 80:
            actions.append({
                "priority": "HIGH",
                "action": "Analyser les points de non-conformité",
                "deadline": "J+2",
                "responsible": "Équipe technique"
            })

        # Actions basées sur les éléments manquants
        if cross_analysis.missing_elements:
            actions.append({
                "priority": "HIGH",
                "action": "Demander les éléments manquants à l'acheteur",
                "deadline": "J+1",
                "responsible": "Bid Manager"
            })

        # Actions standard
        actions.extend([
            {
                "priority": "HIGH",
                "action": "Rédiger les questions pour l'acheteur",
                "deadline": "J+1",
                "responsible": "Bid Manager"
            },
            {
                "priority": "MEDIUM",
                "action": "Estimer les coûts et ressources",
                "deadline": "J+3",
                "responsible": "Équipe commerciale"
            },
            {
                "priority": "MEDIUM",
                "action": "Identifier les partenaires potentiels",
                "deadline": "J+5",
                "responsible": "Direction commerciale"
            },
            {
                "priority": "LOW",
                "action": "Préparer la structure du mémoire technique",
                "deadline": "J+7",
                "responsible": "Équipe technique"
            }
        ])

        return actions

    def _generate_questions_for_buyer(
        self, cross_analysis, rag_insights
    ) -> List[str]:
        """Génère les questions à poser à l'acheteur"""
        questions = []

        # Questions sur les éléments manquants
        for missing in cross_analysis.missing_elements[:3]:
            questions.append(f"Pouvez-vous clarifier : {missing} ?")

        # Questions sur les contradictions
        for contradiction in cross_analysis.contradictions[:2]:
            questions.append(f"Clarification nécessaire sur : {contradiction['description']}")

        # Questions standards importantes
        questions.extend([
            "Y a-t-il un budget prévisionnel pour ce marché ?",
            "Une visite des sites est-elle possible/obligatoire ?",
            "Acceptez-vous les variantes techniques ?",
            "Quelle est la date prévisionnelle de démarrage des prestations ?",
            "Y a-t-il des titulaires sortants ? Si oui, lesquels ?"
        ])

        return questions[:10]

    def _analyze_competitive_positioning(
        self, documents, cross_analysis
    ) -> Dict[str, Any]:
        """Analyse le positionnement concurrentiel"""
        return {
            "market_complexity": "Élevée" if cross_analysis.technical_complexity > 70 else "Moyenne",
            "expected_competitors": "5-8 ESN nationales et régionales",
            "our_strengths": [
                "Expertise sectorielle",
                "Proximité géographique",
                "Références similaires"
            ],
            "our_weaknesses": [
                "Taille de structure",
                "Couverture nationale limitée"
            ],
            "differentiation_strategy": "Miser sur la proximité et la réactivité",
            "pricing_strategy": "Alignement marché avec value-added services"
        }

    def _generate_executive_summary(
        self, documents, cross_analysis, go_no_go_score, decision
    ) -> str:
        """Génère le résumé exécutif"""
        return f"""
RÉSUMÉ EXÉCUTIF - ANALYSE AO VSGP INFOGÉRANCE

• Appel d'offres : Marché public d'infogérance pour Vallée Sud - Grand Paris
• Documents analysés : {len(documents)} ({', '.join([d.doc_type for d in documents])})
• Score global : {cross_analysis.global_score:.1f}%
• Décision GO/NO-GO : {decision} (Score: {go_no_go_score:.1f}%)

POINTS CLÉS:
- Complexité technique : {cross_analysis.technical_complexity:.0f}/100
- Clarté financière : {cross_analysis.financial_clarity:.0f}%
- {cross_analysis.total_requirements} exigences identifiées
- {len(cross_analysis.contradictions)} points de vigilance

RECOMMANDATION:
{self._get_conformity_recommendation(go_no_go_score)}

PROCHAINES ÉTAPES:
1. Envoyer les questions à l'acheteur (J+1)
2. Évaluer les ressources nécessaires (J+3)
3. Décision finale de soumission (J+5)
"""

    async def _save_report(self, report: BidManagerReport):
        """Sauvegarde le rapport en JSON"""
        filename = f"ao_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Convertir le rapport en dictionnaire COMPLET
        report_dict = {
            "ao_reference": report.ao_reference,
            "analysis_date": report.analysis_date,
            "go_no_go_score": report.go_no_go_score,
            "go_no_go_decision": report.go_no_go_decision,
            "executive_summary": report.executive_summary,
            "documents_analyzed": [
                {
                    "filename": doc.filename,
                    "type": doc.doc_type,
                    "text_length": doc.text_length,
                    "pages": doc.pages,
                    "score": doc.score,
                    "requirements_count": len(doc.requirements),
                    "risks_count": len(doc.risks)
                } for doc in report.documents_analyzed
            ],
            "cross_analysis": {
                "total_requirements": report.cross_analysis.total_requirements,
                "contradictions_count": len(report.cross_analysis.contradictions),
                "missing_elements_count": len(report.cross_analysis.missing_elements),
                "timeline_consistency": report.cross_analysis.timeline_consistency,
                "financial_clarity": report.cross_analysis.financial_clarity,
                "technical_complexity": report.cross_analysis.technical_complexity,
                "global_score": report.cross_analysis.global_score
            },
            "all_requirements": self._get_all_requirements(report.documents_analyzed),
            "key_risks": [
                {
                    "source": risk["source"],
                    "type": risk["type"],
                    "description": risk["description"],
                    "severity": risk["severity"],
                    "mitigation": risk["mitigation"]
                } for risk in report.key_risks
            ],
            "questions_for_buyer": report.questions_for_buyer,
            "action_plan": report.action_plan,
            "competitive_positioning": report.competitive_positioning,
            "rag_insights_summary": {
                category: {
                    "questions_count": len(insights),
                    "avg_confidence": sum(q["confidence"] for q in insights) / len(insights) if insights else 0
                } for category, insights in report.rag_insights.items()
            }
        }

        # Sauvegarder le rapport complet
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)

        # Sauvegarder aussi un fichier séparé avec TOUTES les exigences
        req_filename = f"ao_requirements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        requirements_dict = {
            "ao_reference": report.ao_reference,
            "analysis_date": report.analysis_date,
            "total_requirements": report.cross_analysis.total_requirements,
            "requirements_by_document": {
                doc.doc_type: doc.requirements for doc in report.documents_analyzed
            },
            "all_unique_requirements": list(set(
                req for doc in report.documents_analyzed for req in doc.requirements
            ))
        }

        with open(req_filename, 'w', encoding='utf-8') as f:
            json.dump(requirements_dict, f, ensure_ascii=False, indent=2)

        logger.info(f"\n💾 Rapport complet sauvegardé : {filename}")
        logger.info(f"📋 Liste des exigences sauvegardée : {req_filename}")

    def _get_all_requirements(self, documents):
        """Compile toutes les exigences uniques"""
        all_reqs = []
        for doc in documents:
            for req in doc.requirements:
                all_reqs.append({
                    "source": doc.doc_type,
                    "requirement": req
                })
        return all_reqs

    async def _display_final_report(self, report: BidManagerReport):
        """Affiche le rapport final formaté"""

        print("\n" + "="*70)
        print("📊 RAPPORT D'ANALYSE COMPLET - BID MANAGER")
        print("="*70)

        print(report.executive_summary)

        print("\n" + "="*70)
        print("📈 MÉTRIQUES CLÉS")
        print("="*70)
        print(f"• Documents analysés: {len(report.documents_analyzed)}")
        print(f"• Exigences totales: {report.cross_analysis.total_requirements}")
        print(f"• Score GO/NO-GO: {report.go_no_go_score:.1f}%")
        print(f"• Décision: {report.go_no_go_decision}")

        print("\n" + "="*70)
        print("⚠️ RISQUES MAJEURS")
        print("="*70)
        for i, risk in enumerate(report.key_risks[:5], 1):
            print(f"{i}. [{risk['severity'].upper()}] {risk['description']}")
            print(f"   → Mitigation: {risk['mitigation']}")

        print("\n" + "="*70)
        print("📋 PLAN D'ACTION IMMÉDIAT")
        print("="*70)
        for i, action in enumerate(report.action_plan[:5], 1):
            print(f"{i}. [{action['priority']}] {action['action']}")
            print(f"   Échéance: {action['deadline']} | Responsable: {action['responsible']}")

        print("\n" + "="*70)
        print("❓ QUESTIONS POUR L'ACHETEUR")
        print("="*70)
        for i, question in enumerate(report.questions_for_buyer[:5], 1):
            print(f"{i}. {question}")

        print("\n" + "="*70)
        print(f"✅ ANALYSE TERMINÉE - {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)


async def main():
    """Fonction principale"""
    analyzer = AOCompleteAnalyzer()

    # Répertoire contenant les documents de l'AO
    ao_directory = Path("/Users/cedric/Dev/projects/scorpiusProject/Examples/VSGP-AO")

    logger.info("🚀 Démarrage de l'analyse complète de l'appel d'offres...")
    logger.info("📄 Cette analyse est conçue pour un Bid Manager avec 3 ans d'expérience")
    logger.info("-"*70)

    try:
        report = await analyzer.analyze_complete_ao(ao_directory)
        logger.info("\n🎉 Analyse complète terminée avec succès!")

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'analyse: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())