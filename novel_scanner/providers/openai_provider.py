from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

import tiktoken
from openai import AsyncOpenAI

from novel_scanner.providers.base import BaseProvider, ProviderResponse


class OpenAIProvider(BaseProvider):
    def __init__(
        self,
        name: str,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        timeout: int = 120,
        rpm_limit: Optional[int] = None,
        max_concurrent: int = 5,
        context_length: int = 128_000,
        **kwargs,
    ):
        super().__init__(
            name=name,
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            context_length=context_length,
            rpm_limit=rpm_limit,
            max_concurrent=max_concurrent,
            **kwargs,
        )
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        try:
            self._encoder = tiktoken.encoding_for_model(model)
        except KeyError:
            self._encoder = tiktoken.get_encoding("cl100k_base")
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._last_request_times: List[float] = []
        self._rpm_lock = asyncio.Lock()

    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> ProviderResponse:
        async with self._semaphore:
            await self._respect_rpm_limit()
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                stop=stop,
                timeout=self.timeout,
                **kwargs,
            )

        choice = response.choices[0]
        usage = response.usage
        return ProviderResponse(
            content=choice.message.content or "",
            finish_reason=choice.finish_reason,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            model=response.model,
            metadata={"raw_response": response.model_dump(mode="json")},
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
        return len(self._encoder.encode(text))
