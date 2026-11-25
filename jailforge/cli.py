"""Command-line interface for JailForge."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from .attacks import ATTACK_METHODS
from .config import load_config
from .data import load_benign, load_goals
from .eval import Runner, format_summary_table
from .utils import project_root, resolve_path, write_json


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(project_root() / ".env")
    except ImportError:  # pragma: no cover
        pass


def _apply_model_args(config: dict[str, Any], args: argparse.Namespace) -> None:
    if getattr(args, "provider", None):
        config["model"]["provider"] = args.provider
        os.environ["JAILFORGE_PROVIDER"] = args.provider
    if getattr(args, "model", None):
        config["model"]["model"] = args.model
        os.environ["JAILFORGE_MODEL"] = args.model
    if getattr(args, "base_url", None):
        config["model"]["base_url"] = args.base_url
        os.environ["JAILFORGE_BASE_URL"] = args.base_url


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    _apply_model_args(config, args)
    if args.max_goals is not None:
        config["run"]["max_goals"] = args.max_goals
    if args.methods:
        config["run"]["methods"] = args.methods
    if args.defenses:
        config["run"]["defenses"] = args.defenses
    if args.output_dir:
        config["run"]["output_dir"] = args.output_dir
    if args.seed is not None:
        config["run"]["seed"] = args.seed

    runner = Runner(config)
    total = len(runner.goals) * len(config["run"]["methods"]) * len(config["run"]["defenses"])
    print(
        f"[JailForge] model={runner.model.name} goals={len(runner.goals)} "
        f"methods={len(config['run']['methods'])} defenses={len(config['run']['defenses'])} "
        f"trials≈{total}"
    )
    counter = {"last": -1}

    def progress(done: int, total: int, label: str) -> None:
        step = max(1, total // 10)
        if done == total or done // step != counter["last"]:
            counter["last"] = done // step
            print(f"  {done}/{total} ({done / total * 100:5.1f}%) {label}")

    result = runner.run(measure_fpr=not args.no_fpr, progress=progress)
    print()
    print(format_summary_table(result.summary))
    print()
    print(f"[JailForge] artifacts written to: {result.output_dir}")
    errors = result.summary["overall"]["errors"]
    if errors:
        print(f"[JailForge] warning: {errors} model calls failed", file=sys.stderr)
    return 0


def cmd_evolve(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    _apply_model_args(config, args)
    runner = Runner(config)
    if args.goal_id:
        goals = [goal for goal in runner.goals if goal.id == args.goal_id]
        if not goals:
            print(f"goal id not found: {args.goal_id}", file=sys.stderr)
            return 2
        goal = goals[0]
    else:
        goal = runner.goals[0]

    print(f"[JailForge] evolving for {goal.id}: {goal.behavior}")
    result = runner.evolve(
        goal,
        defense_name=args.defense,
        generations=args.generations,
        population=args.population,
    )
    print(f"\nbest fitness: {result.best_fitness:.3f} (baseline {result.baseline_fitness:.3f})")
    print(f"evaluations: {result.evaluations}, cache hits: {result.cache_hits}")
    print("\nbest prompt:\n")
    print(result.best_prompt)
    print("\nhistory:")
    for row in result.history:
        print(
            f"  gen {row['generation']}: best={row['best_fitness']:.3f} "
            f"mean={row['mean_fitness']:.3f} blocked={row['blocked_ratio']:.2f}"
        )

    out_path = resolve_path(f"results/evolution/{goal.id}_{args.defense}.json")
    write_json(out_path, result.to_dict())
    print(f"\nartifacts written to: {out_path}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    print("JailForge doctor")
    print(f"  project root: {project_root()}")
    print(f"  python: {sys.version.split()[0]}")
    for module in ["requests", "yaml", "pandas", "gradio", "dotenv", "pytest"]:
        try:
            imported = __import__(module)
            version = getattr(imported, "__version__", "ok")
            print(f"  {module}: {version}")
        except Exception:
            print(f"  {module}: MISSING")
    for name in ["JAILFORGE_API_KEY", "JAILFORGE_BASE_URL", "JAILFORGE_MODEL", "OPENAI_API_KEY"]:
        print(f"  env {name}: {'set' if os.getenv(name) else 'missing'}")
    try:
        goals = load_goals()
        benign = load_benign()
        print(f"  goals: {len(goals)}")
        print(f"  benign: {len(benign)}")
    except Exception as exc:
        print(f"  data error: {exc}")
        return 1
    if args.check_model:
        try:
            config = load_config(args.config)
            _apply_model_args(config, args)
            runner = Runner(config)
            print(f"  model: {runner.model.name}")
            print(f"  health: {runner.model.health()}")
        except Exception as exc:
            print(f"  model error: {exc}")
            return 1
    return 0


def cmd_list_attacks(args: argparse.Namespace) -> int:
    for name, method in ATTACK_METHODS.items():
        print(f"{name:22s} {method.family:12s} {method.description}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jailforge",
        description="JailForge: evolutionary jailbreak red-teaming and defense evaluation",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a batch evaluation")
    run.add_argument("--config", default="configs/mock_quick.yaml")
    run.add_argument("--provider", choices=["mock", "openai_compatible"])
    run.add_argument("--model")
    run.add_argument("--base-url", dest="base_url")
    run.add_argument("--max-goals", type=int)
    run.add_argument("--methods", nargs="*")
    run.add_argument("--defenses", nargs="*")
    run.add_argument("--output-dir")
    run.add_argument("--seed", type=int)
    run.add_argument("--no-fpr", action="store_true", help="skip benign false-positive measurement")
    run.set_defaults(func=cmd_run)

    evolve = sub.add_parser("evolve", help="run the evolutionary attacker for one goal")
    evolve.add_argument("--config", default="configs/mock_quick.yaml")
    evolve.add_argument("--provider", choices=["mock", "openai_compatible"])
    evolve.add_argument("--model")
    evolve.add_argument("--base-url", dest="base_url")
    evolve.add_argument("--goal-id")
    evolve.add_argument("--defense", default="layered")
    evolve.add_argument("--generations", type=int)
    evolve.add_argument("--population", type=int)
    evolve.set_defaults(func=cmd_evolve)

    doctor = sub.add_parser("doctor", help="check environment, data and optional model health")
    doctor.add_argument("--config", default="configs/mock_quick.yaml")
    doctor.add_argument("--provider", choices=["mock", "openai_compatible"])
    doctor.add_argument("--model")
    doctor.add_argument("--base-url", dest="base_url")
    doctor.add_argument("--check-model", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    listing = sub.add_parser("list-attacks", help="list available attack strategies")
    listing.set_defaults(func=cmd_list_attacks)

    demo = sub.add_parser("demo", help="launch the Gradio demo")
    demo.set_defaults(func=lambda args: _launch_demo())

    return parser


def _launch_demo() -> int:
    try:
        from app import demo
    except ImportError as exc:
        print(f"cannot import demo: {exc}", file=sys.stderr)
        return 1
    import gradio as gr

    demo.launch(theme=gr.themes.Soft())
    return 0


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
