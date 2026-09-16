"""Read-only pandas sandbox (PRD §7.9), for questions the fixed tools don't
cover. No imports, no dunder access, no file or network access, a timeout,
and a row cap on the result.
"""
from __future__ import annotations

import multiprocessing
import re

import numpy as np
import pandas as pd

TIMEOUT_SECONDS = 5
MAX_ROWS = 500

_FORBIDDEN_PATTERN = re.compile(r"__|import\s|open\(|exec\(|eval\(|getattr|setattr|globals|locals")


class SandboxError(Exception):
    pass


def _run_in_process(code: str, tables: dict[str, pd.DataFrame], queue) -> None:
    safe_globals = {"__builtins__": {}, "pd": pd, "np": np}
    safe_locals = {k: v.copy() for k, v in tables.items()}
    try:
        result = eval(code, safe_globals, safe_locals)  # noqa: S307 - sandboxed builtins
        if isinstance(result, pd.DataFrame):
            result = result.head(MAX_ROWS).to_dict("records")
        elif isinstance(result, pd.Series):
            result = result.head(MAX_ROWS).to_dict()
        queue.put(("ok", result))
    except Exception as exc:  # noqa: BLE001 - reporting back to the caller, not swallowing
        queue.put(("error", str(exc)))


def run_sandbox(code: str, tables: dict[str, pd.DataFrame]):
    if _FORBIDDEN_PATTERN.search(code):
        raise SandboxError("Code contains a forbidden token (imports, dunder access, exec/eval, I/O)")

    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(target=_run_in_process, args=(code, tables, queue))
    process.start()
    process.join(timeout=TIMEOUT_SECONDS)

    if process.is_alive():
        process.terminate()
        process.join()
        raise SandboxError(f"Sandbox code timed out after {TIMEOUT_SECONDS}s")

    if queue.empty():
        raise SandboxError("Sandbox process exited without a result")

    status, value = queue.get()
    if status == "error":
        raise SandboxError(value)
    return value
