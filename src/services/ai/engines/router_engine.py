"""Router query engine for adaptive query processing."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
import re

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.ai.engines.simple_query_engine import SimpleQueryEngine, QueryResult
from src.services.ai.engines.subquestion_engine import SubQuestionQueryEngine
from src.services.ai.mistral_service import get_mistral_service
from src.core.ai_config import ai_config

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Types of queries the router can handle."""
    SIMPLE = "simple"  # Direct factual questions
    COMPLEX = "complex"  # Multi-part questions
    COMPARISON = "comparison"  # Comparing multiple items
    AGGREGATION = "aggregation"  # Counting, listing, summarizing
    PROCEDURAL = "procedural"  # How-to, step-by-step
    ANALYTICAL = "analytical"  # Analysis, interpretation
    TEMPORAL = "temporal"  # Time-based queries
    COMPLIANCE = "compliance"  # Regulatory compliance checks


class RouterQueryEngine:
    """
    Query engine that routes queries to appropriate specialized engines.

    This engine:
    1. Classifies incoming queries
    2. Routes to the best engine for that query type
    3. Can chain multiple engines for complex needs
    4. Provides adaptive query processing
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize Router query engine.

        Args:
            db: Database session
        """
        self.db = db
        self.simple_engine = SimpleQueryEngine(db)
        self.subquestion_engine = SubQuestionQueryEngine(db)
        self.mistral_service = get_mistral_service()

        # Query type patterns for classification
        self._init_patterns()

    def _init_patterns(self):
        """Initialize pattern matchers for query classification."""
        self.patterns = {
            QueryType.SIMPLE: [
                r"qu'est[- ]ce que",
                r"définition",
                r"signifie",
                r"^quel(?:le)?\s+(?:est|sont)",
                r"^où\s+",
                r"^quand\s+"
            ],
            QueryType.COMPARISON: [
                r"compar\w+",
                r"différence",
                r"versus",
                r"contre",
                r"meilleur",
                r"préfér\w+",
                r"avantage",
                r"inconvénient"
            ],
            QueryType.AGGREGATION: [
                r"combien",
                r"liste[rz]?",
                r"énumér\w+",
                r"tous?\s+les",
                r"chaque",
                r"résume[rz]?",
                r"synthèse"
            ],
            QueryType.PROCEDURAL: [
                r"comment",
                r"étapes?",
                r"procédure",
                r"processus",
                r"méthode",
                r"façon de",
                r"manière de"
            ],
            QueryType.ANALYTICAL: [
                r"analys\w+",
                r"évaluer",
                r"interpréter",
                r"expliquer pourquoi",
                r"raisons?",
                r"causes?",
                r"conséquences?"
            ],
            QueryType.TEMPORAL: [
                r"quand",
                r"délai",
                r"date",
                r"période",
                r"avant",
                r"après",
                r"pendant",
                r"historique",
                r"évolution"
            ],
            QueryType.COMPLIANCE: [
                r"conforme",
                r"conformité",
                r"réglementaire",
                r"légal",
                r"obligation",
                r"doit",
                r"requis",
                r"norme",
                r"standard"
            ]
        }

    async def query(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        force_engine: Optional[str] = None,
        enable_chaining: bool = True
    ) -> QueryResult:
        """
        Route and execute query through appropriate engine.

        Args:
            query_text: Query text
            top_k: Number of results
            filters: Search filters
            force_engine: Force specific engine ("simple", "subquestion")
            enable_chaining: Allow chaining multiple engines

        Returns:
            QueryResult from appropriate engine
        """
        start_time = datetime.utcnow()

        try:
            # Step 1: Classify query if engine not forced
            if force_engine:
                query_type = QueryType.SIMPLE if force_engine == "simple" else QueryType.COMPLEX
                logger.info(f"Forced engine: {force_engine}")
            else:
                logger.info(f"Classifying query: {query_text[:50]}...")
                query_type = await self._classify_query(query_text)
                logger.info(f"Query classified as: {query_type}")

            # Step 2: Route to appropriate engine
            result = await self._route_query(
                query_text=query_text,
                query_type=query_type,
                top_k=top_k,
                filters=filters,
                enable_chaining=enable_chaining
            )

            # Add routing metadata
            result.metadata["router"] = {
                "query_type": query_type,
                "engine_used": self._get_engine_for_type(query_type),
                "chaining_enabled": enable_chaining,
                "processing_time_ms": int(
                    (datetime.utcnow() - start_time).total_seconds() * 1000
                )
            }

            logger.info(f"Router query completed using {query_type} strategy")
            return result

        except Exception as e:
            logger.error(f"Router query failed: {e}")
            # Fall back to simple query
            return await self.simple_engine.query(
                query_text=query_text,
                top_k=top_k,
                filters=filters
            )

    async def _classify_query(self, query_text: str) -> QueryType:
        """
        Classify query into a type.

        Args:
            query_text: Query to classify

        Returns:
            QueryType classification
        """
        query_lower = query_text.lower()

        # Pattern-based classification
        pattern_scores = {}

        for query_type, patterns in self.patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    score += 1

            if score > 0:
                pattern_scores[query_type] = score

        # If clear pattern match, use it
        if pattern_scores:
            best_type = max(pattern_scores, key=pattern_scores.get)
            if pattern_scores[best_type] >= 2:  # Strong signal
                return best_type

        # Use LLM for more nuanced classification
        classification = await self._llm_classify(query_text)

        # Combine pattern and LLM classification
        if classification in pattern_scores:
            # Both agree
            return classification
        elif pattern_scores:
            # Trust pattern if LLM unsure
            return max(pattern_scores, key=pattern_scores.get)
        else:
            # Trust LLM
            return classification

    async def _llm_classify(self, query_text: str) -> QueryType:
        """
        Use LLM to classify query.

        Args:
            query_text: Query to classify

        Returns:
            QueryType classification
        """
        system_prompt = """Tu es un expert en classification de questions sur les marchés publics.

        Classifie la question dans l'une de ces catégories:
        - simple: Questions factuelles directes
        - complex: Questions multi-parties nécessitant décomposition
        - comparison: Comparaisons entre éléments
        - aggregation: Comptage, listes, résumés
        - procedural: Comment faire, procédures
        - analytical: Analyse, interprétation
        - temporal: Questions liées au temps
        - compliance: Conformité réglementaire

        Réponds UNIQUEMENT avec le nom de la catégorie."""

        user_prompt = f"Classifie cette question: {query_text}"

        # Get classification
        response = await self.mistral_service.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=20
        )

        # Parse response
        response_lower = response.lower().strip()

        # Map to QueryType
        for query_type in QueryType:
            if query_type.value in response_lower:
                return query_type

        # Default to COMPLEX if unclear
        return QueryType.COMPLEX

    async def _route_query(
        self,
        query_text: str,
        query_type: QueryType,
        top_k: Optional[int],
        filters: Optional[Dict[str, Any]],
        enable_chaining: bool
    ) -> QueryResult:
        """
        Route query to appropriate engine based on type.

        Args:
            query_text: Query text
            query_type: Classified query type
            top_k: Number of results
            filters: Search filters
            enable_chaining: Allow chaining

        Returns:
            QueryResult from appropriate engine
        """
        # Simple routing logic - can be extended
        if query_type in [QueryType.SIMPLE, QueryType.TEMPORAL]:
            # Use simple engine for straightforward queries
            return await self.simple_engine.query(
                query_text=query_text,
                top_k=top_k,
                filters=filters,
                use_hybrid=query_type == QueryType.TEMPORAL
            )

        elif query_type in [QueryType.COMPLEX, QueryType.COMPARISON, QueryType.ANALYTICAL]:
            # Use sub-question engine for complex queries
            return await self.subquestion_engine.query(
                query_text=query_text,
                top_k=top_k,
                filters=filters,
                max_subquestions=5 if query_type == QueryType.COMPLEX else 3
            )

        elif query_type == QueryType.AGGREGATION:
            # Use specialized aggregation logic
            return await self._handle_aggregation_query(
                query_text=query_text,
                top_k=top_k or 10,  # More results for aggregation
                filters=filters
            )

        elif query_type == QueryType.PROCEDURAL:
            # Use step-by-step processing
            return await self._handle_procedural_query(
                query_text=query_text,
                top_k=top_k,
                filters=filters
            )

        elif query_type == QueryType.COMPLIANCE:
            # Use compliance checking logic
            return await self._handle_compliance_query(
                query_text=query_text,
                top_k=top_k,
                filters=filters
            )

        else:
            # Default to sub-question engine
            return await self.subquestion_engine.query(
                query_text=query_text,
                top_k=top_k,
                filters=filters
            )

    async def _handle_aggregation_query(
        self,
        query_text: str,
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> QueryResult:
        """
        Handle aggregation queries (lists, counts, summaries).

        Args:
            query_text: Query text
            top_k: Number of results
            filters: Search filters

        Returns:
            QueryResult with aggregated data
        """
        # Get more results for aggregation
        result = await self.simple_engine.query(
            query_text=query_text,
            top_k=top_k,
            filters=filters,
            use_hybrid=True
        )

        # Post-process for better aggregation
        if result.sources:
            # Enhance answer with structured list
            system_prompt = """Tu es un expert en synthèse d'informations.

            Organise la réponse sous forme de liste structurée ou de tableau récapitulatif.

            Règles:
            1. Utilise des puces ou numérotation
            2. Groupe les éléments similaires
            3. Sois exhaustif mais concis
            4. Cite les sources
            """

            user_prompt = f"""Question: {query_text}

Informations disponibles:
{result.answer}

Reformule en liste structurée ou tableau."""

            enhanced_answer = await self.mistral_service.generate_completion(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1
            )

            result.answer = enhanced_answer

        return result

    async def _handle_procedural_query(
        self,
        query_text: str,
        top_k: Optional[int],
        filters: Optional[Dict[str, Any]]
    ) -> QueryResult:
        """
        Handle procedural queries (how-to, step-by-step).

        Args:
            query_text: Query text
            top_k: Number of results
            filters: Search filters

        Returns:
            QueryResult with procedural steps
        """
        # First get relevant information
        result = await self.simple_engine.query(
            query_text=query_text,
            top_k=top_k,
            filters=filters
        )

        # Structure as steps
        if result.sources:
            system_prompt = """Tu es un expert en procédures de marchés publics.

            Reformule la réponse en étapes claires et ordonnées.

            Format:
            Étape 1: [Description]
            - Détail important
            - Point d'attention

            Étape 2: [Description]
            ...

            Ajoute les délais et documents requis si pertinent."""

            user_prompt = f"""Question: {query_text}

Informations disponibles:
{result.answer}

Présente sous forme d'étapes procédurales."""

            procedural_answer = await self.mistral_service.generate_completion(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1
            )

            result.answer = procedural_answer
            result.metadata["format"] = "procedural"

        return result

    async def _handle_compliance_query(
        self,
        query_text: str,
        top_k: Optional[int],
        filters: Optional[Dict[str, Any]]
    ) -> QueryResult:
        """
        Handle compliance queries.

        Args:
            query_text: Query text
            top_k: Number of results
            filters: Search filters

        Returns:
            QueryResult with compliance analysis
        """
        # Get relevant regulatory information
        result = await self.simple_engine.query(
            query_text=query_text,
            top_k=top_k,
            filters=filters
        )

        # Enhance with compliance analysis
        if result.sources:
            system_prompt = """Tu es un expert en conformité réglementaire des marchés publics.

            Analyse la conformité et structure ta réponse ainsi:

            1. **Exigences réglementaires**
               - Requirement 1
               - Requirement 2

            2. **Évaluation de conformité**
               ✅ Conforme: [éléments]
               ⚠️ À vérifier: [éléments]
               ❌ Non conforme: [éléments]

            3. **Recommandations**
               - Action 1
               - Action 2

            Cite les articles et sources réglementaires."""

            user_prompt = f"""Question de conformité: {query_text}

Informations disponibles:
{result.answer}

Fournis une analyse de conformité structurée."""

            compliance_answer = await self.mistral_service.generate_completion(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1
            )

            result.answer = compliance_answer
            result.metadata["format"] = "compliance"
            result.metadata["requires_validation"] = True

        return result

    def _get_engine_for_type(self, query_type: QueryType) -> str:
        """
        Get engine name for query type.

        Args:
            query_type: Query type

        Returns:
            Engine name
        """
        if query_type in [QueryType.SIMPLE, QueryType.TEMPORAL]:
            return "simple"
        else:
            return "subquestion"

    async def adaptive_query(
        self,
        query_text: str,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> QueryResult:
        """
        Adaptive query with context awareness.

        Args:
            query_text: Query text
            user_context: User context (role, preferences)
            conversation_history: Previous Q&A pairs

        Returns:
            Contextually adapted QueryResult
        """
        # Enhance query with context if available
        enhanced_query = query_text

        if conversation_history:
            # Add relevant context from history
            recent_context = self._extract_relevant_context(
                query_text,
                conversation_history
            )
            if recent_context:
                enhanced_query = f"{recent_context}\n\n{query_text}"

        # Adapt parameters based on user context
        top_k = 5  # Default
        if user_context:
            # Expert users might want more results
            if user_context.get("expertise_level") == "expert":
                top_k = 10
            # Novices might want simpler answers
            elif user_context.get("expertise_level") == "novice":
                top_k = 3

        # Execute query with adapted parameters
        result = await self.query(
            query_text=enhanced_query,
            top_k=top_k
        )

        # Post-process based on user context
        if user_context and user_context.get("expertise_level") == "novice":
            # Simplify answer for novices
            result.answer = await self._simplify_answer(result.answer)

        return result

    def _extract_relevant_context(
        self,
        query: str,
        history: List[Dict[str, str]]
    ) -> str:
        """
        Extract relevant context from conversation history.

        Args:
            query: Current query
            history: Conversation history

        Returns:
            Relevant context string
        """
        if not history:
            return ""

        # Take last 2 exchanges for context
        recent = history[-2:] if len(history) >= 2 else history

        context_parts = []
        for exchange in recent:
            if "question" in exchange and "answer" in exchange:
                # Include if potentially relevant
                q = exchange["question"][:100]
                a = exchange["answer"][:200]
                context_parts.append(f"Q: {q}\nA: {a}")

        if context_parts:
            return "Contexte de la conversation:\n" + "\n".join(context_parts)

        return ""

    async def _simplify_answer(self, answer: str) -> str:
        """
        Simplify answer for novice users.

        Args:
            answer: Original answer

        Returns:
            Simplified answer
        """
        system_prompt = """Simplifie cette réponse pour un utilisateur non-expert.

        Règles:
        1. Utilise un langage simple
        2. Évite le jargon technique
        3. Explique les acronymes
        4. Reste factuel et précis
        """

        user_prompt = f"Simplifie: {answer}"

        simplified = await self.mistral_service.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2
        )

        return simplified