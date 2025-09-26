#!/usr/bin/env python3
"""
Test complet d'analyse de conformité technique CCTP.

Ce script implémente le plan de test complet pour valider:
- L'extraction des exigences techniques
- La détection des normes et standards
- L'analyse de conformité réglementaire
- Le pipeline RAG pour questions techniques
- La génération de rapports de conformité
"""

import asyncio
import logging
import time
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import uuid

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
class ConformityTestResult:
    """Structure pour stocker les résultats de test."""
    phase: str
    test_name: str
    success: bool
    score: float
    duration_ms: int
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


@dataclass
class ConformityReport:
    """Rapport de conformité technique."""
    document_id: str
    document_name: str
    analysis_date: datetime
    global_score: float
    requirements_detected: int
    standards_found: List[str]
    temporal_constraints: Dict[str, Any]
    compliance_issues: List[Dict[str, Any]]
    recommendations: List[str]
    test_results: List[ConformityTestResult]


class CCTPConformityAnalyzer:
    """Analyseur de conformité technique pour CCTP."""

    def __init__(self):
        """Initialize the analyzer."""
        self.test_results = []
        self.document_path = Path("/Users/cedric/Dev/projects/scorpiusProject/Examples/VSGP-AO/CCTP.pdf")

        # Questions de test organisées par catégorie
        self.test_queries = {
            "normes": [
                "Quelles sont toutes les normes techniques mentionnées dans le document ?",
                "Quelles normes ISO sont requises pour ce marché ?",
                "Y a-t-il des normes de sécurité électrique à respecter ?",
                "Les équipements doivent-ils être certifiés CE ?",
                "Quelles sont les normes environnementales applicables ?"
            ],
            "specifications": [
                "Quelles sont les principales spécifications techniques du projet ?",
                "Quelles sont les performances minimales requises ?",
                "Quels matériaux sont spécifiquement mentionnés ?",
                "Quelles sont les contraintes d'intégration technique ?",
                "Y a-t-il des exigences de compatibilité spécifiques ?"
            ],
            "delais": [
                "Quel est le délai global d'exécution du marché ?",
                "Quels sont les jalons intermédiaires à respecter ?",
                "Y a-t-il des pénalités de retard prévues ?",
                "Quelle est la date de livraison finale ?",
                "Existe-t-il des contraintes de planning spécifiques ?"
            ],
            "livrables": [
                "Quels documents techniques sont à fournir ?",
                "Quel format est attendu pour les plans et schémas ?",
                "Combien d'exemplaires de la documentation sont requis ?",
                "Quelle documentation de maintenance est demandée ?",
                "Quels sont les livrables de formation prévus ?"
            ],
            "complexes": [
                "Y a-t-il des contradictions entre les différentes sections du CCTP ?",
                "Les délais sont-ils cohérents avec la complexité technique décrite ?",
                "Toutes les normes citées sont-elles compatibles entre elles ?",
                "Quels sont les principaux risques techniques identifiables ?",
                "Quelles clarifications seraient nécessaires avant de répondre ?"
            ]
        }

        # Patterns de détection pour l'extraction
        self.patterns = {
            "normes": [
                r"(?:norme?s?|standard?s?)\s+(?:ISO|NF|EN|CE|DTU|AFNOR)\s*[\d\-\.]+",
                r"ISO\s*\d{3,5}(?:[-:]\d{4})?",
                r"NF\s*[A-Z]\s*\d{2}-\d{3}",
                r"EN\s*\d{3,5}",
                r"DTU\s*\d{1,2}(?:\.\d{1,2})?",
                r"marquage\s+CE",
                r"certification\s+(?:ISO|NF|CE)"
            ],
            "delais": [
                r"\d+\s*(?:jours?|mois|semaines?|années?)\s*(?:ouvrés?|calendaires?)?",
                r"délai\s+(?:de?|d')\s*(?:livraison|exécution|réalisation)",
                r"date\s+(?:limite|butoir|finale)",
                r"pénalité(?:s)?\s+de\s+retard",
                r"planning\s+(?:prévisionnel|détaillé)",
                r"phase\s+\d+",
                r"jalon\s+(?:n°)?\d+"
            ],
            "montants": [
                r"€\s*[\d\s,]+(?:\.\d{2})?",
                r"[\d\s,]+(?:\.\d{2})?\s*€",
                r"euros?\s+HT",
                r"montant\s+(?:minimum|maximum|estimé)"
            ],
            "livrables": [
                r"(?:document|dossier|rapport|plan|schéma)s?\s+(?:technique|de\s+maintenance|d'exécution)",
                r"manuel\s+(?:utilisateur|d'exploitation|de\s+maintenance)",
                r"(?:formation|support)\s+(?:utilisateur|technique)",
                r"PV\s+de\s+(?:réception|recette|validation)"
            ]
        }

    async def analyze_with_services(self):
        """Analyse using the actual services."""
        from src.processors.pdf_processor import PDFProcessor
        from src.services.ai.mistral_service import get_mistral_service
        from src.services.ai.chunking_service import ChunkingService
        from src.services.ai.prompt_templates import PromptTemplates

        self.pdf_processor = PDFProcessor()
        self.mistral_service = get_mistral_service()
        self.chunking_service = ChunkingService()
        self.prompt_templates = PromptTemplates

        return await self.run_full_test_suite()

    async def phase1_document_processing(self) -> ConformityTestResult:
        """Phase 1: Test du processing et de l'extraction PDF."""
        logger.info("\n" + "="*60)
        logger.info("📄 PHASE 1: PROCESSING DU DOCUMENT CCTP")
        logger.info("="*60)

        start_time = time.time()

        try:
            # Chargement du document
            logger.info(f"📂 Chargement: {self.document_path.name}")

            with open(self.document_path, 'rb') as f:
                file_content = f.read()

            file_size_mb = len(file_content) / (1024 * 1024)
            logger.info(f"   Taille: {file_size_mb:.2f} MB")

            # Processing PDF
            logger.info("⚙️ Extraction du contenu PDF...")
            result = await self.pdf_processor.process_document(
                file_content=file_content,
                filename=self.document_path.name
            )

            if not result.success:
                raise Exception(f"Échec du processing: {result.metadata.get('error')}")

            # Stockage du résultat pour les phases suivantes
            self.processing_result = result
            self.raw_text = result.raw_text

            # Métriques d'extraction
            duration_ms = int((time.time() - start_time) * 1000)
            pages = result.metadata.get('pages', 0)
            text_length = len(result.raw_text)

            logger.info(f"✅ Extraction réussie")
            logger.info(f"   Pages: {pages}")
            logger.info(f"   Caractères extraits: {text_length:,}")
            logger.info(f"   Temps: {duration_ms}ms")

            # Analyse de la structure
            has_tables = "tableau" in result.raw_text.lower() or "|" in result.raw_text
            has_lists = bool(re.search(r'\n\s*[-•]\s+', result.raw_text))
            has_sections = bool(re.search(r'\n\s*\d+\.\s+[A-Z]', result.raw_text))

            logger.info(f"📊 Structure détectée:")
            logger.info(f"   Tableaux: {'✓' if has_tables else '✗'}")
            logger.info(f"   Listes: {'✓' if has_lists else '✗'}")
            logger.info(f"   Sections numérotées: {'✓' if has_sections else '✗'}")

            return ConformityTestResult(
                phase="Phase 1",
                test_name="Document Processing",
                success=True,
                score=100.0,
                duration_ms=duration_ms,
                details={
                    "pages": pages,
                    "text_length": text_length,
                    "file_size_mb": file_size_mb,
                    "has_tables": has_tables,
                    "has_lists": has_lists,
                    "has_sections": has_sections
                }
            )

        except Exception as e:
            logger.error(f"❌ Erreur Phase 1: {str(e)}")
            return ConformityTestResult(
                phase="Phase 1",
                test_name="Document Processing",
                success=False,
                score=0.0,
                duration_ms=int((time.time() - start_time) * 1000),
                errors=[str(e)]
            )

    async def phase2_requirements_extraction(self) -> ConformityTestResult:
        """Phase 2: Test de l'extraction des exigences."""
        logger.info("\n" + "="*60)
        logger.info("🔍 PHASE 2: EXTRACTION DES EXIGENCES TECHNIQUES")
        logger.info("="*60)

        start_time = time.time()

        try:
            # Extraction des normes
            logger.info("📋 Recherche des normes et standards...")
            normes_found = []

            for pattern in self.patterns["normes"]:
                matches = re.findall(pattern, self.raw_text, re.IGNORECASE)
                normes_found.extend(matches)

            # Dédupliquer et nettoyer
            normes_found = list(set([n.strip() for n in normes_found]))
            logger.info(f"   {len(normes_found)} normes détectées")

            if normes_found:
                logger.info("   Échantillon:")
                for norme in normes_found[:5]:
                    logger.info(f"     • {norme}")

            # Extraction des délais
            logger.info("\n⏰ Recherche des contraintes temporelles...")
            delais_found = []

            for pattern in self.patterns["delais"]:
                matches = re.findall(pattern, self.raw_text, re.IGNORECASE)
                delais_found.extend(matches)

            logger.info(f"   {len(delais_found)} contraintes temporelles détectées")

            # Extraction des livrables
            logger.info("\n📦 Recherche des livrables...")
            livrables_found = []

            for pattern in self.patterns["livrables"]:
                matches = re.findall(pattern, self.raw_text, re.IGNORECASE)
                livrables_found.extend(matches)

            livrables_found = list(set([l.strip() for l in livrables_found]))
            logger.info(f"   {len(livrables_found)} types de livrables détectés")

            # Calcul du score
            total_requirements = len(normes_found) + len(delais_found) + len(livrables_found)
            score = min(100, (total_requirements / 30) * 100)  # Objectif: 30+ exigences

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(f"\n📊 Résumé de l'extraction:")
            logger.info(f"   Total exigences: {total_requirements}")
            logger.info(f"   Score: {score:.1f}%")
            logger.info(f"   Temps: {duration_ms}ms")

            # Stockage pour les phases suivantes
            self.extracted_requirements = {
                "normes": normes_found,
                "delais": delais_found,
                "livrables": livrables_found
            }

            return ConformityTestResult(
                phase="Phase 2",
                test_name="Requirements Extraction",
                success=True,
                score=score,
                duration_ms=duration_ms,
                details={
                    "normes_count": len(normes_found),
                    "delais_count": len(delais_found),
                    "livrables_count": len(livrables_found),
                    "total_requirements": total_requirements,
                    "sample_normes": normes_found[:5],
                    "sample_delais": delais_found[:5],
                    "sample_livrables": livrables_found[:5]
                }
            )

        except Exception as e:
            logger.error(f"❌ Erreur Phase 2: {str(e)}")
            return ConformityTestResult(
                phase="Phase 2",
                test_name="Requirements Extraction",
                success=False,
                score=0.0,
                duration_ms=int((time.time() - start_time) * 1000),
                errors=[str(e)]
            )

    async def phase3_chunking_and_indexing(self) -> ConformityTestResult:
        """Phase 3: Test du chunking et de l'indexation."""
        logger.info("\n" + "="*60)
        logger.info("📚 PHASE 3: CHUNKING ET INDEXATION")
        logger.info("="*60)

        start_time = time.time()

        try:
            # Création des chunks
            logger.info("📄 Création des chunks...")
            document_id = str(uuid.uuid4())

            chunks = await self.chunking_service.chunk_document(
                processing_result=self.processing_result,
                document_id=document_id
            )

            logger.info(f"   {len(chunks)} chunks créés")

            # Analyse des chunks
            chunk_sizes = [chunk.chunk_size for chunk in chunks]
            avg_size = sum(chunk_sizes) / len(chunk_sizes) if chunks else 0
            min_size = min(chunk_sizes) if chunks else 0
            max_size = max(chunk_sizes) if chunks else 0

            logger.info(f"📊 Statistiques des chunks:")
            logger.info(f"   Taille moyenne: {avg_size:.0f} caractères")
            logger.info(f"   Taille min: {min_size} caractères")
            logger.info(f"   Taille max: {max_size} caractères")

            # Test d'overlap
            if len(chunks) > 1:
                overlap_detected = False
                for i in range(len(chunks) - 1):
                    if chunks[i].chunk_text[-50:] in chunks[i+1].chunk_text:
                        overlap_detected = True
                        break
                logger.info(f"   Overlap détecté: {'✓' if overlap_detected else '✗'}")

            # Test des métadonnées
            chunks_with_page = sum(1 for c in chunks if c.page_number is not None)
            chunks_with_section = sum(1 for c in chunks if c.section_type is not None)

            logger.info(f"📋 Métadonnées des chunks:")
            logger.info(f"   Avec numéro de page: {chunks_with_page}/{len(chunks)}")
            logger.info(f"   Avec type de section: {chunks_with_section}/{len(chunks)}")

            # Génération d'embeddings pour quelques chunks (test)
            logger.info("\n🧮 Test de génération d'embeddings...")
            test_texts = [chunk.chunk_text for chunk in chunks[:3]]

            embeddings = await self.mistral_service.generate_embeddings_batch(
                test_texts,
                batch_size=3,
                show_progress=False
            )

            logger.info(f"   {len(embeddings)} embeddings générés")
            logger.info(f"   Dimension: {len(embeddings[0]) if embeddings else 0}")

            # Stockage pour les phases suivantes
            self.chunks = chunks

            # Calcul du score
            score = 100.0
            if avg_size < 300 or avg_size > 1500:
                score -= 20  # Pénalité pour taille non optimale
            if chunks_with_page < len(chunks) * 0.8:
                score -= 10  # Pénalité pour métadonnées manquantes

            duration_ms = int((time.time() - start_time) * 1000)

            return ConformityTestResult(
                phase="Phase 3",
                test_name="Chunking and Indexing",
                success=True,
                score=score,
                duration_ms=duration_ms,
                details={
                    "chunks_count": len(chunks),
                    "avg_chunk_size": avg_size,
                    "min_chunk_size": min_size,
                    "max_chunk_size": max_size,
                    "chunks_with_page": chunks_with_page,
                    "chunks_with_section": chunks_with_section,
                    "embeddings_tested": len(embeddings) if 'embeddings' in locals() else 0
                }
            )

        except Exception as e:
            logger.error(f"❌ Erreur Phase 3: {str(e)}")
            return ConformityTestResult(
                phase="Phase 3",
                test_name="Chunking and Indexing",
                success=False,
                score=0.0,
                duration_ms=int((time.time() - start_time) * 1000),
                errors=[str(e)]
            )

    async def phase4_rag_technical_queries(self) -> ConformityTestResult:
        """Phase 4: Test des requêtes RAG techniques."""
        logger.info("\n" + "="*60)
        logger.info("🤖 PHASE 4: REQUÊTES RAG TECHNIQUES")
        logger.info("="*60)

        start_time = time.time()
        results_details = []

        try:
            # Préparation du contexte
            context = "\n\n".join([chunk.chunk_text for chunk in self.chunks[:10]])

            successful_queries = 0
            total_queries = 0
            avg_response_time = []

            for category, queries in self.test_queries.items():
                logger.info(f"\n📝 Catégorie: {category.upper()}")
                logger.info("-" * 40)

                for query in queries[:2]:  # Test 2 queries per category
                    total_queries += 1
                    query_start = time.time()

                    logger.info(f"\n❓ Question: {query}")

                    try:
                        # Générer le prompt
                        prompt = self.prompt_templates.procurement_analysis_prompt(
                            query=query,
                            context=context,
                            document_type="CCTP"
                        )

                        # Appel à Mistral avec retry
                        await asyncio.sleep(2)  # Rate limiting

                        response = await self.mistral_service.generate_completion(
                            prompt=prompt,
                            max_tokens=300,
                            temperature=0.1
                        )

                        query_time = (time.time() - query_start) * 1000
                        avg_response_time.append(query_time)

                        if response:
                            successful_queries += 1
                            response_preview = response[:200].strip()
                            logger.info(f"💡 Réponse: {response_preview}...")
                            logger.info(f"⏱️ Temps: {query_time:.0f}ms")

                            results_details.append({
                                "category": category,
                                "query": query,
                                "response_length": len(response),
                                "response_time_ms": query_time,
                                "success": True
                            })
                        else:
                            logger.warning(f"⚠️ Pas de réponse générée")
                            results_details.append({
                                "category": category,
                                "query": query,
                                "success": False
                            })

                    except Exception as e:
                        logger.warning(f"⚠️ Erreur query: {str(e)[:100]}")
                        results_details.append({
                            "category": category,
                            "query": query,
                            "success": False,
                            "error": str(e)[:100]
                        })
                        await asyncio.sleep(5)  # Pause en cas d'erreur

            # Calcul des métriques
            success_rate = (successful_queries / total_queries * 100) if total_queries > 0 else 0
            avg_time = sum(avg_response_time) / len(avg_response_time) if avg_response_time else 0

            logger.info(f"\n📊 Résumé des requêtes RAG:")
            logger.info(f"   Requêtes testées: {total_queries}")
            logger.info(f"   Requêtes réussies: {successful_queries}")
            logger.info(f"   Taux de succès: {success_rate:.1f}%")
            logger.info(f"   Temps moyen: {avg_time:.0f}ms")

            duration_ms = int((time.time() - start_time) * 1000)

            return ConformityTestResult(
                phase="Phase 4",
                test_name="RAG Technical Queries",
                success=success_rate >= 70,
                score=success_rate,
                duration_ms=duration_ms,
                details={
                    "total_queries": total_queries,
                    "successful_queries": successful_queries,
                    "success_rate": success_rate,
                    "avg_response_time_ms": avg_time,
                    "queries_details": results_details
                }
            )

        except Exception as e:
            logger.error(f"❌ Erreur Phase 4: {str(e)}")
            return ConformityTestResult(
                phase="Phase 4",
                test_name="RAG Technical Queries",
                success=False,
                score=0.0,
                duration_ms=int((time.time() - start_time) * 1000),
                errors=[str(e)]
            )

    async def phase5_conformity_analysis(self) -> ConformityTestResult:
        """Phase 5: Analyse de conformité et détection d'anomalies."""
        logger.info("\n" + "="*60)
        logger.info("🔎 PHASE 5: ANALYSE DE CONFORMITÉ")
        logger.info("="*60)

        start_time = time.time()

        try:
            conformity_issues = []
            recommendations = []

            # Vérification des normes obsolètes
            logger.info("📋 Vérification des normes...")
            obsolete_patterns = [
                r"ISO\s*9001:2008",  # Remplacée par ISO 9001:2015
                r"EN\s*50160:1999",  # Versions obsolètes
            ]

            for pattern in obsolete_patterns:
                if re.search(pattern, self.raw_text, re.IGNORECASE):
                    issue = f"Norme obsolète détectée: {pattern}"
                    conformity_issues.append({
                        "type": "norme_obsolete",
                        "severity": "major",
                        "description": issue
                    })
                    logger.warning(f"   ⚠️ {issue}")

            # Vérification de la complétude
            logger.info("\n✅ Vérification de complétude...")
            required_sections = [
                ("objet", r"(?:objet|but|objectif)\s+du\s+marché"),
                ("delais", r"délai[s]?\s+d'exécution"),
                ("penalites", r"pénalité[s]?"),
                ("reception", r"(?:réception|recette|validation)"),
                ("garantie", r"garantie[s]?")
            ]

            missing_sections = []
            for section_name, pattern in required_sections:
                if not re.search(pattern, self.raw_text, re.IGNORECASE):
                    missing_sections.append(section_name)
                    conformity_issues.append({
                        "type": "section_manquante",
                        "severity": "minor",
                        "description": f"Section '{section_name}' non trouvée"
                    })

            if missing_sections:
                logger.warning(f"   ⚠️ Sections manquantes: {', '.join(missing_sections)}")
                recommendations.append(
                    f"Demander des clarifications sur: {', '.join(missing_sections)}"
                )
            else:
                logger.info(f"   ✅ Toutes les sections requises sont présentes")

            # Analyse de cohérence des délais
            logger.info("\n⏰ Analyse de cohérence temporelle...")
            delai_matches = re.findall(r"(\d+)\s*(jours?|mois|semaines?)", self.raw_text, re.IGNORECASE)

            if delai_matches:
                delais_jours = []
                for valeur, unite in delai_matches:
                    val = int(valeur)
                    if "mois" in unite.lower():
                        val = val * 30
                    elif "semaine" in unite.lower():
                        val = val * 7
                    delais_jours.append(val)

                if delais_jours:
                    min_delai = min(delais_jours)
                    max_delai = max(delais_jours)

                    if max_delai > min_delai * 10:
                        conformity_issues.append({
                            "type": "incoherence_delais",
                            "severity": "warning",
                            "description": f"Grande variation de délais: {min_delai} à {max_delai} jours"
                        })
                        recommendations.append(
                            "Vérifier la cohérence des délais mentionnés dans le document"
                        )

            # Génération de recommandations supplémentaires
            if len(self.extracted_requirements["normes"]) > 10:
                recommendations.append(
                    "Nombreuses normes requises: prévoir une revue technique approfondie"
                )

            if not self.extracted_requirements["livrables"]:
                recommendations.append(
                    "Clarifier la liste exacte des livrables attendus"
                )

            # Calcul du score de conformité
            base_score = 100
            for issue in conformity_issues:
                if issue["severity"] == "major":
                    base_score -= 15
                elif issue["severity"] == "warning":
                    base_score -= 10
                elif issue["severity"] == "minor":
                    base_score -= 5

            conformity_score = max(0, base_score)

            logger.info(f"\n📊 Résumé de conformité:")
            logger.info(f"   Score de conformité: {conformity_score}%")
            logger.info(f"   Problèmes détectés: {len(conformity_issues)}")
            logger.info(f"   Recommandations: {len(recommendations)}")

            # Stockage pour le rapport final
            self.conformity_issues = conformity_issues
            self.recommendations = recommendations

            duration_ms = int((time.time() - start_time) * 1000)

            return ConformityTestResult(
                phase="Phase 5",
                test_name="Conformity Analysis",
                success=True,
                score=conformity_score,
                duration_ms=duration_ms,
                details={
                    "issues_count": len(conformity_issues),
                    "major_issues": sum(1 for i in conformity_issues if i["severity"] == "major"),
                    "warnings": sum(1 for i in conformity_issues if i["severity"] == "warning"),
                    "minor_issues": sum(1 for i in conformity_issues if i["severity"] == "minor"),
                    "recommendations_count": len(recommendations),
                    "conformity_issues": conformity_issues[:5],  # Sample
                    "recommendations": recommendations
                }
            )

        except Exception as e:
            logger.error(f"❌ Erreur Phase 5: {str(e)}")
            return ConformityTestResult(
                phase="Phase 5",
                test_name="Conformity Analysis",
                success=False,
                score=0.0,
                duration_ms=int((time.time() - start_time) * 1000),
                errors=[str(e)]
            )

    async def phase6_performance_metrics(self) -> ConformityTestResult:
        """Phase 6: Métriques de performance."""
        logger.info("\n" + "="*60)
        logger.info("⚡ PHASE 6: MÉTRIQUES DE PERFORMANCE")
        logger.info("="*60)

        start_time = time.time()

        try:
            # Compilation des métriques de toutes les phases
            total_duration = sum(r.duration_ms for r in self.test_results)
            avg_score = sum(r.score for r in self.test_results) / len(self.test_results) if self.test_results else 0

            # Métriques spécifiques
            processing_speed = len(self.raw_text) / (self.test_results[0].duration_ms / 1000) if self.test_results else 0
            chunks_per_second = len(self.chunks) / (self.test_results[2].duration_ms / 1000) if len(self.test_results) > 2 else 0

            # Test de cache
            logger.info("💾 Test du cache d'embeddings...")
            test_text = self.chunks[0].chunk_text if self.chunks else "Test text"

            # Premier appel (miss cache)
            cache_test_start = time.time()
            await self.mistral_service.generate_embeddings_batch([test_text], show_progress=False)
            first_call_time = (time.time() - cache_test_start) * 1000

            # Second appel (hit cache)
            cache_test_start = time.time()
            await self.mistral_service.generate_embeddings_batch([test_text], show_progress=False)
            second_call_time = (time.time() - cache_test_start) * 1000

            cache_speedup = first_call_time / second_call_time if second_call_time > 0 else 1

            # Statistiques d'utilisation
            usage_stats = self.mistral_service.get_usage_stats()

            logger.info(f"\n📊 Métriques globales:")
            logger.info(f"   Durée totale: {total_duration}ms ({total_duration/1000:.2f}s)")
            logger.info(f"   Score moyen: {avg_score:.1f}%")
            logger.info(f"   Vitesse processing: {processing_speed:.0f} chars/s")
            logger.info(f"   Vitesse chunking: {chunks_per_second:.1f} chunks/s")
            logger.info(f"   Cache speedup: {cache_speedup:.1f}x")

            logger.info(f"\n💰 Utilisation API:")
            logger.info(f"   Requêtes totales: {usage_stats['total_requests']}")
            logger.info(f"   Hits cache: {usage_stats['cache_saves']}")
            logger.info(f"   Coût estimé: ${usage_stats['total_cost_usd']:.4f}")
            logger.info(f"   Économies cache: ${usage_stats['estimated_savings_usd']:.4f}")

            # Validation des objectifs de performance
            performance_targets_met = {
                "processing_time": total_duration < 30000,  # < 30s
                "cache_effective": cache_speedup > 2,  # 2x speedup minimum
                "score_threshold": avg_score > 70,  # 70% minimum
                "api_efficiency": usage_stats['cache_saves'] > 0  # Au moins quelques hits cache
            }

            targets_met = sum(performance_targets_met.values())
            total_targets = len(performance_targets_met)
            performance_score = (targets_met / total_targets) * 100

            logger.info(f"\n🎯 Objectifs de performance:")
            for target, met in performance_targets_met.items():
                status = "✅" if met else "❌"
                logger.info(f"   {status} {target}")

            duration_ms = int((time.time() - start_time) * 1000)

            return ConformityTestResult(
                phase="Phase 6",
                test_name="Performance Metrics",
                success=performance_score >= 75,
                score=performance_score,
                duration_ms=duration_ms,
                details={
                    "total_test_duration_ms": total_duration,
                    "avg_test_score": avg_score,
                    "processing_speed_chars_per_sec": processing_speed,
                    "chunks_per_second": chunks_per_second,
                    "cache_speedup": cache_speedup,
                    "api_requests": usage_stats['total_requests'],
                    "cache_hits": usage_stats['cache_saves'],
                    "cost_usd": usage_stats['total_cost_usd'],
                    "performance_targets_met": targets_met,
                    "performance_targets_total": total_targets
                }
            )

        except Exception as e:
            logger.error(f"❌ Erreur Phase 6: {str(e)}")
            return ConformityTestResult(
                phase="Phase 6",
                test_name="Performance Metrics",
                success=False,
                score=0.0,
                duration_ms=int((time.time() - start_time) * 1000),
                errors=[str(e)]
            )

    def generate_conformity_report(self) -> ConformityReport:
        """Génère le rapport de conformité final."""
        logger.info("\n" + "="*60)
        logger.info("📑 GÉNÉRATION DU RAPPORT DE CONFORMITÉ")
        logger.info("="*60)

        # Calcul du score global
        global_score = sum(r.score for r in self.test_results) / len(self.test_results) if self.test_results else 0

        # Compilation des standards trouvés
        standards = self.extracted_requirements.get("normes", []) if hasattr(self, 'extracted_requirements') else []

        # Contraintes temporelles
        temporal_constraints = {
            "delais": self.extracted_requirements.get("delais", [])[:5] if hasattr(self, 'extracted_requirements') else [],
            "count": len(self.extracted_requirements.get("delais", [])) if hasattr(self, 'extracted_requirements') else 0
        }

        report = ConformityReport(
            document_id=str(uuid.uuid4()),
            document_name=self.document_path.name,
            analysis_date=datetime.now(),
            global_score=global_score,
            requirements_detected=len(self.extracted_requirements.get("normes", [])) +
                                len(self.extracted_requirements.get("delais", [])) +
                                len(self.extracted_requirements.get("livrables", []))
                                if hasattr(self, 'extracted_requirements') else 0,
            standards_found=standards[:10],  # Top 10 standards
            temporal_constraints=temporal_constraints,
            compliance_issues=getattr(self, 'conformity_issues', []),
            recommendations=getattr(self, 'recommendations', []),
            test_results=self.test_results
        )

        return report

    def print_final_report(self, report: ConformityReport):
        """Affiche le rapport final formaté."""
        logger.info("\n" + "="*70)
        logger.info(" "*20 + "📊 RAPPORT FINAL D'ANALYSE DE CONFORMITÉ")
        logger.info("="*70)

        logger.info(f"\n📄 Document: {report.document_name}")
        logger.info(f"📅 Date d'analyse: {report.analysis_date.strftime('%Y-%m-%d %H:%M')}")
        logger.info(f"🎯 Score global: {report.global_score:.1f}%")

        # Résumé des phases
        logger.info(f"\n📈 Résultats par phase:")
        logger.info("-" * 50)
        for result in report.test_results:
            status = "✅" if result.success else "❌"
            logger.info(f"{status} {result.phase} - {result.test_name}: {result.score:.1f}%")

        # Exigences détectées
        logger.info(f"\n📋 Exigences détectées: {report.requirements_detected}")
        if report.standards_found:
            logger.info(f"   Normes principales:")
            for std in report.standards_found[:5]:
                logger.info(f"     • {std}")

        # Problèmes de conformité
        if report.compliance_issues:
            logger.info(f"\n⚠️ Problèmes de conformité: {len(report.compliance_issues)}")
            for issue in report.compliance_issues[:3]:
                severity_icon = "🔴" if issue["severity"] == "major" else "🟡" if issue["severity"] == "warning" else "🔵"
                logger.info(f"   {severity_icon} [{issue['severity'].upper()}] {issue['description']}")

        # Recommandations
        if report.recommendations:
            logger.info(f"\n💡 Recommandations principales:")
            for i, rec in enumerate(report.recommendations[:3], 1):
                logger.info(f"   {i}. {rec}")

        # Métriques de performance
        perf_result = next((r for r in report.test_results if r.test_name == "Performance Metrics"), None)
        if perf_result and perf_result.details:
            logger.info(f"\n⚡ Métriques de performance:")
            logger.info(f"   • Temps total d'analyse: {perf_result.details.get('total_test_duration_ms', 0)/1000:.2f}s")
            logger.info(f"   • Vitesse de traitement: {perf_result.details.get('processing_speed_chars_per_sec', 0):.0f} chars/s")
            logger.info(f"   • Cache speedup: {perf_result.details.get('cache_speedup', 1):.1f}x")
            logger.info(f"   • Coût API: ${perf_result.details.get('cost_usd', 0):.4f}")

        # Conclusion
        logger.info("\n" + "="*70)
        if report.global_score >= 85:
            logger.info("✅ EXCELLENTE CONFORMITÉ - Document bien structuré et complet")
        elif report.global_score >= 70:
            logger.info("✅ BONNE CONFORMITÉ - Quelques clarifications nécessaires")
        elif report.global_score >= 50:
            logger.info("⚠️ CONFORMITÉ MOYENNE - Plusieurs points à clarifier")
        else:
            logger.info("❌ CONFORMITÉ FAIBLE - Révision importante nécessaire")
        logger.info("="*70)

    async def run_full_test_suite(self):
        """Exécute la suite complète de tests."""
        logger.info("\n" + "="*70)
        logger.info(" "*15 + "🚀 DÉMARRAGE DU TEST DE CONFORMITÉ TECHNIQUE CCTP")
        logger.info("="*70)
        logger.info(f"📄 Document: {self.document_path.name}")
        logger.info(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        logger.info("="*70)

        # Exécution séquentielle des phases
        phases = [
            self.phase1_document_processing,
            self.phase2_requirements_extraction,
            self.phase3_chunking_and_indexing,
            self.phase4_rag_technical_queries,
            self.phase5_conformity_analysis,
            self.phase6_performance_metrics
        ]

        for phase_func in phases:
            result = await phase_func()
            self.test_results.append(result)

            # Arrêt si phase critique échoue
            if not result.success and result.phase in ["Phase 1", "Phase 3"]:
                logger.error(f"❌ Arrêt du test: {result.phase} a échoué")
                break

        # Génération du rapport final
        report = self.generate_conformity_report()
        self.print_final_report(report)

        return report


async def main():
    """Point d'entrée principal."""
    analyzer = CCTPConformityAnalyzer()

    try:
        report = await analyzer.analyze_with_services()

        # Export optionnel en JSON
        report_dict = {
            "document_name": report.document_name,
            "analysis_date": report.analysis_date.isoformat(),
            "global_score": report.global_score,
            "requirements_detected": report.requirements_detected,
            "standards_found": report.standards_found,
            "compliance_issues": report.compliance_issues,
            "recommendations": report.recommendations,
            "test_results": [
                {
                    "phase": r.phase,
                    "test_name": r.test_name,
                    "success": r.success,
                    "score": r.score,
                    "duration_ms": r.duration_ms
                }
                for r in report.test_results
            ]
        }

        # Sauvegarde du rapport
        report_path = Path(f"conformity_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"\n💾 Rapport sauvegardé: {report_path}")

    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}", exc_info=True)
        return False

    return True


if __name__ == "__main__":
    asyncio.run(main())