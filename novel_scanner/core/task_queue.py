from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass(slots=True)
class Task:
    id: str
    chunk_id: int
    text: str
    tokens: int
    stage_id: str
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    assigned_provider: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        chunk_id: int,
        text: str,
        tokens: int,
        stage_id: str,
        max_retries: int = 3,
        **metadata,
    ) -> Task:
        return cls(
            id=str(uuid.uuid4()),
            chunk_id=chunk_id,
            text=text,
            tokens=tokens,
            stage_id=stage_id,
            max_retries=max_retries,
            metadata=metadata,
        )


class TaskQueue:
    def __init__(self):
        self._queue: asyncio.Queue[Task] = asyncio.Queue()
        self._pending_tasks: Dict[str, Task] = {}
        self._running_tasks: Dict[str, Task] = {}
        self._completed_tasks: Dict[str, Task] = {}
        self._failed_tasks: Dict[str, Task] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    async def add_task(self, task: Task) -> None:
        async with self._lock:
            if self._closed:
                raise RuntimeError("Cannot add task to closed queue")
            self._pending_tasks[task.id] = task
            await self._queue.put(task)

    async def add_tasks(self, tasks: list[Task]) -> None:
        for task in tasks:
            await self.add_task(task)

    def close(self) -> None:
        self._closed = True

    async def get_task(
        self, min_tokens: Optional[int] = None, max_tokens: Optional[int] = None
    ) -> Optional[Task]:
        while True:
            if self._queue.empty():
                if self._closed:
                    return None
                await asyncio.sleep(0.1)
                continue

            task = await self._queue.get()

            if min_tokens and task.tokens < min_tokens:
                await self._queue.put(task)
                await asyncio.sleep(0.01)
                continue

            if max_tokens and task.tokens > max_tokens:
                await self._queue.put(task)
                await asyncio.sleep(0.01)
                continue

            async with self._lock:
                if task.id in self._pending_tasks:
                    del self._pending_tasks[task.id]
                    task.status = TaskStatus.RUNNING
                    task.started_at = datetime.now()
                    self._running_tasks[task.id] = task
                    return task

            await asyncio.sleep(0.01)

    async def mark_completed(self, task_id: str, result: str) -> None:
        async with self._lock:
            if task_id in self._running_tasks:
                task = self._running_tasks.pop(task_id)
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now()
                self._completed_tasks[task_id] = task

    async def mark_failed(
        self, task_id: str, error: str, retry: bool = True
    ) -> Optional[Task]:
        async with self._lock:
            if task_id not in self._running_tasks:
                return None

            task = self._running_tasks.pop(task_id)
            task.error = error
            task.retry_count += 1

            if retry and task.retry_count < task.max_retries:
                task.status = TaskStatus.RETRYING
                self._pending_tasks[task.id] = task
                await self._queue.put(task)
                return task
            else:
                task.status = TaskStatus.FAILED
                self._failed_tasks[task_id] = task
                return None

    def get_stats(self) -> Dict[str, int]:
        return {
            "pending": len(self._pending_tasks),
            "running": len(self._running_tasks),
            "completed": len(self._completed_tasks),
            "failed": len(self._failed_tasks),
            "total": len(self._pending_tasks)
            + len(self._running_tasks)
            + len(self._completed_tasks)
            + len(self._failed_tasks),
        }

    async def wait_completion(self, timeout: Optional[float] = None) -> bool:
        start = asyncio.get_event_loop().time()
        while True:
            stats = self.get_stats()
            if stats["pending"] == 0 and stats["running"] == 0:
                return True
            if timeout and (asyncio.get_event_loop().time() - start) > timeout:
                return False
            await asyncio.sleep(0.5)

    def get_completed_tasks(self) -> list[Task]:
        return sorted(
            self._completed_tasks.values(), key=lambda t: t.chunk_id
        )

    def get_failed_tasks(self) -> list[Task]:
        return list(self._failed_tasks.values())
