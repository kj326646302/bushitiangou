from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from novel_scanner.config.models import PipelineConfig, ProviderConfig, StageConfig
from novel_scanner.core.ai_pool import AIPool
from novel_scanner.core.pipeline import PipelineEngine


class NovelScanner:
    def __init__(
        self,
        ai_config_path: str | Path,
        pipeline_config_path: str | Path,
        prompts_dir: str | Path,
    ):
        self.ai_config_path = Path(ai_config_path)
        self.pipeline_config_path = Path(pipeline_config_path)
        self.prompts_dir = Path(prompts_dir)

        self.ai_pool = AIPool()
        self._load_ai_config()

        self.pipeline_config = self._load_pipeline_config()
        self.pipeline_engine = PipelineEngine(
            self.ai_pool, self.pipeline_config, self.prompts_dir
        )

    def _load_ai_config(self) -> None:
        with open(self.ai_config_path, encoding="utf-8") as file:
            config_data = yaml.safe_load(file)

        for provider_data in config_data.get("providers", []):
            provider_config = ProviderConfig(
                name=provider_data["name"],
                type=provider_data["type"],
                model=provider_data["model"],
                api_key=provider_data.get("api_key"),
                api_key_env=provider_data.get("api_key_env"),
                base_url=provider_data.get("base_url"),
                context_length=provider_data.get("context_length", 128_000),
                rpm_limit=provider_data.get("rpm_limit"),
                max_concurrent=provider_data.get("max_concurrent", 5),
                priority=provider_data.get("priority", 1),
                retry_times=provider_data.get("retry_times", 3),
                timeout=provider_data.get("timeout", 120),
                metadata=provider_data.get("metadata", {}),
            )
            self.ai_pool.register_provider(provider_config)

    def _load_pipeline_config(self) -> PipelineConfig:
        with open(self.pipeline_config_path, encoding="utf-8") as file:
            config_data = yaml.safe_load(file)

        stages = [
            StageConfig(
                id=stage_data["id"],
                type=stage_data["type"],
                description=stage_data.get("description"),
                prompt=stage_data.get("prompt"),
                inputs=stage_data.get("inputs", []),
                ai_pool=stage_data.get("ai_pool"),
                config=stage_data.get("config", {}),
                parallel=stage_data.get("parallel", True),
            )
            for stage_data in config_data.get("pipeline", {}).get("stages", [])
        ]

        return PipelineConfig(
            name=config_data.get("pipeline", {}).get("name", "default"),
            stages=stages,
            metadata=config_data.get("pipeline", {}).get("metadata", {}),
        )

    async def scan_novel(
        self,
        novel_path: str | Path,
        world_info: Optional[str] = None,
        context_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        novel_path = Path(novel_path)
        with open(novel_path, encoding="utf-8") as file:
            text = file.read()

        result = await self.pipeline_engine.run(text, world_info, context_override)
        return result

    async def scan_text(
        self,
        text: str,
        world_info: Optional[str] = None,
        context_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        result = await self.pipeline_engine.run(text, world_info, context_override)
        return result


def run_scanner(
    novel_path: str | Path,
    ai_config_path: str | Path,
    pipeline_config_path: str | Path,
    prompts_dir: str | Path,
    world_info: Optional[str] = None,
    output_dir: Optional[str | Path] = None,
) -> Dict[str, Any]:
    scanner = NovelScanner(ai_config_path, pipeline_config_path, prompts_dir)
    result = asyncio.run(scanner.scan_novel(novel_path, world_info))

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        score = result.get("score", {}).get("score", 0)
        tags = result.get("score", {}).get("tags", [])
        tags_str = "_".join(tags[:5]) if tags else "未分类"
        
        novel_name = Path(novel_path).stem
        output_filename = f"[{score}分]_[{tags_str}]_{novel_name}.txt"
        output_path = output_dir / output_filename
        
        final_output = result.get("merge") or result.get("score", {}).get("raw_response", "")
        output_path.write_text(str(final_output), encoding="utf-8")

    return result
