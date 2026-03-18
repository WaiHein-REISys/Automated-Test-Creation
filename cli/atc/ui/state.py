"""Shared UI state and NiceGUI progress reporter."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from atc.core.progress import Phase, PipelineResult, ProgressEvent, ProgressReporter


@dataclass
class LogEntry:
    """A single log line displayed in the UI."""

    timestamp: str
    phase: str
    message: str
    level: str = "info"


@dataclass
class RunHistory:
    """Record of a past pipeline run."""

    timestamp: str
    config_path: str
    url: str
    product_name: str
    generated: int = 0
    failed: int = 0
    skipped: int = 0
    total: int = 0


class AppState:
    """Global application state shared across UI pages."""

    def __init__(self) -> None:
        self.config_path: str = ""
        self.config_data: dict[str, Any] = {}
        self.is_running: bool = False
        self.current_phase: Phase | None = None
        self.phase_progress: dict[str, str] = {}  # phase_value → status (pending/active/done)
        self.logs: list[LogEntry] = []
        self.result: PipelineResult | None = None
        self.cancel_event: asyncio.Event = asyncio.Event()
        self.run_history: list[RunHistory] = []
        self._state_dir = Path.home() / ".atc"
        self._load_history()

    def reset_run(self) -> None:
        """Reset state for a new pipeline run."""
        self.is_running = False
        self.current_phase = None
        self.phase_progress = {p.value: "pending" for p in Phase}
        self.logs = []
        self.result = None
        self.cancel_event = asyncio.Event()

    def add_log(self, entry: LogEntry) -> None:
        self.logs.append(entry)

    def save_run(self, result: PipelineResult) -> None:
        """Save a completed run to history."""
        record = RunHistory(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            config_path=self.config_path,
            url=self.config_data.get("url", ""),
            product_name=self.config_data.get("product_name", ""),
            generated=result.generated,
            failed=result.failed,
            skipped=result.skipped,
            total=result.total,
        )
        self.run_history.insert(0, record)
        self.run_history = self.run_history[:20]  # keep last 20
        self._save_history()

    def _load_history(self) -> None:
        path = self._state_dir / "run_history.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.run_history = [RunHistory(**r) for r in data]
            except Exception:
                self.run_history = []

    def _save_history(self) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        path = self._state_dir / "run_history.json"
        data = [
            {
                "timestamp": r.timestamp,
                "config_path": r.config_path,
                "url": r.url,
                "product_name": r.product_name,
                "generated": r.generated,
                "failed": r.failed,
                "skipped": r.skipped,
                "total": r.total,
            }
            for r in self.run_history
        ]
        path.write_text(json.dumps(data, indent=2))


class NiceGuiReporter:
    """ProgressReporter that pushes events into AppState for the NiceGUI frontend."""

    def __init__(self, state: AppState, on_update: Any = None) -> None:
        self.state = state
        self._on_update = on_update  # callable to trigger UI refresh

    def _now(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    async def _notify(self) -> None:
        if self._on_update:
            self._on_update()

    async def report(self, event: ProgressEvent) -> None:
        entry = LogEntry(
            timestamp=self._now(),
            phase=event.phase.label,
            message=event.message,
            level=event.level,
        )
        self.state.add_log(entry)
        await self._notify()

    async def phase_start(self, phase: Phase, message: str) -> None:
        self.state.current_phase = phase
        self.state.phase_progress[phase.value] = "active"
        entry = LogEntry(
            timestamp=self._now(),
            phase=phase.label,
            message=f"▶ {message}",
            level="info",
        )
        self.state.add_log(entry)
        await self._notify()

    async def phase_end(self, phase: Phase, message: str) -> None:
        self.state.phase_progress[phase.value] = "done"
        entry = LogEntry(
            timestamp=self._now(),
            phase=phase.label,
            message=f"✓ {message}",
            level="success",
        )
        self.state.add_log(entry)
        await self._notify()

    async def item_progress(
        self, phase: Phase, current: int, total: int, message: str
    ) -> None:
        entry = LogEntry(
            timestamp=self._now(),
            phase=phase.label,
            message=f"[{current}/{total}] {message}",
            level="info",
        )
        self.state.add_log(entry)
        await self._notify()


# Singleton state instance
app_state = AppState()
