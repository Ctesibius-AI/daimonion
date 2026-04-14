"""
Night Logger — Structured step log for the Night Processor.

Writes one line per step transition to ~/.daimonion/night_runs/YYYY-MM-DD/night.log
Human-readable, grep-friendly, QA-parseable.

Format:
    [HH:MM:SS] STEP name START
    [HH:MM:SS] STEP name END status=ok key=value duration=1200ms
    [HH:MM:SS] NIGHT COMPLETE duration=12300ms
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from src.config import NIGHT_RUNS_DIR


class NightLogger:
    """Structured step logger for Night Processor runs."""

    def __init__(self, date: str | None = None):
        self.date = date or datetime.now(timezone.utc).strftime('%Y-%m-%d')
        self._run_dir = os.path.join(NIGHT_RUNS_DIR, self.date)
        os.makedirs(self._run_dir, exist_ok=True)
        self._log_path = os.path.join(self._run_dir, 'night.log')
        self._step_starts: dict[str, float] = {}

    def _write(self, line: str):
        ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
        with open(self._log_path, 'a') as f:
            f.write(f'[{ts}] {line}\n')

    def start(self, step: str):
        """Log step start."""
        self._step_starts[step] = time.time()
        self._write(f'STEP {step} START')

    def end(self, step: str, **kwargs):
        """Log step end with key=value pairs."""
        t0 = self._step_starts.pop(step, None)
        if t0 is not None:
            kwargs['duration'] = f'{int((time.time() - t0) * 1000)}ms'
        parts = ' '.join(f'{k}={v}' for k, v in kwargs.items())
        self._write(f'STEP {step} END {parts}')

    def error(self, step: str, err: str):
        """Log step failure."""
        t0 = self._step_starts.pop(step, None)
        duration = ''
        if t0 is not None:
            duration = f' duration={int((time.time() - t0) * 1000)}ms'
        self._write(f'STEP {step} ERROR {err}{duration}')

    def night_complete(self, total_ms: int, **kwargs):
        """Log night processor completion."""
        parts = ' '.join(f'{k}={v}' for k, v in kwargs.items())
        self._write(f'NIGHT COMPLETE duration={total_ms}ms {parts}'.rstrip())

    @property
    def log_path(self) -> str:
        return self._log_path
