from __future__ import annotations

import asyncio
from typing import Dict, Iterable, List, Optional

from novel_scanner.config.models import ProviderConfig
from novel_scanner.providers import BaseProvider, GeminiProvider, OpenAIProvider


class AIPool:
    def __init__(self):
        self.providers: Dict[str, BaseProvider] = {}
        self.priorities: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    def register_provider(self, config: ProviderConfig) -> None:
        api_key = config.resolve_api_key()
        if not api_key:
            raise ValueError(f"API key not provided for provider {config.name}")

        provider = self._build_provider(config, api_key)
        self.providers[config.name] = provider
        self.priorities[config.name] = config.priority

    def _build_provider(self, config: ProviderConfig, api_key: str) -> BaseProvider:
        provider_type = config.type.lower()
        common_kwargs = dict(
            name=config.name,
            model=config.model,
            api_key=api_key,
            base_url=config.base_url,
            timeout=config.timeout,
            rpm_limit=config.rpm_limit,
            max_concurrent=config.max_concurrent,
        )

        if provider_type == "openai":
            return OpenAIProvider(
                context_length=config.context_length,
                **common_kwargs
            )
        if provider_type == "gemini":
            return GeminiProvider(
                context_length=config.context_length,
                **common_kwargs
            )

        raise ValueError(f"Unsupported provider type: {config.type}")

    def get_provider(self, name: str) -> BaseProvider:
        return self.providers[name]

    def list_providers(self, names: Optional[Iterable[str]] = None) -> List[BaseProvider]:
        if names is None:
            providers = list(self.providers.values())
        else:
            providers = [self.providers[name] for name in names if name in self.providers]

        return sorted(
            providers,
            key=lambda provider: self.priorities.get(provider.name, 100),
        )

    async def execute_with_failover(
        self,
        messages: List[Dict[str, str]],
        stage_config,
        request_options: Optional[Dict[str, Any]] = None,
        required_tokens: int = 0,
    ):
        providers = self.list_providers(stage_config.ai_pool)
        if not providers:
            raise RuntimeError("No providers configured in AI pool")

        allowed_keys = {"temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty", "stop"}
        request_options = request_options or {}
        filtered_options = {
            key: value for key, value in request_options.items() if key in allowed_keys and value is not None
        }

        last_exception: Optional[Exception] = None

        for provider in providers:
            if provider.context_length < required_tokens:
                continue

            retries = stage_config.config.get("retry_times", provider.retry_times)
            for attempt in range(max(1, retries)):
                try:
                    return await provider.complete(
                        messages=messages,
                        **filtered_options,
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    last_exception = exc
                    await asyncio.sleep(min(2 ** attempt, 5))
                    continue

        if last_exception:
            raise last_exception
        raise RuntimeError("No providers available for the task")
