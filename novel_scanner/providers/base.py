from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class ProviderResponse:
    content: str
    finish_reason: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseProvider(abc.ABC):
    def __init__(
        self,
        name: str,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        context_length: int = 128_000,
        timeout: int = 120,
        rpm_limit: Optional[int] = None,
        max_concurrent: int = 1,
        retry_times: int = 3,
        **kwargs,
    ):
        self.name = name
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.context_length = context_length
        self.timeout = timeout
        self.rpm_limit = rpm_limit
        self.max_concurrent = max_concurrent
        self.retry_times = retry_times
        self.kwargs = kwargs

    @abc.abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> ProviderResponse:
        """发送请求并返回结果"""
        pass

    @abc.abstractmethod
    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        pass

    def get_available_context(self, max_tokens: Optional[int] = None) -> int:
        """获取可用的上下文长度（扣除输出tokens）"""
        output_tokens = max_tokens or 4096
        return max(0, self.context_length - output_tokens)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, model={self.model})"
