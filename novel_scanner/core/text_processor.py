from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import tiktoken


@dataclass(slots=True)
class TextChunk:
    id: int
    text: str
    token_start: int
    token_end: int
    tokens: int
    metadata: dict = field(default_factory=dict)


class TextSplitter:
    def __init__(self, encoding_name: str = "cl100k_base"):
        self.encoding = tiktoken.get_encoding(encoding_name)

    def split(
        self,
        text: str,
        max_tokens: int,
        overlap: int = 0,
    ) -> List[TextChunk]:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if overlap >= max_tokens:
            raise ValueError("overlap must be smaller than max_tokens")

        token_ids = self.encoding.encode(text)
        total_tokens = len(token_ids)
        if total_tokens <= max_tokens:
            return [
                TextChunk(
                    id=0,
                    text=text,
                    token_start=0,
                    token_end=total_tokens,
                    tokens=total_tokens,
                    metadata={"char_start": 0, "char_end": len(text)},
                )
            ]

        chunks: List[TextChunk] = []
        step = max_tokens - overlap
        start = 0
        chunk_id = 0

        while start < total_tokens:
            end = min(start + max_tokens, total_tokens)
            chunk_tokens = token_ids[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(
                TextChunk(
                    id=chunk_id,
                    text=chunk_text,
                    token_start=start,
                    token_end=end,
                    tokens=len(chunk_tokens),
                    metadata={},
                )
            )
            chunk_id += 1
            start += step

        return chunks

    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))
