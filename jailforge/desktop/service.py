"""Service layer used by the desktop HTTP UI.

Everything here returns plain JSON-serialisable dictionaries. The heavy lifting
is delegated to the existing :mod:`jailforge` evaluation pipeline.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from ..attacks import ATTACK_METHODS
from ..config import load_config
from ..data import load_benign, load_goals
from ..defense import DEFENSE_PROFILES
from ..eval import Runner
from ..schema import Goal
from ..utils import write_json
from .jobs import JobManager
from .paths import VERSION, is_frozen, load_env, results_dir, safe_run_name

_ALLOWED_RUN_FILES = {"summary.json", "report.md", "trials.csv", "config.yaml"}
_RUN_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
_EVOLUTION_FILE = re.compile(r"^[A-Za-z0-9_.-]+\.json$")


class ServiceError(RuntimeError):
    """A user-facing error (bad input, missing API key, ...)."""


class JailForgeService:
    def __init__(self) -> None:
        self.env_path = load_env()
        self.jobs = JobManager()
        self.results_dir = results_dir()
        self.results_dir.mkdir(parents=True, exist_ok=True)
        (self.results_dir / "evolution").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #
    def meta(self) -> dict[str, Any]:
        goals = load_goals()
        try:
            benign = load_benign()
        except Exception:
            benign = []
        model = self._model_status()
        return {
            "app": "JailForge",
            "version": VERSION,
            "python": sys.version.split()[0],
            "frozen": is_frozen(),
            "results_dir": str(self.results_dir),
            "env_path": str(self.env_path) if self.env_path else "",
            "model": model,
            "counts": {
                "goals": len(goals),
                "benign": len(benign),
                "attacks": len(ATTACK_METHODS),
                "defenses": len(DEFENSE_PROFILES),
                "categories": len({goal.category for goal in goals}),
            },
            "categories": sorted({goal.category for goal in goals}),
            "attacks": [
                {"name": method.name, "family": method.family, "description": method.description}
                for method in ATTACK_METHODS.values()
            ],
            "defenses": [
                {"name": name, "label": profile["label"], "description": profile["description"]}
                for name, profile in DEFENSE_PROFILES.items()
            ],
            "limits": {
                "max_goals": 32,
                "max_generations": 10,
                "max_population": 20,
            },
            "links": {
                "github": "https://github.com/Jia-JC/JailForge",
                "releases": "https://github.com/Jia-JC/JailForge/releases",
            },
        }

    def goals(self) -> list[dict[str, Any]]:
        return [goal.to_dict() for goal in load_goals()]

    def _model_status(self) -> dict[str, Any]:
        api_key = os.getenv("JAILFORGE_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("JAILFORGE_BASE_URL", "")
        model = os.getenv("JAILFORGE_MODEL", "")
        available = bool(api_key and base_url and model)
        return {
            "mock": True,
            "real_available": available,
            "real_model": model,
            "base_url": base_url,
            "reason": "" if available else "未检测到 JAILFORGE_API_KEY / BASE_URL / MODEL",
        }

    # ------------------------------------------------------------------ #
    # Single test
    # ------------------------------------------------------------------ #
    def single(
        self,
        goal_text: str,
        method: str,
        defense: str,
        provider: str = "mock",
        judge_mode: str = "rule",
    ) -> dict[str, Any]:
        if not goal_text or not goal_text.strip():
            raise ServiceError("请先输入测试目标。")
        runner = self._build_runner(provider, judge_mode, safe_run_name("single"))
        trial = runner.single(goal_text.strip(), method, defense)
        return self._serialize_trial(trial)

    # ------------------------------------------------------------------ #
    # Batch
    # ------------------------------------------------------------------ #
    def start_batch(
        self,
        sample_size: int,
        methods: list[str],
        defenses: list[str],
        provider: str = "mock",
        judge_mode: str = "rule",
    ) -> dict[str, Any]:
        methods = self._validate_methods(methods)
        defenses = self._validate_defenses(defenses)
        sample_size = max(1, min(32, int(sample_size)))
        runner = self._build_runner(provider, judge_mode, safe_run_name("batch"))
        goals = runner.goals[:sample_size]
        run_name = runner.config["run"]["name"]

        def work(update):
            def progress(done: int, total: int, label: str) -> None:
                update(done / max(1, total), f"{done}/{total} · {label}")

            result = runner.run(
                goals=goals,
                methods=methods,
                defenses=defenses,
                progress=progress,
            )
            return self._serialize_run(result)

        job_id = self.jobs.submit("batch", work)
        return {
            "job_id": job_id,
            "run_name": run_name,
            "trials": len(goals) * len(methods) * len(defenses),
        }

    # ------------------------------------------------------------------ #
    # Evolution
    # ------------------------------------------------------------------ #
    def start_evolve(
        self,
        goal_text: str,
        defense: str,
        generations: int,
        population: int,
        provider: str = "mock",
        judge_mode: str = "rule",
    ) -> dict[str, Any]:
        if not goal_text or not goal_text.strip():
            raise ServiceError("请先输入进化目标。")
        generations = max(2, min(10, int(generations)))
        population = max(4, min(20, int(population)))
        runner = self._build_runner(provider, judge_mode, safe_run_name("evolve"))
        goal = Goal(id="adhoc", behavior=goal_text.strip(), category="自定义", source="user")
        run_name = runner.config["run"]["name"]

        def work(update):
            def progress(gen: int, total: int, best: float) -> None:
                update((gen + 1) / max(1, total + 1), f"第 {gen}/{total} 代 · 最佳适应度 {best:.3f}")

            result = runner.evolve(
                goal,
                defense_name=defense,
                generations=generations,
                population=population,
            )
            payload = result.to_dict()
            payload["run_id"] = run_name
            payload["download"] = f"/api/download?run=evolution&file={run_name}.json"
            write_json(self.results_dir / "evolution" / f"{run_name}.json", payload)
            return payload

        job_id = self.jobs.submit("evolve", work)
        return {"job_id": job_id, "run_name": run_name, "generations": generations, "population": population}

    # ------------------------------------------------------------------ #
    # Runs / downloads
    # ------------------------------------------------------------------ #
    def runs(self, limit: int = 12) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        try:
            children = sorted(
                (path for path in self.results_dir.iterdir() if path.is_dir()),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return []
        for path in children:
            summary_path = path / "summary.json"
            if not summary_path.exists():
                continue
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            meta = summary.get("meta", {})
            overall = summary.get("overall", {})
            entries.append(
                {
                    "run_id": path.name,
                    "model": meta.get("model", ""),
                    "provider": meta.get("provider", ""),
                    "timestamp": meta.get("timestamp", ""),
                    "asr": overall.get("asr", 0.0),
                    "n": overall.get("n", 0),
                    "success": overall.get("success", 0),
                    "downloads": {
                        "report": f"/api/download?run={path.name}&file=report.md",
                        "csv": f"/api/download?run={path.name}&file=trials.csv",
                        "summary": f"/api/download?run={path.name}&file=summary.json",
                    },
                }
            )
            if len(entries) >= limit:
                break
        return entries

    def download_path(self, run_id: str, filename: str) -> Path:
        if not _RUN_ID.match(run_id or ""):
            raise ServiceError("非法的运行 ID。")
        if run_id == "evolution":
            if not _EVOLUTION_FILE.match(filename or ""):
                raise ServiceError("非法的文件名。")
            path = (self.results_dir / "evolution" / filename).resolve()
        else:
            if filename not in _ALLOWED_RUN_FILES:
                raise ServiceError("不允许下载该文件。")
            path = (self.results_dir / run_id / filename).resolve()
        root = self.results_dir.resolve()
        if not path.is_relative_to(root):
            raise ServiceError("路径越界。")
        if not path.exists():
            raise ServiceError("文件不存在。")
        return path

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _build_runner(self, provider: str, judge_mode: str, run_name: str) -> Runner:
        if provider not in {"mock", "openai_compatible"}:
            raise ServiceError("未知的模型来源。")
        config = load_config("configs/mock_quick.yaml")
        config["run"]["name"] = run_name
        config["run"]["output_dir"] = str(self.results_dir / run_name)
        config["run"]["cache_path"] = str(self.results_dir / "cache.json")
        config["run"]["max_goals"] = 32
        config["model"]["provider"] = provider
        if provider == "openai_compatible":
            status = self._model_status()
            if not status["real_available"]:
                hint = self.env_path or (Path.home() / ".jailforge" / ".env")
                raise ServiceError(
                    "真实 API 未配置。请在 .env 中填写 JAILFORGE_API_KEY、"
                    "JAILFORGE_BASE_URL、JAILFORGE_MODEL。\n"
                    f"推荐位置：{hint}"
                )
            config["model"]["model"] = status["real_model"]
            config["model"]["base_url"] = status["base_url"]
            config["model"]["api_key_env"] = "JAILFORGE_API_KEY"
            config["judge"]["provider"] = "llm" if judge_mode == "llm" else "rule"
        else:
            config["judge"]["provider"] = "rule"
        return Runner(config)

    def _validate_methods(self, methods: list[str]) -> list[str]:
        cleaned = [name for name in (methods or []) if name in ATTACK_METHODS]
        if not cleaned:
            raise ServiceError("请至少选择一种攻击方法。")
        return cleaned

    def _validate_defenses(self, defenses: list[str]) -> list[str]:
        cleaned = [name for name in (defenses or []) if name in DEFENSE_PROFILES]
        if not cleaned:
            raise ServiceError("请至少选择一种防御配置。")
        return cleaned

    def _serialize_trial(self, trial: Any) -> dict[str, Any]:
        return {
            "record": trial.to_record(),
            "prompt": trial.attack.text,
            "defense": {
                "name": trial.defense,
                "blocked": trial.decision.blocked,
                "stage": trial.decision.stage,
                "reason": trial.decision.reason,
                "scores": trial.decision.scores,
                "system_prompt": (trial.decision.system_prompt or "")[:600],
            },
            "response": trial.response.text,
            "judge": {
                "success": trial.judge.success,
                "score": trial.judge.score,
                "rationale": trial.judge.rationale,
                "name": trial.judge.judge,
                "severity": trial.judge.severity,
                "confidence": trial.judge.confidence,
            },
            "model": trial.response.model,
            "elapsed_ms": round(trial.elapsed_ms, 1),
        }

    def _serialize_run(self, result: Any) -> dict[str, Any]:
        summary = result.summary
        run_id = result.output_dir.name
        preview = [
            {
                "goal_id": trial.goal.id,
                "method": trial.attack.method,
                "defense": trial.defense,
                "blocked": trial.blocked,
                "success": trial.success,
                "judge_score": trial.judge.score,
            }
            for trial in result.trials[:12]
        ]
        return {
            "run_id": run_id,
            "summary": summary,
            "n_trials": len(result.trials),
            "preview": preview,
            "downloads": {
                "report": f"/api/download?run={run_id}&file=report.md",
                "csv": f"/api/download?run={run_id}&file=trials.csv",
                "summary": f"/api/download?run={run_id}&file=summary.json",
            },
        }
