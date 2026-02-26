"""Text chunking with LangChain RecursiveCharacterTextSplitter."""

from __future__ import annotations

import re
from typing import Any


def chunk_page(
    url: str,
    title: str,
    markdown_text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[dict[str, Any]]:
    """Split a markdown page into chunks with metadata.

    Each chunk gets: url, title, section_header, chunk_index, text.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""],
    )

    texts = splitter.split_text(markdown_text)
    chunks: list[dict[str, Any]] = []

    for i, text in enumerate(texts):
        section_header = _extract_nearest_heading(markdown_text, text)
        chunks.append(
            {
                "url": url,
                "title": title,
                "section_header": section_header,
                "chunk_index": i,
                "text": text,
            }
        )

    return chunks


def _extract_nearest_heading(full_text: str, chunk_text: str) -> str:
    """Find the nearest markdown heading above the chunk position."""
    chunk_start = full_text.find(chunk_text)
    if chunk_start == -1:
        return ""

    preceding_text = full_text[:chunk_start]
    headings = re.findall(r"^(#{1,4})\s+(.+)$", preceding_text, re.MULTILINE)

    if headings:
        return headings[-1][1].strip()
    return ""
