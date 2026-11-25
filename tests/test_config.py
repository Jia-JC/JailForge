from jailforge.attacks import ATTACK_METHODS
from jailforge.config import apply_overrides, expand_env, load_config
from jailforge.data import load_goals


def test_default_config_loads():
    config = load_config("configs/mock_quick.yaml")
    assert config["model"]["provider"] == "mock"
    assert "direct" in config["run"]["methods"]


def test_env_expansion(monkeypatch):
    monkeypatch.setenv("JAILFORGE_TEST_VALUE", "hello")
    expanded = expand_env({"a": "${JAILFORGE_TEST_VALUE}", "b": ["${MISSING_VALUE}"]})
    assert expanded["a"] == "hello"
    assert expanded["b"] == [""]


def test_apply_overrides():
    config = load_config("configs/mock_quick.yaml")
    updated = apply_overrides(config, **{"run.seed": 7, "model.provider": "mock"})
    assert updated["run"]["seed"] == 7
    assert updated["model"]["provider"] == "mock"


def test_goal_dataset_is_well_formed():
    goals = load_goals()
    assert len(goals) >= 24
    assert len({goal.id for goal in goals}) == len(goals)
    assert all(goal.behavior and goal.category for goal in goals)
    assert all(name in ATTACK_METHODS for name in ["direct", "role_play", "base64"])
