"""Splits long text into overlapping pieces small enough to embed well.

Typical usage example:

  chunks = Chunker().split(text)
"""

import re

_PARAGRAPH_BREAK = re.compile(r'\n\s*\n')
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+')


class Chunker:
    """Cuts text at paragraph and sentence boundaries into pieces of about a set size.

    Attributes:
        size: The target length of a piece, in characters.
        overlap: How many characters of the previous piece start the next, so an idea split across a boundary is still found.
    """

    def __init__(self, size: int = 900, overlap: int = 150):
        """Creates the chunker.

        Args:
            size (int): The target length of a piece, in characters.
            overlap (int): How many characters of the previous piece start the next.
        """
        self.size = size
        self.overlap = overlap

    def split(self, text: str) -> list[str]:
        """Splits text into pieces.

        Args:
            text (str): The text.

        Returns:
            list[str]: The pieces in order; empty for empty text.
        """
        sentences = []
        for paragraph in _PARAGRAPH_BREAK.split(text):
            cleaned = ' '.join(paragraph.split())
            if not cleaned:
                continue
            for sentence in _SENTENCE_END.split(cleaned):
                while len(sentence) > self.size:
                    sentences.append(sentence[: self.size])
                    sentence = sentence[self.size :]
                if sentence:
                    sentences.append(sentence)
        chunks = []
        current = ''
        for sentence in sentences:
            if current and len(current) + 1 + len(sentence) > self.size:
                chunks.append(current)
                current = current[-self.overlap :] if self.overlap else ''
            current = f'{current} {sentence}'.strip()
        if current:
            chunks.append(current)
        return chunks
