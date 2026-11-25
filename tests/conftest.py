import shutil
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TESTRUNS = ROOT / ".testruns"


@pytest.fixture
def workdir():
    """Workspace-local temp directory.

    The Windows sandbox denies listing some system temp directories, so tests
    avoid pytest's tmp_path plugin and clean up their own directory.
    """
    path = TESTRUNS / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
