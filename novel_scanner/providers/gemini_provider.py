from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

from app.services.gemini import GeminiClient
from app.models.schemas import ChatCompletionRequest
from novel_scanner.providers.base import BaseProvider, ProviderResponse


class GeminiProvider(BaseProvider):
    def __init__(
        self,
        name: str,
        model: str,
        api_key: str,
        context_length: int = 1_000_000,
        timeout: int = 120,
        rpm_limit: Optional[int] = None,
        max_concurrent: int = 10,
    ):
        super().__init__(
            name=name,
            model=model,
            api_key=api_key,
            context_length=context_length,
            timeout=timeout,
            rpm_limit=rpm_limit,
            max_concurrent=max_concurrent,
        )
        self.client = GeminiClient(api_key=api_key)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._last_request_times: List[float] = []
        self._rpm_lock = asyncio.Lock()

    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> ProviderResponse:
        async with self._semaphore:
            await self._respect_rpm_limit()
            
            request = ChatCompletionRequest(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )

            contents, safety_settings, system_instruction = self.client.convert_messages(
                messages, use_system_prompt=True, model=self.model
            )

            response = await self.client.complete_chat(
                request, contents, safety_settings, system_instruction
            )

        return ProviderResponse(
            content=response.text,
            finish_reason=response.finish_reason,
            prompt_tokens=response.prompt_token_count or 0,
            completion_tokens=response.candidates_token_count or 0,
            total_tokens=response.total_token_count or 0,
            model=response.model,
            metadata={"raw_response": response.data},
        )

    async def _respect_rpm_limit(self) -> None:
        if not self.rpm_limit:
            return

        import time

        async with self._rpm_lock:
            current_time = time.monotonic()
            window_start = current_time - 60
            self._last_request_times = [
                t for t in self._last_request_times if t >= window_start
            ]
            if len(self._last_request_times) >= self.rpm_limit:
                sleep_time = 60 - (current_time - self._last_request_times[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            self._last_request_times.append(time.monotonic())

    def count_tokens(self, text: str) -> int:
        return len(text) // 4
