"""Smart document chunking service with multiple strategies."""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import hashlib

from src.core.ai_config import ai_config, ChunkingStrategy
from src.processors.base import ProcessingResult

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a document chunk with metadata."""

    chunk_id: str
    chunk_text: str
    chunk_index: int
    chunk_size: int
    overlap_size: int
    metadata: Dict[str, Any]
    document_type: Optional[str] = None
    section_type: Optional[str] = None
    page_number: Optional[int] = None
    confidence_score: float = 1.0


class ChunkingService:
    """Service for intelligent document chunking."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize chunking service.

        Args:
            config: Optional configuration override
        """
        self.config = config or ai_config.get_chunking_config()
        self.strategy = ChunkingStrategy(self.config["strategy"])
        self.chunk_size = self.config["chunk_size"]
        self.chunk_overlap = self.config["chunk_overlap"]
        self.max_chunk_size = self.config["max_chunk_size"]

        # French procurement document patterns
        self.section_patterns = {
            "article": r"(?:Article|ARTICLE)\s+(\d+(?:\.\d+)?)",
            "chapitre": r"(?:Chapitre|CHAPITRE)\s+([IVXLCDM]+|\d+)",
            "section": r"(?:Section|SECTION)\s+(\d+(?:\.\d+)?)",
            "titre": r"(?:Titre|TITRE)\s+([IVXLCDM]+|\d+)",
            "annexe": r"(?:Annexe|ANNEXE)\s+(\d+|[A-Z])",
            "clause": r"(?:Clause|CLAUSE)\s+(\d+(?:\.\d+)?)",
        }

        # Document type markers
        self.doc_type_markers = {
            "CCTP": ["cahier", "clauses", "techniques", "particulières"],
            "CCAP": ["cahier", "clauses", "administratives", "particulières"],
            "RC": ["règlement", "consultation"],
            "BPU": ["bordereau", "prix", "unitaires"],
            "DQE": ["détail", "quantitatif", "estimatif"],
            "DPGF": ["décomposition", "prix", "global", "forfaitaire"],
        }

    async def chunk_document(
        self,
        processing_result: ProcessingResult,
        document_id: str,
        strategy_override: Optional[ChunkingStrategy] = None
    ) -> List[DocumentChunk]:
        """
        Chunk a document using the configured strategy.

        Args:
            processing_result: Document processing result
            document_id: Document ID for chunk ID generation
            strategy_override: Override default strategy

        Returns:
            List of document chunks
        """
        strategy = strategy_override or self.strategy

        if strategy == ChunkingStrategy.FIXED_SIZE:
            return await self._fixed_size_chunking(processing_result, document_id)
        elif strategy == ChunkingStrategy.SEMANTIC:
            return await self._semantic_chunking(processing_result, document_id)
        elif strategy == ChunkingStrategy.STRUCTURAL:
            return await self._structural_chunking(processing_result, document_id)
        elif strategy == ChunkingStrategy.HYBRID:
            return await self._hybrid_chunking(processing_result, document_id)
        else:
            logger.warning(f"Unknown strategy {strategy}, falling back to fixed size")
            return await self._fixed_size_chunking(processing_result, document_id)

    async def _fixed_size_chunking(
        self,
        processing_result: ProcessingResult,
        document_id: str
    ) -> List[DocumentChunk]:
        """
        Simple fixed-size chunking with overlap.

        Args:
            processing_result: Document processing result
            document_id: Document ID

        Returns:
            List of fixed-size chunks
        """
        chunks = []
        text = processing_result.raw_text

        if not text:
            logger.warning("No raw text available for chunking")
            return []

        chunk_index = 0

        # Token approximation (1 token ≈ 3-4 characters, using 3 for more chunks)
        char_size = self.chunk_size * 3
        char_overlap = self.chunk_overlap * 3

        logger.info(f"Fixed-size chunking: text length={len(text)}, chunk_size={char_size}, overlap={char_overlap}")

        for i in range(0, len(text), char_size - char_overlap):
            chunk_text = text[i:i + char_size]

            if len(chunk_text.strip()) < 50:  # Skip very small chunks
                continue

            chunk = DocumentChunk(
                chunk_id=self._generate_chunk_id(document_id, chunk_index),
                chunk_text=chunk_text,
                chunk_index=chunk_index,
                chunk_size=len(chunk_text),
                overlap_size=char_overlap if i > 0 else 0,
                metadata={
                    "strategy": "fixed_size",
                    "start_char": i,
                    "end_char": i + len(chunk_text)
                }
            )
            chunks.append(chunk)
            chunk_index += 1

        logger.info(f"Created {len(chunks)} fixed-size chunks")
        return chunks

    async def _semantic_chunking(
        self,
        processing_result: ProcessingResult,
        document_id: str
    ) -> List[DocumentChunk]:
        """
        Semantic chunking based on natural boundaries.

        Args:
            processing_result: Document processing result
            document_id: Document ID

        Returns:
            List of semantic chunks
        """
        chunks = []
        text = processing_result.raw_text

        # Split by paragraphs first
        paragraphs = self._split_into_paragraphs(text)

        current_chunk = []
        current_size = 0
        chunk_index = 0
        char_size = self.chunk_size * 4

        for para in paragraphs:
            para_size = len(para)

            # If paragraph is too large, split it
            if para_size > char_size:
                # Save current chunk if exists
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append(self._create_chunk(
                        document_id, chunk_index, chunk_text, "semantic"
                    ))
                    chunk_index += 1
                    current_chunk = []
                    current_size = 0

                # Split large paragraph
                sentences = self._split_into_sentences(para)
                for sentence in sentences:
                    if current_size + len(sentence) > char_size:
                        if current_chunk:
                            chunk_text = " ".join(current_chunk)
                            chunks.append(self._create_chunk(
                                document_id, chunk_index, chunk_text, "semantic"
                            ))
                            chunk_index += 1
                        current_chunk = [sentence]
                        current_size = len(sentence)
                    else:
                        current_chunk.append(sentence)
                        current_size += len(sentence)
            else:
                # Check if adding paragraph exceeds limit
                if current_size + para_size > char_size:
                    # Save current chunk
                    if current_chunk:
                        chunk_text = "\n\n".join(current_chunk)
                        chunks.append(self._create_chunk(
                            document_id, chunk_index, chunk_text, "semantic"
                        ))
                        chunk_index += 1
                    current_chunk = [para]
                    current_size = para_size
                else:
                    current_chunk.append(para)
                    current_size += para_size

        # Add remaining chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(self._create_chunk(
                document_id, chunk_index, chunk_text, "semantic"
            ))

        logger.info(f"Created {len(chunks)} semantic chunks")
        return chunks

    async def _structural_chunking(
        self,
        processing_result: ProcessingResult,
        document_id: str
    ) -> List[DocumentChunk]:
        """
        Structural chunking based on document structure.

        Args:
            processing_result: Document processing result
            document_id: Document ID

        Returns:
            List of structural chunks
        """
        chunks = []
        chunk_index = 0

        # Use structured content if available
        if processing_result.structured_content:
            structured = processing_result.structured_content

            # Process sections
            if "sections" in structured:
                for section_key, section_content in structured["sections"].items():
                    if isinstance(section_content, dict) and "content" in section_content:
                        content_text = self._extract_text_from_content(section_content["content"])
                    else:
                        content_text = str(section_content)

                    if len(content_text.strip()) > 50:
                        chunk = DocumentChunk(
                            chunk_id=self._generate_chunk_id(document_id, chunk_index),
                            chunk_text=content_text,
                            chunk_index=chunk_index,
                            chunk_size=len(content_text),
                            overlap_size=0,
                            metadata={
                                "strategy": "structural",
                                "section": section_key
                            },
                            section_type=section_key
                        )
                        chunks.append(chunk)
                        chunk_index += 1

            # Process procurement sections
            if "procurement_sections" in structured:
                for section_type, items in structured["procurement_sections"].items():
                    combined_text = ""
                    for item in items:
                        if isinstance(item, dict) and "text" in item:
                            combined_text += item["text"] + "\n\n"
                        else:
                            combined_text += str(item) + "\n\n"

                    if len(combined_text.strip()) > 50:
                        # Split if too large
                        if len(combined_text) > self.max_chunk_size * 4:
                            sub_chunks = await self._split_large_section(
                                combined_text, document_id, chunk_index, section_type
                            )
                            chunks.extend(sub_chunks)
                            chunk_index += len(sub_chunks)
                        else:
                            chunk = DocumentChunk(
                                chunk_id=self._generate_chunk_id(document_id, chunk_index),
                                chunk_text=combined_text.strip(),
                                chunk_index=chunk_index,
                                chunk_size=len(combined_text),
                                overlap_size=0,
                                metadata={
                                    "strategy": "structural",
                                    "procurement_section": section_type
                                },
                                section_type=section_type,
                                document_type=self._detect_document_type(combined_text)
                            )
                            chunks.append(chunk)
                            chunk_index += 1

            # Process tables separately
            if "tables" in structured:
                for i, table in enumerate(structured["tables"]):
                    table_text = self._format_table_as_text(table)
                    if len(table_text.strip()) > 50:
                        chunk = DocumentChunk(
                            chunk_id=self._generate_chunk_id(document_id, chunk_index),
                            chunk_text=table_text,
                            chunk_index=chunk_index,
                            chunk_size=len(table_text),
                            overlap_size=0,
                            metadata={
                                "strategy": "structural",
                                "content_type": "table",
                                "table_index": i
                            },
                            section_type="table",
                            page_number=table.get("page") if isinstance(table, dict) else None
                        )
                        chunks.append(chunk)
                        chunk_index += 1

        # Fallback to text-based structural chunking
        if not chunks:
            chunks = await self._text_based_structural_chunking(
                processing_result.raw_text, document_id
            )

        logger.info(f"Created {len(chunks)} structural chunks")
        return chunks

    async def _hybrid_chunking(
        self,
        processing_result: ProcessingResult,
        document_id: str
    ) -> List[DocumentChunk]:
        """
        Hybrid chunking combining structural and semantic approaches.

        Args:
            processing_result: Document processing result
            document_id: Document ID

        Returns:
            List of hybrid chunks
        """
        # Start with structural chunking
        structural_chunks = await self._structural_chunking(processing_result, document_id)

        # If structural chunking doesn't produce enough chunks, use fixed-size as fallback
        if len(structural_chunks) < 5 and processing_result.raw_text:
            logger.info("Structural chunking produced few chunks, falling back to fixed-size")
            return await self._fixed_size_chunking(processing_result, document_id)

        # Refine large chunks with semantic chunking
        final_chunks = []
        chunk_index = 0

        for struct_chunk in structural_chunks:
            if struct_chunk.chunk_size > self.max_chunk_size * 4:
                # Split large structural chunk semantically
                sub_chunks = await self._refine_chunk_semantically(
                    struct_chunk, document_id, chunk_index
                )
                final_chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)
            else:
                # Keep as is but update index
                struct_chunk.chunk_index = chunk_index
                struct_chunk.chunk_id = self._generate_chunk_id(document_id, chunk_index)
                final_chunks.append(struct_chunk)
                chunk_index += 1

        # Add overlap for better context
        final_chunks = self._add_chunk_overlap(final_chunks)

        logger.info(f"Created {len(final_chunks)} hybrid chunks")
        return final_chunks

    async def _text_based_structural_chunking(
        self,
        text: str,
        document_id: str
    ) -> List[DocumentChunk]:
        """
        Extract structural chunks from raw text using patterns.

        Args:
            text: Raw text
            document_id: Document ID

        Returns:
            List of chunks based on text patterns
        """
        chunks = []
        chunk_index = 0

        # Find all section headers
        section_positions = []
        for pattern_name, pattern in self.section_patterns.items():
            for match in re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE):
                section_positions.append({
                    "type": pattern_name,
                    "start": match.start(),
                    "end": match.end(),
                    "number": match.group(1),
                    "full_match": match.group(0)
                })

        # Sort by position
        section_positions.sort(key=lambda x: x["start"])

        # Extract text between sections
        for i, section in enumerate(section_positions):
            start = section["start"]
            end = section_positions[i + 1]["start"] if i + 1 < len(section_positions) else len(text)

            section_text = text[start:end].strip()

            if len(section_text) > 50:
                chunk = DocumentChunk(
                    chunk_id=self._generate_chunk_id(document_id, chunk_index),
                    chunk_text=section_text,
                    chunk_index=chunk_index,
                    chunk_size=len(section_text),
                    overlap_size=0,
                    metadata={
                        "strategy": "text_structural",
                        "section_type": section["type"],
                        "section_number": section["number"]
                    },
                    section_type=f"{section['type']}_{section['number']}"
                )
                chunks.append(chunk)
                chunk_index += 1

        return chunks

    async def _split_large_section(
        self,
        text: str,
        document_id: str,
        start_index: int,
        section_type: str
    ) -> List[DocumentChunk]:
        """
        Split a large section into smaller chunks.

        Args:
            text: Section text
            document_id: Document ID
            start_index: Starting chunk index
            section_type: Type of section

        Returns:
            List of sub-chunks
        """
        chunks = []
        paragraphs = self._split_into_paragraphs(text)
        current_chunk = []
        current_size = 0
        chunk_index = start_index
        max_size = self.max_chunk_size * 4

        for para in paragraphs:
            if current_size + len(para) > max_size:
                if current_chunk:
                    chunk_text = "\n\n".join(current_chunk)
                    chunk = DocumentChunk(
                        chunk_id=self._generate_chunk_id(document_id, chunk_index),
                        chunk_text=chunk_text,
                        chunk_index=chunk_index,
                        chunk_size=len(chunk_text),
                        overlap_size=0,
                        metadata={
                            "strategy": "split_section",
                            "original_section": section_type
                        },
                        section_type=section_type
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                current_chunk = [para]
                current_size = len(para)
            else:
                current_chunk.append(para)
                current_size += len(para)

        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunk = DocumentChunk(
                chunk_id=self._generate_chunk_id(document_id, chunk_index),
                chunk_text=chunk_text,
                chunk_index=chunk_index,
                chunk_size=len(chunk_text),
                overlap_size=0,
                metadata={
                    "strategy": "split_section",
                    "original_section": section_type
                },
                section_type=section_type
            )
            chunks.append(chunk)

        return chunks

    async def _refine_chunk_semantically(
        self,
        chunk: DocumentChunk,
        document_id: str,
        start_index: int
    ) -> List[DocumentChunk]:
        """
        Refine a large chunk using semantic boundaries.

        Args:
            chunk: Large chunk to refine
            document_id: Document ID
            start_index: Starting index

        Returns:
            List of refined chunks
        """
        refined = []
        sentences = self._split_into_sentences(chunk.chunk_text)
        current_chunk = []
        current_size = 0
        chunk_index = start_index
        max_size = self.chunk_size * 4

        for sentence in sentences:
            if current_size + len(sentence) > max_size:
                if current_chunk:
                    chunk_text = " ".join(current_chunk)
                    new_chunk = DocumentChunk(
                        chunk_id=self._generate_chunk_id(document_id, chunk_index),
                        chunk_text=chunk_text,
                        chunk_index=chunk_index,
                        chunk_size=len(chunk_text),
                        overlap_size=0,
                        metadata={
                            **chunk.metadata,
                            "refinement": "semantic"
                        },
                        document_type=chunk.document_type,
                        section_type=chunk.section_type,
                        page_number=chunk.page_number
                    )
                    refined.append(new_chunk)
                    chunk_index += 1
                current_chunk = [sentence]
                current_size = len(sentence)
            else:
                current_chunk.append(sentence)
                current_size += len(sentence)

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            new_chunk = DocumentChunk(
                chunk_id=self._generate_chunk_id(document_id, chunk_index),
                chunk_text=chunk_text,
                chunk_index=chunk_index,
                chunk_size=len(chunk_text),
                overlap_size=0,
                metadata={
                    **chunk.metadata,
                    "refinement": "semantic"
                },
                document_type=chunk.document_type,
                section_type=chunk.section_type,
                page_number=chunk.page_number
            )
            refined.append(new_chunk)

        return refined

    def _add_chunk_overlap(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """
        Add overlap between consecutive chunks.

        Args:
            chunks: List of chunks

        Returns:
            Chunks with overlap added
        """
        if not chunks or len(chunks) < 2:
            return chunks

        overlap_chars = self.chunk_overlap * 4

        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            curr_chunk = chunks[i]

            # Add end of previous chunk to current
            overlap_text = prev_chunk.chunk_text[-overlap_chars:]
            curr_chunk.chunk_text = overlap_text + "\n" + curr_chunk.chunk_text
            curr_chunk.overlap_size = len(overlap_text)
            curr_chunk.chunk_size = len(curr_chunk.chunk_text)

        return chunks

    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        # Split by double newlines or common paragraph markers
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # French sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        return [s.strip() for s in sentences if s.strip()]

    def _generate_chunk_id(self, document_id: str, chunk_index: int) -> str:
        """Generate unique chunk ID."""
        chunk_str = f"{document_id}_{chunk_index}"
        return hashlib.md5(chunk_str.encode()).hexdigest()

    def _create_chunk(
        self,
        document_id: str,
        chunk_index: int,
        text: str,
        strategy: str
    ) -> DocumentChunk:
        """Create a DocumentChunk object."""
        return DocumentChunk(
            chunk_id=self._generate_chunk_id(document_id, chunk_index),
            chunk_text=text,
            chunk_index=chunk_index,
            chunk_size=len(text),
            overlap_size=0,
            metadata={"strategy": strategy}
        )

    def _extract_text_from_content(self, content: List[Dict]) -> str:
        """Extract text from structured content."""
        texts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                texts.append(item["text"])
            else:
                texts.append(str(item))
        return "\n\n".join(texts)

    def _format_table_as_text(self, table: Any) -> str:
        """Format table data as text."""
        if isinstance(table, dict):
            if "text" in table:
                return table["text"]
            elif "data" in table:
                rows = []
                for row in table["data"]:
                    if isinstance(row, list):
                        rows.append(" | ".join(str(cell) for cell in row))
                return "\n".join(rows)
        return str(table)

    def _detect_document_type(self, text: str) -> Optional[str]:
        """Detect document type from text."""
        text_lower = text.lower()
        for doc_type, markers in self.doc_type_markers.items():
            if all(marker in text_lower for marker in markers):
                return doc_type
        return None