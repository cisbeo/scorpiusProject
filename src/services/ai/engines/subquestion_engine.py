"""SubQuestion query engine for complex multi-part queries."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import asyncio
import re

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.ai.engines.simple_query_engine import SimpleQueryEngine, QueryResult
from src.services.ai.mistral_service import get_mistral_service
from src.core.ai_config import ai_config

logger = logging.getLogger(__name__)


class SubQuestion:
    """Represents a sub-question extracted from a complex query."""

    def __init__(
        self,
        question: str,
        context: str = "",
        priority: int = 0,
        dependencies: List[str] = None
    ):
        self.question = question
        self.context = context
        self.priority = priority
        self.dependencies = dependencies or []
        self.answer: Optional[str] = None
        self.sources: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "question": self.question,
            "context": self.context,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "answer": self.answer,
            "sources": self.sources
        }


class SubQuestionQueryEngine:
    """
    Query engine that decomposes complex queries into sub-questions.

    This engine:
    1. Analyzes complex queries
    2. Breaks them into atomic sub-questions
    3. Orders sub-questions by dependencies
    4. Executes each sub-question
    5. Synthesizes final answer
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize SubQuestion query engine.

        Args:
            db: Database session
        """
        self.db = db
        self.simple_engine = SimpleQueryEngine(db)
        self.mistral_service = get_mistral_service()
        self.max_subquestions = 5
        self.parallel_execution = True

    async def query(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        max_subquestions: Optional[int] = None
    ) -> QueryResult:
        """
        Execute a complex query by decomposition.

        Args:
            query_text: Complex query text
            top_k: Number of results per sub-query
            filters: Search filters
            max_subquestions: Maximum number of sub-questions

        Returns:
            QueryResult with synthesized answer
        """
        start_time = datetime.utcnow()

        try:
            # Step 1: Decompose query into sub-questions
            logger.info(f"Decomposing query: {query_text[:50]}...")
            subquestions = await self._decompose_query(
                query_text,
                max_subquestions or self.max_subquestions
            )

            if not subquestions:
                # Fall back to simple query if decomposition fails
                logger.warning("No sub-questions generated, falling back to simple query")
                return await self.simple_engine.query(
                    query_text=query_text,
                    top_k=top_k,
                    filters=filters
                )

            logger.info(f"Generated {len(subquestions)} sub-questions")

            # Step 2: Execute sub-questions
            if self.parallel_execution and not self._has_dependencies(subquestions):
                # Execute in parallel if no dependencies
                logger.info("Executing sub-questions in parallel")
                await self._execute_parallel(subquestions, top_k, filters)
            else:
                # Execute sequentially respecting dependencies
                logger.info("Executing sub-questions sequentially")
                await self._execute_sequential(subquestions, top_k, filters)

            # Step 3: Synthesize final answer
            logger.info("Synthesizing final answer from sub-questions")
            final_answer = await self._synthesize_answer(
                original_query=query_text,
                subquestions=subquestions
            )

            # Step 4: Collect all sources
            all_sources = self._collect_sources(subquestions)

            # Calculate confidence based on sub-question results
            confidence = self._calculate_combined_confidence(subquestions)

            # Create result
            result = QueryResult(
                query=query_text,
                answer=final_answer,
                sources=all_sources,
                metadata={
                    "engine": "subquestion",
                    "num_subquestions": len(subquestions),
                    "subquestions": [sq.to_dict() for sq in subquestions],
                    "processing_time_ms": int(
                        (datetime.utcnow() - start_time).total_seconds() * 1000
                    )
                },
                confidence=confidence
            )

            logger.info(f"SubQuestion query completed with {len(subquestions)} sub-questions")
            return result

        except Exception as e:
            logger.error(f"SubQuestion query failed: {e}")
            # Fall back to simple query
            return await self.simple_engine.query(
                query_text=query_text,
                top_k=top_k,
                filters=filters
            )

    async def _decompose_query(
        self,
        query: str,
        max_subquestions: int
    ) -> List[SubQuestion]:
        """
        Decompose a complex query into sub-questions.

        Args:
            query: Original complex query
            max_subquestions: Maximum number of sub-questions

        Returns:
            List of SubQuestion objects
        """
        system_prompt = """Tu es un expert en analyse de questions complexes sur les marchés publics.

        Décompose la question en sous-questions atomiques qui peuvent être répondues indépendamment.

        Règles:
        1. Chaque sous-question doit être simple et précise
        2. Évite la redondance entre sous-questions
        3. Ordonne par priorité (plus important en premier)
        4. Maximum {max_subquestions} sous-questions
        5. Indique les dépendances si une réponse nécessite une autre

        Format de réponse (JSON):
        {{
            "subquestions": [
                {{
                    "question": "La sous-question",
                    "context": "Contexte ou clarification",
                    "priority": 1,
                    "dependencies": []
                }}
            ]
        }}
        """.format(max_subquestions=max_subquestions)

        user_prompt = f"""Question complexe à décomposer:
        {query}

        Décompose cette question en sous-questions atomiques."""

        # Generate decomposition
        response = await self.mistral_service.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3  # Some creativity for decomposition
        )

        # Parse response
        try:
            import json
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                subquestions = []

                for sq_data in data.get("subquestions", [])[:max_subquestions]:
                    subquestions.append(SubQuestion(
                        question=sq_data.get("question", ""),
                        context=sq_data.get("context", ""),
                        priority=sq_data.get("priority", 0),
                        dependencies=sq_data.get("dependencies", [])
                    ))

                # Sort by priority
                subquestions.sort(key=lambda x: x.priority)
                return subquestions

        except Exception as e:
            logger.error(f"Failed to parse decomposition: {e}")

        return []

    async def _execute_parallel(
        self,
        subquestions: List[SubQuestion],
        top_k: Optional[int],
        filters: Optional[Dict[str, Any]]
    ):
        """
        Execute sub-questions in parallel.

        Args:
            subquestions: List of sub-questions
            top_k: Number of results per query
            filters: Search filters
        """
        tasks = []

        for sq in subquestions:
            task = self.simple_engine.query(
                query_text=sq.question,
                top_k=top_k,
                filters=filters,
                use_cache=True
            )
            tasks.append(task)

        # Execute all queries in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Assign results to sub-questions
        for sq, result in zip(subquestions, results):
            if isinstance(result, Exception):
                logger.error(f"Sub-question failed: {sq.question}, Error: {result}")
                sq.answer = f"Erreur lors de la recherche: {str(result)}"
            else:
                sq.answer = result.answer
                sq.sources = result.sources

    async def _execute_sequential(
        self,
        subquestions: List[SubQuestion],
        top_k: Optional[int],
        filters: Optional[Dict[str, Any]]
    ):
        """
        Execute sub-questions sequentially respecting dependencies.

        Args:
            subquestions: List of sub-questions
            top_k: Number of results per query
            filters: Search filters
        """
        answered = {}

        for sq in subquestions:
            # Build context from dependencies
            context = ""
            if sq.dependencies:
                dep_answers = []
                for dep in sq.dependencies:
                    if dep in answered:
                        dep_answers.append(f"{dep}: {answered[dep]}")

                if dep_answers:
                    context = "Contexte des questions précédentes:\n" + "\n".join(dep_answers)

            # Enhance question with context if available
            query_text = sq.question
            if context:
                query_text = f"{context}\n\nQuestion: {sq.question}"

            # Execute query
            result = await self.simple_engine.query(
                query_text=query_text,
                top_k=top_k,
                filters=filters,
                use_cache=True
            )

            sq.answer = result.answer
            sq.sources = result.sources

            # Store for dependencies
            answered[sq.question] = sq.answer

    async def _synthesize_answer(
        self,
        original_query: str,
        subquestions: List[SubQuestion]
    ) -> str:
        """
        Synthesize final answer from sub-question results.

        Args:
            original_query: Original complex query
            subquestions: List of answered sub-questions

        Returns:
            Synthesized final answer
        """
        # Build context from sub-question answers
        subq_context = []
        for i, sq in enumerate(subquestions, 1):
            if sq.answer:
                subq_context.append(
                    f"Sous-question {i}: {sq.question}\n"
                    f"Réponse: {sq.answer}"
                )

        context = "\n\n".join(subq_context)

        system_prompt = """Tu es un expert en synthèse d'informations sur les marchés publics.

        Synthétise les réponses aux sous-questions pour répondre à la question principale.

        Règles importantes:
        1. Base-toi UNIQUEMENT sur les réponses aux sous-questions
        2. Sois complet mais concis
        3. Structure ta réponse de manière claire
        4. Cite les sources pertinentes
        5. Indique si certains aspects n'ont pas pu être répondus
        """

        user_prompt = f"""Question principale: {original_query}

Réponses aux sous-questions:
{context}

Synthétise ces informations pour répondre complètement à la question principale."""

        # Generate synthesis
        synthesis = await self.mistral_service.generate_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1  # Low temperature for factual synthesis
        )

        return synthesis

    def _has_dependencies(self, subquestions: List[SubQuestion]) -> bool:
        """
        Check if any sub-questions have dependencies.

        Args:
            subquestions: List of sub-questions

        Returns:
            True if dependencies exist
        """
        return any(sq.dependencies for sq in subquestions)

    def _collect_sources(self, subquestions: List[SubQuestion]) -> List[Dict[str, Any]]:
        """
        Collect all unique sources from sub-questions.

        Args:
            subquestions: List of sub-questions

        Returns:
            List of unique sources
        """
        seen_chunks = set()
        sources = []

        for sq in subquestions:
            for source in sq.sources:
                chunk_id = source.get("chunk_id")
                if chunk_id and chunk_id not in seen_chunks:
                    seen_chunks.add(chunk_id)
                    # Add sub-question info to source
                    source["subquestion"] = sq.question[:100]
                    sources.append(source)

        # Sort by score
        sources.sort(key=lambda x: x.get("score", 0), reverse=True)

        return sources

    def _calculate_combined_confidence(
        self,
        subquestions: List[SubQuestion]
    ) -> float:
        """
        Calculate combined confidence from sub-questions.

        Args:
            subquestions: List of sub-questions

        Returns:
            Combined confidence score
        """
        if not subquestions:
            return 0.0

        # Simple average for now
        # Could be weighted by priority
        total_confidence = 0.0
        count = 0

        for sq in subquestions:
            if sq.answer and sq.answer != "Je n'ai pas trouvé d'informations":
                # Estimate confidence based on sources
                if sq.sources:
                    avg_score = sum(s.get("score", 0) for s in sq.sources) / len(sq.sources)
                    total_confidence += avg_score
                    count += 1

        if count == 0:
            return 0.0

        return min(max(total_confidence / count, 0.0), 1.0)

    async def query_with_analysis(
        self,
        query_text: str,
        analyze_first: bool = True,
        top_k: Optional[int] = None
    ) -> Tuple[QueryResult, Dict[str, Any]]:
        """
        Query with optional complexity analysis.

        Args:
            query_text: Query text
            analyze_first: Whether to analyze complexity first
            top_k: Number of results

        Returns:
            Tuple of (QueryResult, analysis_metadata)
        """
        analysis = {}

        if analyze_first:
            # Analyze query complexity
            complexity = await self._analyze_complexity(query_text)
            analysis["complexity"] = complexity

            # Decide strategy based on complexity
            if complexity["score"] < 0.3:
                # Simple query - use simple engine
                logger.info("Query classified as simple, using SimpleQueryEngine")
                result = await self.simple_engine.query(
                    query_text=query_text,
                    top_k=top_k
                )
                analysis["engine_used"] = "simple"
            else:
                # Complex query - use sub-question decomposition
                logger.info("Query classified as complex, using SubQuestionQueryEngine")
                result = await self.query(
                    query_text=query_text,
                    top_k=top_k
                )
                analysis["engine_used"] = "subquestion"
        else:
            # Direct execution without analysis
            result = await self.query(
                query_text=query_text,
                top_k=top_k
            )
            analysis["engine_used"] = "subquestion"

        return result, analysis

    async def _analyze_complexity(self, query_text: str) -> Dict[str, Any]:
        """
        Analyze query complexity.

        Args:
            query_text: Query to analyze

        Returns:
            Complexity analysis
        """
        # Simple heuristics for complexity
        indicators = {
            "multiple_questions": len(re.findall(r'\?', query_text)) > 1,
            "conjunctions": any(word in query_text.lower() for word in ["et", "ou", "ainsi que", "également"]),
            "comparisons": any(word in query_text.lower() for word in ["comparer", "différence", "versus", "contre"]),
            "lists": any(word in query_text.lower() for word in ["liste", "énumérer", "tous les", "chaque"]),
            "temporal": any(word in query_text.lower() for word in ["avant", "après", "pendant", "historique"]),
            "length": len(query_text) > 150
        }

        # Calculate complexity score
        score = sum(1 for v in indicators.values() if v) / len(indicators)

        return {
            "score": score,
            "indicators": indicators,
            "classification": "complex" if score > 0.3 else "simple"
        }