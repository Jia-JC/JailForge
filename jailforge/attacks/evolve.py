"""Fitness-guided evolutionary jailbreak search.

The attacker evolves *prompt framings* against a fixed target model and defense
configuration. Fitness rewards successful jailbreaks and penalises prompts that
are blocked by the defense, so the search is explicitly defense-aware.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from ..schema import Goal
from ..utils import stable_hash
from .mutations import Genome, baseline_genome, crossover, mutate, random_genome


@dataclass
class EvolutionResult:
    goal_id: str
    goal: str
    best_genome: Genome
    best_prompt: str
    best_fitness: float
    baseline_fitness: float
    generations: int
    population: int
    history: list[dict[str, Any]] = field(default_factory=list)
    cache_hits: int = 0
    evaluations: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["best_genome"] = self.best_genome.to_dict()
        return payload


class EvolutionaryAttacker:
    """Genetic search over :class:`Genome` framings for one goal."""

    def __init__(
        self,
        model: Any,
        judge: Any,
        defense: Any,
        config: dict[str, Any] | None = None,
        seed: int = 42,
    ) -> None:
        self.model = model
        self.judge = judge
        self.defense = defense
        self.config = config or {}
        self.rng = random.Random(seed)
        self._cache: dict[str, tuple[float, str, bool, Any, Any]] = {}
        self.cache_hits = 0
        self.evaluations = 0

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #
    def _evaluate(self, genome: Genome, goal: Goal) -> tuple[float, str, bool, Any, Any]:
        prompt = genome.render(goal.behavior)
        key = stable_hash(goal.id, prompt, getattr(self.model, "name", "model"))
        if key in self._cache:
            self.cache_hits += 1
            return self._cache[key]

        self.evaluations += 1
        decision = self.defense.pre(prompt)
        if decision.blocked:
            result = (0.0, prompt, True, None, None)
            self._cache[key] = result
            return result

        try:
            response = self.model.generate(
                _messages(decision.system_prompt, decision.prompt)
            )
            judge_result = self.judge.judge(goal, prompt, response)
            fitness = (1.0 if judge_result.success else 0.0) + 0.25 * max(
                0.0, min(1.0, judge_result.score)
            )
            fitness -= min(0.05, len(prompt) / 20000.0)
        except Exception as exc:  # pragma: no cover - provider errors
            judge_result = None
            response = f"<error: {exc}>"
            fitness = 0.0

        result = (round(fitness, 6), prompt, False, judge_result, response)
        self._cache[key] = result
        return result

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #
    def evolve(
        self,
        goal: Goal,
        generations: int | None = None,
        population_size: int | None = None,
        progress: Callable[[int, int, float], None] | None = None,
    ) -> EvolutionResult:
        generations = int(generations or self.config.get("generations", 6))
        population_size = int(population_size or self.config.get("population", 12))
        elite = max(1, int(self.config.get("elite", 2)))
        mutation_rate = float(self.config.get("mutation_rate", 0.35))
        tournament = max(2, int(self.config.get("tournament", 3)))
        early_stop = bool(self.config.get("early_stop", True))

        population = self._initial_population(population_size)
        scored: list[tuple[float, Genome]] = []
        for genome in population:
            fitness, *_ = self._evaluate(genome, goal)
            scored.append((fitness, genome))
        scored.sort(key=lambda item: item[0], reverse=True)

        baseline_fitness = next(
            (fitness for fitness, genome in scored if genome.signature == baseline_genome().signature),
            0.0,
        )
        history: list[dict[str, Any]] = []

        for generation in range(generations + 1):
            best_fitness = scored[0][0]
            mean_fitness = sum(f for f, _ in scored) / len(scored)
            blocked = 0
            # A blocked prompt has fitness exactly 0 in this design.
            blocked = sum(1 for f, _ in scored if f == 0.0)
            history.append(
                {
                    "generation": generation,
                    "best_fitness": round(best_fitness, 4),
                    "mean_fitness": round(mean_fitness, 4),
                    "blocked_ratio": round(blocked / len(scored), 4),
                    "population": len(scored),
                }
            )
            if progress:
                progress(generation, generations, best_fitness)
            if early_stop and best_fitness >= 1.25:
                break
            if generation == generations:
                break

            next_population: list[Genome] = [genome for _, genome in scored[:elite]]
            seen = {genome.signature for genome in next_population}
            attempts = 0
            while len(next_population) < population_size and attempts < population_size * 20:
                attempts += 1
                parent_a = self._tournament(scored, tournament)
                parent_b = self._tournament(scored, tournament)
                child = crossover(parent_a, parent_b, self.rng)
                if self.rng.random() < mutation_rate:
                    child = mutate(child, self.rng)
                if child.signature in seen:
                    continue
                seen.add(child.signature)
                next_population.append(child)
            while len(next_population) < population_size:
                next_population.append(random_genome(self.rng))

            scored = []
            for genome in next_population:
                fitness, *_ = self._evaluate(genome, goal)
                scored.append((fitness, genome))
            scored.sort(key=lambda item: item[0], reverse=True)

        best_fitness, best_genome = scored[0]
        best_prompt = best_genome.render(goal.behavior)
        return EvolutionResult(
            goal_id=goal.id,
            goal=goal.behavior,
            best_genome=best_genome,
            best_prompt=best_prompt,
            best_fitness=best_fitness,
            baseline_fitness=baseline_fitness,
            generations=generations,
            population=population_size,
            history=history,
            cache_hits=self.cache_hits,
            evaluations=self.evaluations,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _initial_population(self, size: int) -> list[Genome]:
        population = [baseline_genome()]
        seen = {baseline_genome().signature}
        while len(population) < size:
            genome = random_genome(self.rng)
            if genome.signature in seen:
                continue
            seen.add(genome.signature)
            population.append(genome)
        return population

    def _tournament(self, scored: list[tuple[float, Genome]], k: int) -> Genome:
        contenders = self.rng.sample(scored, k=min(k, len(scored)))
        return max(contenders, key=lambda item: item[0])[1]


def _messages(system_prompt: str | None, user_prompt: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    return messages
