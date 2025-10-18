from __future__ import annotations

import os

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class ProviderConfig:
    name: str
    type: str
    model: str
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    context_length: int = 128_000
    rpm_limit: Optional[int] = None
    max_concurrent: int = 1
    priority: int = 1
    retry_times: int = 3
    timeout: int = 120
    metadata: Dict[str, Any] = field(default_factory=dict)

    def resolve_api_key(self) -> Optional[str]:
        if self.api_key:
            return self.api_key
        if self.api_key_env:
            return os.environ.get(self.api_key_env)
        return None


@dataclass(slots=True)
class StageConfig:
    id: str
    type: str
    description: Optional[str] = None
    prompt: Optional[str] = None
    inputs: List[str] = field(default_factory=list)
    ai_pool: Optional[List[str]] = None
    config: Dict[str, Any] = field(default_factory=dict)
    parallel: bool = True


@dataclass(slots=True)
class PipelineConfig:
    name: str
    stages: List[StageConfig] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
