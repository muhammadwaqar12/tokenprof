"""Capture request payloads from a program without editing it.

`tokenprof record -- python app.py` runs your program with a sitecustomize
shim on the path. The shim wraps the OpenAI and Anthropic client methods,
writes each outgoing request to a JSONL file, and calls through untouched.

Two deliberate constraints. The shim never raises into your program: if
patching fails, your program runs exactly as it would have, and you get a
warning instead of a crash. And it only records requests, never responses,
so nothing here changes what your program does.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

# Written to a temp dir and put on PYTHONPATH. Python imports sitecustomize
# automatically at interpreter startup, which is how this attaches without
# the target program knowing anything about it.
SHIM = """
import json as _json
import os as _os
import sys as _sys
import threading as _threading

_OUT = _os.environ.get("TOKENPROF_OUT")
_LOCK = _threading.Lock()


def _dump(provider, kwargs):
    if not _OUT:
        return
    try:
        payload = {k: v for k, v in kwargs.items() if k != "extra_headers"}
        line = _json.dumps({"provider": provider, "request": payload}, default=str)
    except Exception:
        return
    try:
        with _LOCK, open(_OUT, "a", encoding="utf-8") as fh:
            fh.write(line + "\\n")
    except Exception:
        pass


def _wrap(cls, provider):
    original = cls.create

    def create(self, *args, **kwargs):
        _dump(provider, kwargs)
        return original(self, *args, **kwargs)

    create.__name__ = "create"
    create.__doc__ = original.__doc__
    cls.create = create


_patched = []

try:
    from openai.resources.chat import completions as _oc

    _wrap(_oc.Completions, "openai_chat")
    _wrap(_oc.AsyncCompletions, "openai_chat")
    _patched.append("openai")
except Exception:
    pass

try:
    from anthropic.resources import messages as _am

    _wrap(_am.Messages, "anthropic_messages")
    _wrap(_am.AsyncMessages, "anthropic_messages")
    _patched.append("anthropic")
except Exception:
    pass

if _os.environ.get("TOKENPROF_VERBOSE"):
    print("tokenprof: patched " + (", ".join(_patched) or "nothing"), file=_sys.stderr)

try:
    import sitecustomize_original  # noqa: F401
except Exception:
    pass
"""


def record(argv: list[str], out_path: str, verbose: bool = False) -> int:
    """Run a command with recording enabled. Returns its exit code."""
    if not argv:
        raise ValueError("nothing to run: pass a command after --")

    shim_dir = tempfile.mkdtemp(prefix="tokenprof-shim-")
    with open(os.path.join(shim_dir, "sitecustomize.py"), "w", encoding="utf-8") as fh:
        fh.write(SHIM)

    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = shim_dir + (os.pathsep + existing if existing else "")
    env["TOKENPROF_OUT"] = os.path.abspath(out_path)
    if verbose:
        env["TOKENPROF_VERBOSE"] = "1"

    before = _count_lines(out_path)
    try:
        proc = subprocess.run(argv, env=env)
    except FileNotFoundError:
        raise SystemExit(f"command not found: {argv[0]}") from None
    captured = _count_lines(out_path) - before

    if captured:
        print(
            f"\ntokenprof: captured {captured} request(s) to {out_path}\n"
            f"  tokenprof analyze {out_path}",
            file=sys.stderr,
        )
    else:
        print(
            "\ntokenprof: captured nothing.\n"
            "  The program may not have called openai or anthropic, or it ran in a\n"
            "  subprocess that did not inherit PYTHONPATH. Re-run with --verbose to\n"
            "  see whether the shim attached.",
            file=sys.stderr,
        )
    return proc.returncode


def _count_lines(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0
