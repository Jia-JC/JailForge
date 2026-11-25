"""Batch evaluation runner."""

from __future__ import annotations

import copy
import csv
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from ..attacks import ATTACK_METHODS, EvolutionaryAttacker, get_attack
from ..config import resolve_model_settings, save_config
from ..data import load_benign, load_goals
from ..defense import DEFENSE_PROFILES, build_defense
from ..judge import build_judge
from ..models import BaseLLM, build_model
from ..schema import AttackPrompt, DefenseDecision, Goal, JudgeResult, ModelResponse, Trial
from ..utils import now_iso, resolve_path, stable_hash
from .cache import ResponseCache
from .metrics import summarize

FIELD_ORDER = [
    "goal_id",
    "goal",
    "category",
    "method",
    "attack_family",
    "defense",
    "blocked",
    "block_stage",
    "block_reason",
    "output_blocked",
    "output_reason",
    "prompt",
    "response",
    "model",
    "error",
    "judge_success",
    "judge_score",
    "judge_rationale",
    "judge_name",
    "valid",
    "success",
    "latency_ms",
    "elapsed_ms",
    "cached",
]


@dataclass
class RunResult:
    trials: list[Trial]
    summary: dict[str, Any]
    output_dir: Path
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "output_dir": str(self.output_dir),
            "n_trials": len(self.trials),
        }


class Runner:
    def __init__(
        self,
        config: dict[str, Any],
        model: BaseLLM | None = None,
        judge: Any | None = None,
    ) -> None:
        self.config = config
        self.model_settings = resolve_model_settings(config)
        self.model = model or build_model(self.model_settings)
        self.judge = judge or build_judge(config.get("judge", {}), self.model)
        self.seed = int(config.get("run", {}).get("seed", 42))
        data_cfg = config.get("data", {})
        self.goals: list[Goal] = load_goals(
            data_cfg.get("path"),
            max_goals=config.get("run", {}).get("max_goals"),
        )
        self.attack_registry = ATTACK_METHODS
        defense_cfg = config.get("defense", {})
        self.defenses = {
            name: build_defense(name, defense_cfg) for name in DEFENSE_PROFILES
        }
        run_cfg = config.get("run", {})
        cache_path = resolve_path(run_cfg.get("cache_path", "results/cache.json"))
        self.cache = ResponseCache(
            cache_path, enabled=bool(run_cfg.get("cache", True))
        )

    # ------------------------------------------------------------------ #
    # Batch evaluation
    # ------------------------------------------------------------------ #
    def run(
        self,
        goals: Iterable[Goal] | None = None,
        methods: list[str] | None = None,
        defenses: list[str] | None = None,
        measure_fpr: bool = True,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> RunResult:
        goals = list(goals if goals is not None else self.goals)
        methods = methods or list(self.config.get("run", {}).get("methods", []))
        defenses = defenses or list(self.config.get("run", {}).get("defenses", []))
        methods = [m for m in methods if m in self.attack_registry]
        defenses = [d for d in defenses if d in self.defenses]
        if not goals:
            raise ValueError("no goals selected")
        if not methods:
            raise ValueError("no valid attack methods selected")
        if not defenses:
            raise ValueError("no valid defense profiles selected")

        total = len(goals) * len(methods) * len(defenses)
        done = 0
        trials: list[Trial] = []
        for goal in goals:
            for method_name in methods:
                method = get_attack(self.attack_registry, method_name)
                rng = random.Random(int(stable_hash(self.seed, goal.id, method_name), 16))
                attack = method.generate(goal, rng)
                for defense_name in defenses:
                    trial = self._run_one(goal, attack, defense_name)
                    trials.append(trial)
                    done += 1
                    if progress:
                        progress(done, total, f"{goal.id} / {method_name} / {defense_name}")

        fpr = self.measure_fpr(defenses) if measure_fpr else {}
        summary = summarize(
            trials,
            fpr=fpr,
            meta={
                "timestamp": now_iso(),
                "model": getattr(self.model, "name", "unknown"),
                "provider": self.model_settings.get("provider", ""),
                "seed": self.seed,
                "n_goals": len(goals),
                "methods": methods,
                "defenses": defenses,
            },
        )
        output_dir = self._save(trials, summary)
        self.cache.save()
        return RunResult(trials=trials, summary=summary, output_dir=output_dir, config=self.config)

    def _run_one(self, goal: Goal, attack: AttackPrompt, defense_name: str) -> Trial:
        start = time.perf_counter()
        defense = self.defenses[defense_name]
        decision = defense.pre(attack.text)

        if decision.blocked:
            response = ModelResponse(text="", model=getattr(self.model, "name", "unknown"))
            judge = JudgeResult(
                success=False,
                score=0.0,
                rationale=f"输入过滤命中：{decision.reason}",
                judge="input_filter",
                severity=0,
                confidence=1.0,
            )
            return Trial(
                goal=goal,
                attack=attack,
                defense=defense_name,
                decision=decision,
                response=response,
                judge=judge,
                elapsed_ms=(time.perf_counter() - start) * 1000,
            )

        response = self._generate(decision)
        output_blocked = False
        output_reason = ""
        if response.error:
            judge = JudgeResult(
                success=False,
                score=0.0,
                rationale=f"模型调用失败：{response.error}",
                judge="error",
                severity=0,
                confidence=1.0,
            )
        else:
            post = defense.post(response.text)
            output_blocked = post.blocked
            output_reason = post.reason
            if post.blocked:
                judge = JudgeResult(
                    success=False,
                    score=0.0,
                    rationale=f"输出过滤命中：{post.reason}",
                    judge="output_filter",
                    severity=0,
                    confidence=1.0,
                )
            else:
                judge = self.judge.judge(goal, attack.text, response.text)

        return Trial(
            goal=goal,
            attack=attack,
            defense=defense_name,
            decision=decision,
            response=response,
            judge=judge,
            elapsed_ms=(time.perf_counter() - start) * 1000,
            output_blocked=output_blocked,
            output_reason=output_reason,
        )

    def _generate(self, decision: DefenseDecision) -> ModelResponse:
        messages: list[dict[str, str]] = []
        if decision.system_prompt:
            messages.append({"role": "system", "content": decision.system_prompt})
        messages.append({"role": "user", "content": decision.prompt})
        key = stable_hash(getattr(self.model, "name", "model"), messages)
        cached = self.cache.get(key)
        if cached is not None:
            return ModelResponse(
                text=cached,
                model=getattr(self.model, "name", "unknown"),
                latency_ms=0.0,
                cached=True,
            )
        started = time.perf_counter()
        try:
            text = self.model.generate(messages)
        except Exception as exc:  # pragma: no cover - provider dependent
            return ModelResponse(
                text="",
                model=getattr(self.model, "name", "unknown"),
                latency_ms=(time.perf_counter() - started) * 1000,
                error=str(exc),
            )
        latency = (time.perf_counter() - started) * 1000
        self.cache.set(key, text)
        return ModelResponse(
            text=text,
            model=getattr(self.model, "name", "unknown"),
            latency_ms=latency,
            cached=False,
        )

    # ------------------------------------------------------------------ #
    # False-positive rate on benign prompts
    # ------------------------------------------------------------------ #
    def measure_fpr(self, defenses: list[str]) -> dict[str, Any]:
        data_cfg = self.config.get("data", {})
        try:
            benign = load_benign(data_cfg.get("benign_path"))
        except FileNotFoundError:
            return {}
        result: dict[str, Any] = {}
        for name in defenses:
            defense = self.defenses[name]
            blocked = [prompt for prompt in benign if defense.pre(prompt).blocked]
            result[name] = {
                "n": len(benign),
                "blocked": len(blocked),
                "fpr": round(len(blocked) / len(benign), 4) if benign else 0.0,
                "examples": blocked[:3],
            }
        return result

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def _save(self, trials: list[Trial], summary: dict[str, Any]) -> Path:
        run_cfg = self.config.get("run", {})
        output_dir = resolve_path(run_cfg.get("output_dir", "results/run"))
        output_dir.mkdir(parents=True, exist_ok=True)
        records = [trial.to_record() for trial in trials]

        (output_dir / "trials.jsonl").write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in records) + "\n",
            encoding="utf-8",
        )

        (output_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if records:
            with (output_dir / "trials.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELD_ORDER, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(records)
        sanitized = copy.deepcopy(self.config)
        sanitized.get("model", {}).pop("api_key", None)
        save_config(sanitized, output_dir / "config.yaml")

        from ..report import render_run_report

        report = render_run_report(
            summary=summary,
            config=self.config,
            trials=trials,
            output_dir=output_dir,
        )
        (output_dir / "report.md").write_text(report, encoding="utf-8")
        return output_dir

    # ------------------------------------------------------------------ #
    # Convenience helpers
    # ------------------------------------------------------------------ #
    def single(self, goal_text: str, method: str, defense_name: str) -> Trial:
        goal = Goal(
            id="adhoc",
            behavior=goal_text,
            category="自定义",
            source="user",
        )
        method_obj = get_attack(self.attack_registry, method)
        rng = random.Random(int(stable_hash(goal_text, method), 16))
        attack = method_obj.generate(goal, rng)
        return self._run_one(goal, attack, defense_name)

    def evolve(
        self,
        goal: Goal,
        defense_name: str = "layered",
        generations: int | None = None,
        population: int | None = None,
    ):
        defense = self.defenses[defense_name]
        evolver = EvolutionaryAttacker(
            model=self.model,
            judge=self.judge,
            defense=defense,
            config=self.config.get("evolution", {}),
            seed=self.seed,
        )
        result = evolver.evolve(goal, generations=generations, population_size=population)
        self.cache.save()
        return result
