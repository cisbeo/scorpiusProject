"""Prompt templates for RAG queries inspired by Mistral best practices."""

from typing import List, Optional


class PromptTemplates:
    """Collection of optimized prompt templates for different use cases."""

    @staticmethod
    def rag_query_prompt(
        query: str,
        context: str,
        system_instruction: Optional[str] = None
    ) -> str:
        """
        Generate RAG query prompt with clear context separation.
        Based on Mistral's recommended template structure.

        Args:
            query: User's question
            context: Retrieved context chunks
            system_instruction: Optional system instruction

        Returns:
            Formatted prompt
        """
        system_instruction = system_instruction or (
            "Tu es un assistant spécialisé dans l'analyse de documents de marchés publics français. "
            "Réponds en français de manière précise et structurée."
        )

        prompt = f"""{system_instruction}

Les informations contextuelles sont ci-dessous.
---------------------
{context}
---------------------
En utilisant UNIQUEMENT les informations contextuelles ci-dessus et sans connaissances préalables, réponds à la question.
Si l'information n'est pas disponible dans le contexte, dis-le clairement.

Question: {query}

Réponse:"""

        return prompt

    @staticmethod
    def rag_query_with_sources_prompt(
        query: str,
        context_chunks: List[dict],
        system_instruction: Optional[str] = None
    ) -> str:
        """
        Generate RAG query prompt with source tracking.

        Args:
            query: User's question
            context_chunks: List of context chunks with metadata
            system_instruction: Optional system instruction

        Returns:
            Formatted prompt with sources
        """
        system_instruction = system_instruction or (
            "Tu es un assistant spécialisé dans l'analyse de documents de marchés publics français. "
            "Réponds en français de manière précise et structurée."
        )

        # Format context with source indicators
        formatted_context = ""
        for i, chunk in enumerate(context_chunks, 1):
            chunk_text = chunk.get("text", chunk.get("chunk_text", ""))
            page = chunk.get("page_number", "N/A")
            formatted_context += f"[Source {i} - Page {page}]\n{chunk_text}\n\n"

        prompt = f"""{system_instruction}

Les informations contextuelles sont ci-dessous avec leurs sources.
---------------------
{formatted_context}
---------------------
En utilisant UNIQUEMENT les informations contextuelles ci-dessus et sans connaissances préalables, réponds à la question.
Cite les sources pertinentes (ex: [Source 1]) dans ta réponse.
Si l'information n'est pas disponible dans le contexte, dis-le clairement.

Question: {query}

Réponse avec sources:"""

        return prompt

    @staticmethod
    def procurement_analysis_prompt(
        query: str,
        context: str,
        document_type: Optional[str] = None
    ) -> str:
        """
        Specialized prompt for procurement document analysis.

        Args:
            query: Analysis question
            context: Document context
            document_type: Type of procurement document (CCTP, CCAP, etc.)

        Returns:
            Formatted prompt for procurement analysis
        """
        doc_type_info = ""
        if document_type:
            doc_type_info = f"Type de document: {document_type}\n"

        prompt = f"""Tu es un expert en analyse de marchés publics français.
{doc_type_info}
Contexte du document:
---------------------
{context}
---------------------
Analyse le contexte ci-dessus pour répondre à la question suivante.
Sois précis et cite les éléments spécifiques du document.
Focus sur les aspects techniques, juridiques et financiers pertinents.

Question: {query}

Analyse détaillée:"""

        return prompt

    @staticmethod
    def rerank_prompt(
        query: str,
        chunks: List[str]
    ) -> str:
        """
        Prompt for reranking retrieved chunks by relevance.

        Args:
            query: Original query
            chunks: List of retrieved chunks

        Returns:
            Reranking prompt
        """
        chunks_text = "\n\n".join([f"Chunk {i+1}: {chunk}" for i, chunk in enumerate(chunks)])

        prompt = f"""Question: {query}

Chunks récupérés:
{chunks_text}

Classe ces chunks par ordre de pertinence pour répondre à la question (du plus pertinent au moins pertinent).
Retourne uniquement les numéros de chunks séparés par des virgules (ex: 3,1,2,4,5).

Classement:"""

        return prompt

    @staticmethod
    def summary_prompt(
        text: str,
        max_length: int = 500
    ) -> str:
        """
        Generate a summary prompt.

        Args:
            text: Text to summarize
            max_length: Maximum summary length

        Returns:
            Summary prompt
        """
        prompt = f"""Résume le texte suivant en français en conservant les informations essentielles.
La résumé doit faire maximum {max_length} caractères.

Texte:
---------------------
{text}
---------------------

Résumé concis:"""

        return prompt