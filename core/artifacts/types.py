# core/artifacts/types.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


ArtifactKind = Literal["markdown", "image", "file", "json"]


@dataclass
class ArtifactRef:
    kind: ArtifactKind
    name: str
    path: str
    mime_type: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


EventLevel = Literal["info", "warning", "error"]
EventType = Literal["step_start", "step_end", "log", "metric"]


@dataclass
class AgentEvent:
    type: EventType
    name: str
    message: str = ""
    level: EventLevel = "info"
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    text: str
    artifacts: List[ArtifactRef] = field(default_factory=list)
    events: List[AgentEvent] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
