"""
Smart document chunking module for processing large documents.
Implements adaptive chunking strategies based on document size and structure.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

class ChunkingStrategy(Enum):
    """Available chunking strategies."""
    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    STRUCTURAL = "structural"
    SLIDING_WINDOW = "sliding_window"

@dataclass
class DocumentChunk:
    """Represents a single chunk of a document."""

    chunk_id: int
    content: str
    metadata: Dict[str, Any]
    start_char: int
    end_char: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section_title: Optional[str] = None
    chunk_type: Optional[str] = None  # technical, functional, administrative, etc.

    @property
    def char_count(self) -> int:
        """Number of characters in chunk."""
        return len(self.content)

    @property
    def word_count(self) -> int:
        """Approximate word count."""
        return len(self.content.split())

    @property
    def token_estimate(self) -> int:
        """Estimate token count (rough: 1 token ≈ 4 chars for French)."""
        return self.char_count // 4


class BaseChunker(ABC):
    """Abstract base class for document chunkers."""

    @abstractmethod
    def chunk(self, text: str, **kwargs) -> List[DocumentChunk]:
        """Split text into chunks."""
        pass


class FixedSizeChunker(BaseChunker):
    """Simple fixed-size chunking."""

    def __init__(self, chunk_size: int = 2000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, **kwargs) -> List[DocumentChunk]:
        """Split text into fixed-size chunks with overlap."""
        chunks = []
        start = 0
        chunk_id = 0

        while start < len(text):
            end = start + self.chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end within next 100 chars
                sentence_end = text[end:end+100].find('.')
                if sentence_end != -1:
                    end = end + sentence_end + 1

            chunk_content = text[start:end].strip()

            if chunk_content:
                chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    content=chunk_content,
                    metadata={"strategy": "fixed_size"},
                    start_char=start,
                    end_char=end
                ))
                chunk_id += 1

            # Move start position with overlap
            start = end - self.overlap if end < len(text) else end

        return chunks


class SemanticChunker(BaseChunker):
    """Chunk based on semantic boundaries (paragraphs, sections)."""

    def __init__(self, max_chunk_size: int = 3000, min_chunk_size: int = 500):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size

    def chunk(self, text: str, **kwargs) -> List[DocumentChunk]:
        """Split text at semantic boundaries."""
        chunks = []
        chunk_id = 0

        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\n+', text)

        current_chunk = []
        current_size = 0
        start_char = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_size = len(para)

            # If single paragraph is too large, split it
            if para_size > self.max_chunk_size:
                # Save current chunk if exists
                if current_chunk:
                    chunk_content = '\n\n'.join(current_chunk)
                    chunks.append(DocumentChunk(
                        chunk_id=chunk_id,
                        content=chunk_content,
                        metadata={"strategy": "semantic"},
                        start_char=start_char,
                        end_char=start_char + len(chunk_content)
                    ))
                    chunk_id += 1
                    current_chunk = []
                    current_size = 0
                    start_char += len(chunk_content) + 2

                # Split large paragraph
                sentences = re.split(r'(?<=[.!?])\s+', para)
                temp_chunk = []
                temp_size = 0

                for sentence in sentences:
                    if temp_size + len(sentence) > self.max_chunk_size:
                        if temp_chunk:
                            chunk_content = ' '.join(temp_chunk)
                            chunks.append(DocumentChunk(
                                chunk_id=chunk_id,
                                content=chunk_content,
                                metadata={"strategy": "semantic", "split": "sentence"},
                                start_char=start_char,
                                end_char=start_char + len(chunk_content)
                            ))
                            chunk_id += 1
                            start_char += len(chunk_content) + 1
                        temp_chunk = [sentence]
                        temp_size = len(sentence)
                    else:
                        temp_chunk.append(sentence)
                        temp_size += len(sentence) + 1

                if temp_chunk:
                    chunk_content = ' '.join(temp_chunk)
                    chunks.append(DocumentChunk(
                        chunk_id=chunk_id,
                        content=chunk_content,
                        metadata={"strategy": "semantic", "split": "sentence"},
                        start_char=start_char,
                        end_char=start_char + len(chunk_content)
                    ))
                    chunk_id += 1
                    start_char += len(chunk_content) + 1

            # Add to current chunk if fits
            elif current_size + para_size <= self.max_chunk_size:
                current_chunk.append(para)
                current_size += para_size + 2  # +2 for \n\n

            # Save current chunk and start new one
            else:
                if current_chunk:
                    chunk_content = '\n\n'.join(current_chunk)
                    chunks.append(DocumentChunk(
                        chunk_id=chunk_id,
                        content=chunk_content,
                        metadata={"strategy": "semantic"},
                        start_char=start_char,
                        end_char=start_char + len(chunk_content)
                    ))
                    chunk_id += 1
                    start_char += len(chunk_content) + 2

                current_chunk = [para]
                current_size = para_size

        # Add remaining chunk
        if current_chunk:
            chunk_content = '\n\n'.join(current_chunk)
            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                content=chunk_content,
                metadata={"strategy": "semantic"},
                start_char=start_char,
                end_char=start_char + len(chunk_content)
            ))

        return chunks


class StructuralChunker(BaseChunker):
    """Chunk based on document structure (sections, headings)."""

    def __init__(self, max_chunk_size: int = 4000):
        self.max_chunk_size = max_chunk_size
        self.section_patterns = [
            r'^#{1,3}\s+(.+)$',  # Markdown headers
            r'^(\d+\.?\s+[A-Z].+)$',  # Numbered sections
            r'^([A-Z][A-Z\s]{2,})$',  # All caps headers
            r'^(Article\s+\d+.*)$',  # Legal articles
            r'^(TITRE\s+[IVX]+.*)$',  # Roman numeral titles
        ]

    def _detect_sections(self, text: str) -> List[Dict[str, Any]]:
        """Detect section boundaries in text."""
        sections = []
        lines = text.split('\n')
        current_section = None
        current_content = []
        current_start = 0

        for i, line in enumerate(lines):
            is_header = False
            header_text = None

            # Check if line matches any section pattern
            for pattern in self.section_patterns:
                match = re.match(pattern, line.strip())
                if match:
                    is_header = True
                    header_text = match.group(1) if match.groups() else line.strip()
                    break

            if is_header:
                # Save previous section
                if current_section:
                    sections.append({
                        'title': current_section,
                        'content': '\n'.join(current_content),
                        'start_line': current_start,
                        'end_line': i - 1
                    })

                # Start new section
                current_section = header_text
                current_content = []
                current_start = i
            else:
                current_content.append(line)

        # Add last section
        if current_section:
            sections.append({
                'title': current_section,
                'content': '\n'.join(current_content),
                'start_line': current_start,
                'end_line': len(lines) - 1
            })
        elif current_content:
            # No sections detected, treat as single section
            sections.append({
                'title': 'Document',
                'content': '\n'.join(current_content),
                'start_line': 0,
                'end_line': len(lines) - 1
            })

        return sections

    def chunk(self, text: str, **kwargs) -> List[DocumentChunk]:
        """Split text based on document structure."""
        chunks = []
        chunk_id = 0
        char_offset = 0

        sections = self._detect_sections(text)

        for section in sections:
            content = section['content'].strip()
            if not content:
                continue

            # If section is too large, split it further
            if len(content) > self.max_chunk_size:
                # Use semantic chunker for large sections
                sub_chunker = SemanticChunker(self.max_chunk_size)
                sub_chunks = sub_chunker.chunk(content)

                for sub_chunk in sub_chunks:
                    chunks.append(DocumentChunk(
                        chunk_id=chunk_id,
                        content=sub_chunk.content,
                        metadata={
                            "strategy": "structural",
                            "section": section['title'],
                            "subsection": True
                        },
                        start_char=char_offset + sub_chunk.start_char,
                        end_char=char_offset + sub_chunk.end_char,
                        section_title=section['title']
                    ))
                    chunk_id += 1
            else:
                # Keep section as single chunk
                chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    content=content,
                    metadata={
                        "strategy": "structural",
                        "section": section['title']
                    },
                    start_char=char_offset,
                    end_char=char_offset + len(content),
                    section_title=section['title']
                ))
                chunk_id += 1

            char_offset += len(section['content']) + len(section['title']) + 2

        return chunks


class SmartChunker:
    """
    Adaptive chunking system that selects strategy based on document characteristics.
    """

    def __init__(self):
        self.chunkers = {
            ChunkingStrategy.FIXED_SIZE: FixedSizeChunker(),
            ChunkingStrategy.SEMANTIC: SemanticChunker(),
            ChunkingStrategy.STRUCTURAL: StructuralChunker()
        }

    def analyze_document(self, text: str) -> Dict[str, Any]:
        """Analyze document characteristics."""
        return {
            'total_chars': len(text),
            'total_words': len(text.split()),
            'estimated_pages': len(text) // 3000,  # Rough estimate
            'has_sections': bool(re.search(r'^#{1,3}\s+', text, re.MULTILINE)),
            'has_numbering': bool(re.search(r'^\d+\.', text, re.MULTILINE)),
            'paragraph_count': len(re.split(r'\n\n+', text))
        }

    def select_strategy(self, text: str) -> ChunkingStrategy:
        """Select best chunking strategy based on document analysis."""
        analysis = self.analyze_document(text)

        # For very small documents, use fixed size
        if analysis['estimated_pages'] < 5:
            return ChunkingStrategy.FIXED_SIZE

        # For structured documents, use structural chunking
        if analysis['has_sections'] or analysis['has_numbering']:
            return ChunkingStrategy.STRUCTURAL

        # For medium documents, use semantic chunking
        if analysis['estimated_pages'] < 50:
            return ChunkingStrategy.SEMANTIC

        # For large documents, use structural if possible, else semantic
        if analysis['has_sections']:
            return ChunkingStrategy.STRUCTURAL
        else:
            return ChunkingStrategy.SEMANTIC

    def chunk(
        self,
        text: str,
        strategy: Optional[ChunkingStrategy] = None,
        **kwargs
    ) -> List[DocumentChunk]:
        """
        Chunk document using specified or auto-selected strategy.

        Args:
            text: Document text to chunk
            strategy: Specific strategy to use (auto-select if None)
            **kwargs: Additional parameters for chunker

        Returns:
            List of document chunks
        """
        if strategy is None:
            strategy = self.select_strategy(text)

        chunker = self.chunkers[strategy]
        chunks = chunker.chunk(text, **kwargs)

        # Add chunk statistics
        for chunk in chunks:
            chunk.metadata['total_chunks'] = len(chunks)
            chunk.metadata['chunk_index'] = chunk.chunk_id

        return chunks

    def chunk_for_model(
        self,
        text: str,
        max_tokens: int = 512,
        model_type: str = "bert"
    ) -> List[DocumentChunk]:
        """
        Chunk specifically for model constraints.

        Args:
            text: Text to chunk
            max_tokens: Maximum tokens per chunk for model
            model_type: Type of model (bert, gpt, etc.)

        Returns:
            List of chunks sized for model
        """
        # Adjust chunk size based on model
        if model_type == "bert":
            # BERT models typically handle 512 tokens
            # ~4 chars per token in French
            max_chars = max_tokens * 4
        elif model_type == "gpt":
            # GPT models can handle more
            max_chars = max_tokens * 4
        else:
            max_chars = 2000  # Default safe size

        # Use appropriate chunker
        if max_chars < 1000:
            chunker = FixedSizeChunker(chunk_size=max_chars, overlap=100)
        else:
            chunker = SemanticChunker(max_chunk_size=max_chars)

        return chunker.chunk(text)