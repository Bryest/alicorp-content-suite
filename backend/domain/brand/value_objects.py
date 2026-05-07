"""
Value objects for the Brand context.

Value objects are immutable, identity-less, and self-validating. They
encode the *rules* of the domain — e.g. forbidden words must be lowercase
strings, sections must be one of a fixed set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class BrandSection(str, Enum):
    """The five canonical sections of every brand manual."""

    TONE = "TONE"
    AUDIENCE = "AUDIENCE"
    FORBIDDEN = "FORBIDDEN"
    VISUAL = "VISUAL"
    MESSAGING = "MESSAGING"

    @classmethod
    def all(cls) -> list["BrandSection"]:
        return list(cls)


@dataclass(frozen=True)
class BrandTone:
    """Tone of voice — short, human-readable description."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value.strip()) < 3:
            raise ValueError("BrandTone must be at least 3 characters")


@dataclass(frozen=True)
class BrandAudience:
    """Target audience descriptor."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value.strip()) < 3:
            raise ValueError("BrandAudience must be at least 3 characters")


@dataclass(frozen=True)
class ForbiddenWords:
    """
    A normalized set of words the brand prohibits.

    Stored lowercase and trimmed so that conflict detection is case-insensitive.
    """

    words: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_iterable(cls, raw: Iterable[str] | None) -> "ForbiddenWords":
        if not raw:
            return cls(frozenset())
        cleaned = {w.strip().lower() for w in raw if w and w.strip()}
        return cls(frozenset(cleaned))

    def contains(self, text: str) -> list[str]:
        """Return the list of forbidden words found in `text` (lowercase)."""
        if not text:
            return []
        lower = text.lower()
        return sorted(w for w in self.words if w in lower)

    def __iter__(self):
        return iter(sorted(self.words))

    def __len__(self) -> int:
        return len(self.words)
