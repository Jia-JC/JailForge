"""Tiny in-process job manager for long-running batch/evolution tasks."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Job:
    id: str
    kind: str
    status: str = "queued"  # queued | running | done | error
    progress: float = 0.0
    message: str = "排队中"
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, work: Callable[[Callable[[float, str], None]], dict[str, Any]]) -> str:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind)
        with self._lock:
            self._jobs[job.id] = job

        def update(progress: float, message: str) -> None:
            with self._lock:
                job.progress = max(0.0, min(0.99, float(progress)))
                job.message = message

        def runner() -> None:
            with self._lock:
                job.status = "running"
                job.message = "正在运行"
            try:
                result = work(update)
                with self._lock:
                    job.result = result
                    job.status = "done"
                    job.progress = 1.0
                    job.message = "完成"
            except Exception as exc:  # noqa: BLE001 - surfaced to the UI
                with self._lock:
                    job.status = "error"
                    job.error = str(exc)
                    job.message = "失败"
            finally:
                with self._lock:
                    job.finished_at = time.time()

        threading.Thread(target=runner, daemon=True, name=f"jf-job-{job.id}").start()
        return job.id

    def snapshot(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {
                "id": job.id,
                "kind": job.kind,
                "status": job.status,
                "progress": round(job.progress, 4),
                "message": job.message,
                "result": job.result,
                "error": job.error,
                "created_at": job.created_at,
                "finished_at": job.finished_at,
            }
