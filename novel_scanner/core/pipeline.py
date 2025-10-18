from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from novel_scanner.config.models import PipelineConfig, StageConfig
from novel_scanner.core.ai_pool import AIPool
from novel_scanner.core.task_queue import Task, TaskQueue
from novel_scanner.core.text_processor import TextChunk, TextSplitter
from novel_scanner.prompts.template_engine import TemplateEngine


class PipelineEngine:
    def __init__(
        self,
        ai_pool: AIPool,
        pipeline_config: PipelineConfig,
        prompts_dir: Path,
    ):
        self.ai_pool = ai_pool
        self.pipeline_config = pipeline_config
        self.template_engine = TemplateEngine(prompts_dir)
        self.stage_outputs: Dict[str, Any] = {}

    async def run(
        self,
        text: str,
        world_info: Optional[str] = None,
        context_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        self.stage_outputs.clear()

        for stage_config in self.pipeline_config.stages:
            if stage_config.type == "preprocess":
                output = await self._run_preprocess_stage(
                    stage_config, text, context_override
                )
            elif stage_config.type == "process":
                output = await self._run_process_stage(
                    stage_config, world_info
                )
            elif stage_config.type == "aggregate":
                output = await self._run_aggregate_stage(stage_config)
            elif stage_config.type == "score":
                output = await self._run_score_stage(stage_config, world_info)
            else:
                raise ValueError(f"Unknown stage type: {stage_config.type}")

            self.stage_outputs[stage_config.id] = output

        return self.stage_outputs

    async def _run_preprocess_stage(
        self, stage_config: StageConfig, text: str, context_override: Optional[int]
    ) -> List[TextChunk]:
        overlap = stage_config.config.get("chunk_overlap", 0)
        min_chunk_size = stage_config.config.get("min_chunk_size", 10_000)

        providers = self.ai_pool.list_providers(stage_config.ai_pool)
        if not providers:
            providers = self.ai_pool.list_providers()

        max_context = max(
            provider.get_available_context() for provider in providers
        )
        if context_override:
            max_context = min(max_context, context_override)

        chunk_size = max(min_chunk_size, max_context)
        splitter = TextSplitter()
        chunks = splitter.split(text, max_tokens=chunk_size, overlap=overlap)

        return chunks

    async def _run_process_stage(
        self, stage_config: StageConfig, world_info: Optional[str]
    ) -> List[str]:
        inputs = self._resolve_inputs(stage_config.inputs)
        if not inputs or not inputs[0]:
            return []

        chunks = inputs[0]
        if not isinstance(chunks, list):
            chunks = [chunks]

        if not stage_config.prompt:
            raise ValueError(f"Process stage '{stage_config.id}' requires a prompt template")
        template = self.template_engine.load(stage_config.prompt)

        queue = TaskQueue()
        tasks = [
            Task.create(
                chunk_id=chunk.id if isinstance(chunk, TextChunk) else idx,
                text=chunk.text if isinstance(chunk, TextChunk) else str(chunk),
                tokens=chunk.tokens if isinstance(chunk, TextChunk) else 0,
                stage_id=stage_config.id,
                max_retries=stage_config.config.get("max_retries", 3),
            )
            for idx, chunk in enumerate(chunks)
        ]
        await queue.add_tasks(tasks)
        queue.close()

        request_options = self._extract_request_options(stage_config)
        max_concurrent = stage_config.config.get("max_concurrent", 5)
        workers = [
            self._process_worker(queue, template, stage_config, world_info, request_options)
            for _ in range(max(1, max_concurrent))
        ]
        await asyncio.gather(*workers)

        completed = queue.get_completed_tasks()
        return [task.result for task in completed if task.result is not None]

    async def _process_worker(
        self,
        queue: TaskQueue,
        template,
        stage_config: StageConfig,
        world_info: Optional[str],
        request_options: Dict[str, Any],
    ) -> None:
        while True:
            task = await queue.get_task()
            if task is None:
                break

            try:
                rendered = self.template_engine.render(
                    template,
                    {"text": task.text, "chunk_id": task.chunk_id},
                    world_info,
                )
                response = await self.ai_pool.execute_with_failover(
                    messages=rendered.messages,
                    stage_config=stage_config,
                    required_tokens=task.tokens,
                    request_options=request_options,
                )
                await queue.mark_completed(task.id, response.content)
            except Exception as exc:  # pylint: disable=broad-except
                await queue.mark_failed(task.id, str(exc))

    async def _run_aggregate_stage(self, stage_config: StageConfig) -> str:
        inputs = self._resolve_inputs(stage_config.inputs)
        strategy = stage_config.config.get("strategy", "concat")

        all_results = []
        for input_data in inputs:
            if isinstance(input_data, list):
                all_results.extend([str(item) for item in input_data])
            else:
                all_results.append(str(input_data))

        if strategy == "concat":
            separator = stage_config.config.get("separator", "\n\n---\n\n")
            return separator.join(all_results)

        raise ValueError(f"Unknown aggregation strategy: {strategy}")

    async def _run_score_stage(
        self, stage_config: StageConfig, world_info: Optional[str]
    ) -> Dict[str, Any]:
        inputs = self._resolve_inputs(stage_config.inputs)
        if not inputs or not inputs[0]:
            return {"score": 0, "tags": [], "raw_response": ""}

        text = inputs[0] if isinstance(inputs[0], str) else str(inputs[0])
        if not stage_config.prompt:
            raise ValueError(f"Score stage '{stage_config.id}' requires a prompt template")
        template = self.template_engine.load(stage_config.prompt)
        rendered = self.template_engine.render(template, {"text": text}, world_info)

        request_options = self._extract_request_options(stage_config)
        response = await self.ai_pool.execute_with_failover(
            messages=rendered.messages,
            stage_config=stage_config,
            request_options=request_options,
        )

        return self._parse_score_response(response.content, stage_config)

    def _resolve_inputs(self, input_ids: List[str]) -> List[Any]:
        return [self.stage_outputs.get(input_id) for input_id in input_ids]

    @staticmethod
    def _extract_request_options(stage_config: StageConfig) -> Dict[str, Any]:
        return {
            "temperature": stage_config.config.get("temperature", 0.7),
            "max_tokens": stage_config.config.get("max_tokens"),
            "top_p": stage_config.config.get("top_p"),
            "frequency_penalty": stage_config.config.get("frequency_penalty"),
            "presence_penalty": stage_config.config.get("presence_penalty"),
            "stop": stage_config.config.get("stop"),
        }

    @staticmethod
    def _parse_score_response(content: str, stage_config: StageConfig) -> Dict[str, Any]:
        import re

        score_match = re.search(r"(?:score|评分)[:：\s]*(\d+)", content, re.IGNORECASE)
        score = int(score_match.group(1)) if score_match else 0

        tag_patterns = [
            r"(?:tags|标签)[:：\s]*\[([^\]]+)\]",
            r"(?:tags|标签)[:：\s]*([^,\n]+(?:,\s*[^,\n]+)*)",
        ]
        tags = []
        for pattern in tag_patterns:
            tag_match = re.search(pattern, content, re.IGNORECASE)
            if tag_match:
                tags_str = tag_match.group(1)
                tags = [tag.strip() for tag in re.split(r"[,，]", tags_str) if tag.strip()]
                break

        return {"score": score, "tags": tags, "raw_response": content}
