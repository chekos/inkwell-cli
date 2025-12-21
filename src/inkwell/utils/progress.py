"""Pipeline progress display for CLI.

Provides a Docker-style multi-stage progress display with auto-updating elapsed time.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)


class StageStatus(Enum):
    """Status of a pipeline stage."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class PipelineStage:
    """A stage in the pipeline."""

    name: str
    description: str
    task_id: TaskID | None = None
    status: StageStatus = StageStatus.PENDING
    substep: str = ""


class PipelineProgress:
    """Multi-stage progress display with auto-updating elapsed time.

    Shows all pipeline stages upfront (Docker-style) with:
    - Stage number and name
    - Spinner for indeterminate progress
    - Auto-updating elapsed time (via Rich's TimeElapsedColumn)
    - Sub-step descriptions

    Example output:
        [1/4] Transcribing   ◐ Downloading audio...        2m 15s
        [2/4] Selecting      ○ pending
        [3/4] Extracting     ○ pending
        [4/4] Writing        ○ pending

    Usage:
        with PipelineProgress(console) as pp:
            pp.start_stage("transcribe")
            pp.update_substep("transcribe", "Downloading audio...")
            pp.complete_stage("transcribe")
    """

    # Default pipeline stages for inkwell fetch
    DEFAULT_STAGES = [
        ("transcribe", "Transcribing"),
        ("select", "Selecting templates"),
        ("extract", "Extracting content"),
        ("write", "Writing files"),
    ]

    def __init__(
        self,
        console: Console,
        stages: list[tuple[str, str]] | None = None,
        include_interview: bool = False,
    ):
        """Initialize pipeline progress.

        Args:
            console: Rich console for output
            stages: List of (id, display_name) tuples. Defaults to inkwell pipeline.
            include_interview: Whether to include interview as 5th stage
        """
        self.console = console
        self._stages: dict[str, PipelineStage] = {}
        self._progress: Progress | None = None
        self._started = False

        # Set up stages
        stage_list = stages or self.DEFAULT_STAGES.copy()
        if include_interview:
            stage_list.append(("interview", "Interview"))

        self._total_stages = len(stage_list)
        for i, (stage_id, name) in enumerate(stage_list, 1):
            self._stages[stage_id] = PipelineStage(
                name=f"[{i}/{self._total_stages}] {name}",
                description=name,
            )

    def __enter__(self) -> "PipelineProgress":
        """Start the progress display."""
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            TextColumn("{task.fields[substep]}", style="dim"),
            TimeElapsedColumn(),
            console=self.console,
            refresh_per_second=10,
        )
        self._progress.__enter__()

        # Add all stages as tasks (visible from the start)
        for _stage_id, stage in self._stages.items():
            stage.task_id = self._progress.add_task(
                f"[dim]{stage.name}[/dim]",
                total=None,  # Indeterminate
                substep="○ pending",
            )

        self._started = True
        return self

    def __exit__(self, *args: Any) -> None:
        """Stop the progress display."""
        if self._progress:
            self._progress.__exit__(*args)
        self._started = False

    def start_stage(self, stage_id: str) -> None:
        """Mark a stage as in progress.

        Args:
            stage_id: The stage identifier (e.g., "transcribe")
        """
        if not self._started or not self._progress:
            return

        stage = self._stages.get(stage_id)
        if not stage or stage.task_id is None:
            return

        stage.status = StageStatus.IN_PROGRESS
        self._progress.update(
            stage.task_id,
            description=f"[cyan]{stage.name}[/cyan]",
            substep="",
        )

    def update_substep(self, stage_id: str, substep: str) -> None:
        """Update the current substep description.

        Args:
            stage_id: The stage identifier
            substep: Description of current substep (e.g., "Downloading audio...")
        """
        if not self._started or not self._progress:
            return

        stage = self._stages.get(stage_id)
        if not stage or stage.task_id is None:
            return

        stage.substep = substep
        self._progress.update(stage.task_id, substep=substep)

    def complete_stage(self, stage_id: str, summary: str = "") -> None:
        """Mark a stage as complete.

        Args:
            stage_id: The stage identifier
            summary: Optional completion summary (e.g., "via YouTube")
        """
        if not self._started or not self._progress:
            return

        stage = self._stages.get(stage_id)
        if not stage or stage.task_id is None:
            return

        stage.status = StageStatus.COMPLETE
        completion_text = f"[green]✓[/green] {summary}" if summary else "[green]✓[/green]"
        self._progress.update(
            stage.task_id,
            description=f"[green]{stage.name}[/green]",
            substep=completion_text,
        )
        # Stop the spinner by setting total=1 and completed=1
        self._progress.update(stage.task_id, total=1, completed=1)

    def fail_stage(self, stage_id: str, error: str = "") -> None:
        """Mark a stage as failed.

        Args:
            stage_id: The stage identifier
            error: Optional error message
        """
        if not self._started or not self._progress:
            return

        stage = self._stages.get(stage_id)
        if not stage or stage.task_id is None:
            return

        stage.status = StageStatus.FAILED
        error_text = f"[red]✗[/red] {error}" if error else "[red]✗[/red]"
        self._progress.update(
            stage.task_id,
            description=f"[red]{stage.name}[/red]",
            substep=error_text,
        )
        self._progress.update(stage.task_id, total=1, completed=1)

    def print_after(self, message: str) -> None:
        """Print a message that appears after the progress display.

        Use this for summary information after stages complete.

        Args:
            message: Message to print
        """
        if self._progress:
            self._progress.console.print(message)
