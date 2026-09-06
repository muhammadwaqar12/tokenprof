import os
import subprocess
import sys

import pytest

from tokenprof.record import SHIM, record


def test_record_requires_a_command():
    with pytest.raises(ValueError, match="nothing to run"):
        record([], "out.jsonl")


def test_missing_command_is_a_clean_error(tmp_path):
    with pytest.raises(SystemExit, match="command not found"):
        record(["definitely-not-a-real-binary-xyz"], str(tmp_path / "o.jsonl"))


def test_shim_is_valid_python():
    compile(SHIM, "sitecustomize.py", "exec")


def test_shim_never_raises_without_the_sdks(tmp_path):
    # The shim runs at interpreter startup inside someone else's program. If
    # it can throw, it breaks their app rather than profiling it.
    shim = tmp_path / "sitecustomize.py"
    shim.write_text(SHIM)
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    env.pop("TOKENPROF_OUT", None)
    proc = subprocess.run(
        [sys.executable, "-c", "print('app ran')"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "app ran" in proc.stdout


def test_record_captures_a_patched_call(tmp_path):
    """End to end with a stub SDK that mimics the real client shape."""
    pkg = tmp_path / "openai" / "resources" / "chat"
    pkg.mkdir(parents=True)
    (tmp_path / "openai" / "__init__.py").write_text("from . import resources\n")
    (tmp_path / "openai" / "resources" / "__init__.py").write_text("from . import chat\n")
    (tmp_path / "openai" / "resources" / "chat" / "__init__.py").write_text(
        "from . import completions\n"
    )
    (pkg / "completions.py").write_text(
        "class Completions:\n"
        "    def create(self, **kw):\n"
        "        return kw\n"
        "class AsyncCompletions(Completions):\n"
        "    pass\n"
    )
    app = tmp_path / "app.py"
    app.write_text(
        "from openai.resources.chat.completions import Completions\n"
        "Completions().create(model='gpt-4o', messages=[{'role':'user','content':'hi'}])\n"
    )
    out = tmp_path / "captured.jsonl"

    env_path = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = str(tmp_path) + (os.pathsep + env_path if env_path else "")
    try:
        code = record([sys.executable, str(app)], str(out))
    finally:
        if env_path:
            os.environ["PYTHONPATH"] = env_path
        else:
            os.environ.pop("PYTHONPATH", None)

    assert code == 0
    assert out.exists()
    import json

    rec = json.loads(out.read_text().strip())
    assert rec["provider"] == "openai_chat"
    assert rec["request"]["model"] == "gpt-4o"
