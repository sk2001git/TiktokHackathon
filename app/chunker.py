# chunker.py (Final Version with Overlap)

from typing import List, Dict
from dataclasses import dataclass

@dataclass
class Chunk:
    """Represents a single text chunk with metadata."""
    section_id: str
    chunk_index: int
    text: str

def chunk_legal_text(text: str, max_chars: int = 95000, overlap: int = 10000) -> List[Dict]:
    """
    Splits a large text into overlapping, size-bounded chunks using a sliding window.
    This version ignores semantic sections and only splits by character count.

    Returns a list of dicts with:
        - section_id (a generic name)
        - chunk_index
        - text
    """
    # Add a safety check to prevent infinite loops
    if overlap >= max_chars:
        raise ValueError("Overlap cannot be greater than or equal to max_chars.")

    chunks: List[Chunk] = []
    start = 0
    chunk_idx = 0
    section_id = "full_doc_overlap"  # A generic ID for the whole document

    while start < len(text):
        # Determine the end of the current chunk
        end = min(start + max_chars, len(text))
        chunk_text = text[start:end]

        # Add the new chunk to our list
        chunks.append(Chunk(
            section_id=section_id,
            chunk_index=chunk_idx,
            text=chunk_text.strip()
        ))

        # If this chunk has reached the end of the text, we're done.
        if end >= len(text):
            break

        # Move the start position for the next chunk. This creates the overlap.
        start = end - overlap
        chunk_idx += 1
    
    # Return the list of chunks as dictionaries
    return [c.__dict__ for c in chunks]