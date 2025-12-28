from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPolicy:
    primary: str
    fallback: str

    def all(self) -> list[str]:
        return [self.primary, self.fallback]
