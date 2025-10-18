from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from jinja2 import Template


@dataclass(slots=True)
class PromptTemplate:
    name: str
    system_prompt: Optional[str]
    user_prompt: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass(slots=True)
class RenderedPrompt:
    messages: list[dict[str, str]]
    metadata: Dict[str, Any]


class TemplateEngine:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def load(self, template_path: str | Path) -> PromptTemplate:
        path = self._resolve_path(template_path)
        content = path.read_text(encoding="utf-8")
        data = self._parse_template_content(content, path.suffix)
        return PromptTemplate(
            name=data.get("name", path.stem),
            system_prompt=data.get("system_prompt") or data.get("system"),
            user_prompt=data.get("user_prompt") or data.get("user"),
            description=data.get("description"),
            metadata=data.get("metadata", {}),
        )

    def render(
        self,
        template: PromptTemplate,
        variables: Dict[str, Any],
        world_info: Optional[str] = None,
    ) -> RenderedPrompt:
        metadata = dict(template.metadata or {})
        metadata.update({k: v for k, v in variables.items() if k.startswith("meta_")})

        render_ctx = dict(variables)
        if world_info:
            render_ctx.setdefault("world_info", world_info)

        messages: list[dict[str, str]] = []
        if template.system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": self._render_text(template.system_prompt, render_ctx),
                }
            )
        user_prompt = self._render_text(template.user_prompt, render_ctx)
        messages.append({"role": "user", "content": user_prompt})

        return RenderedPrompt(messages=messages, metadata=metadata)

    def _resolve_path(self, template_path: str | Path) -> Path:
        path = Path(template_path)
        if not path.is_absolute():
            path = self.base_dir / path
        return path

    @staticmethod
    def _parse_template_content(content: str, suffix: str) -> Dict[str, Any]:
        if suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(content) or {}
        if suffix.lower() == ".json":
            return json.loads(content)
        raise ValueError(f"Unsupported template format: {suffix}")

    @staticmethod
    def _render_text(template_str: str, variables: Dict[str, Any]) -> str:
        tmpl = Template(template_str, autoescape=False)
        return tmpl.render(**variables)
