import re
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class Chunk:
    """Represents a single text chunk with metadata."""
    section_id: str
    chunk_index: int
    text: str


def split_into_sections(text: str) -> List[str]:
    """
    Splits legal text into sections based on common legal markers like
    'SECTION 1.', numbered laws (e.g., '27001.'), or ALL CAPS headings.
    """
    pattern = r'(?=^\s*(SECTION\s+\d+\.|CHAPTER\s+\d+|[0-9]{4,}\.|[A-Z][A-Z\s]+))'
    sections = re.split(pattern, text, flags=re.M)

    merged = []
    buffer = ""
    for part in sections:
        if not part.strip():
            continue
        if part.strip().startswith(("SECTION", "CHAPTER")) or part.isupper():
            if buffer:
                merged.append(buffer.strip())
            buffer = part
        else:
            buffer += " " + part
    if buffer:
        merged.append(buffer.strip())
    return merged


def chunk_section(section_text: str, section_id: str, max_chars: int = 95000, overlap: int = 2500) -> List[Chunk]:
    """
    Breaks a single section into large overlapping chunks,
    tuned for 128k LLM input windows.
    """
    chunks: List[Chunk] = []
    start = 0
    chunk_idx = 0

    while start < len(section_text):
        end = min(start + max_chars, len(section_text))
        chunk_text = section_text[start:end]

        chunks.append(Chunk(
            section_id=section_id,
            chunk_index=chunk_idx,
            text=chunk_text.strip()
        ))

        if end >= len(section_text):
            break  # finished

        start = end - overlap
        chunk_idx += 1

    return chunks


def chunk_legal_text(text: str, max_chars: int = 95000, overlap: int = 2500) -> List[Dict]:
    """
    Splits legal text into semantically meaningful, size-bounded chunks.

    Returns a list of dicts with:
        - section_id
        - chunk_index
        - text
    """
    sections = split_into_sections(text)
    all_chunks: List[Chunk] = []

    for i, section in enumerate(sections):
        section_id = f"section_{i+1}"
        section_chunks = chunk_section(section, section_id, max_chars, overlap)
        all_chunks.extend(section_chunks)

    return [c.__dict__ for c in all_chunks]
