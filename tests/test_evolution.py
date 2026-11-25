from jailforge.config import load_config
from jailforge.eval import Runner


def _config(workdir):
    config = load_config("configs/mock_quick.yaml")
    config["run"]["max_goals"] = 1
    config["run"]["methods"] = ["direct"]
    config["run"]["defenses"] = ["none"]
    config["run"]["output_dir"] = str(workdir / "run")
    config["run"]["cache"] = False
    config["run"]["cache_path"] = str(workdir / "cache.json")
    config["evolution"]["generations"] = 2
    config["evolution"]["population"] = 4
    return config


def test_evolution_smoke(workdir):
    runner = Runner(_config(workdir))
    goal = runner.goals[0]
    result = runner.evolve(goal, defense_name="none", generations=2, population=4)
    assert result.goal_id == goal.id
    assert result.best_prompt
    assert len(result.history) >= 2
    assert result.best_fitness >= 0.0
    assert result.evaluations >= 1
