"""CLI commands for plugin management.

This module provides the `inkwell plugins` subcommand group for
listing, enabling, disabling, and validating plugins.
"""

import os
import sys

import typer
from rich.console import Console
from rich.table import Table

from inkwell.config.manager import ConfigManager
from inkwell.plugins import (
    ENTRY_POINT_GROUPS,
    PluginEntry,
    PluginRegistry,
    PluginValidationError,
    discover_all_plugins,
)
from inkwell.plugins.config import PluginConfigManager
from inkwell.plugins.types import ExtractionPlugin, OutputPlugin, TranscriptionPlugin

app = typer.Typer(
    name="plugins",
    help="Manage Inkwell plugins",
    no_args_is_help=True,
)
console = Console()


def _get_plugin_type_label(plugin_type: str) -> str:
    """Get human-readable label for plugin type."""
    labels = {
        "extraction": "Extraction Plugins",
        "transcription": "Transcription Plugins",
        "output": "Output Plugins",
    }
    return labels.get(plugin_type, plugin_type.title())


def _get_status_display(entry: PluginEntry) -> str:
    """Get display string for plugin status."""
    if entry.status == "loaded":
        return "[green]✓ enabled[/green]"
    elif entry.status == "disabled":
        return "[yellow]○ disabled[/yellow]"
    else:  # broken
        return "[red]✗ error[/red]"


def _get_source_label(source: str) -> str:
    """Determine if plugin is built-in or third-party."""
    if source.startswith("inkwell.plugins.") or source.startswith("inkwell."):
        return "[dim](built-in)[/dim]"
    return "[cyan](installed)[/cyan]"


def _load_all_registries() -> dict[str, PluginRegistry]:
    """Load all plugin registries.

    Returns:
        Dict mapping plugin type names to their registries.
    """
    # Map plugin types to their base classes
    plugin_classes = {
        "extraction": ExtractionPlugin,
        "transcription": TranscriptionPlugin,
        "output": OutputPlugin,
    }

    registries = {}
    all_plugins = discover_all_plugins()

    for plugin_type, results in all_plugins.items():
        plugin_class = plugin_classes[plugin_type]
        registry: PluginRegistry = PluginRegistry(plugin_class)  # type: ignore[type-abstract]

        # Register each discovered plugin
        for result in results:
            priority = 100 if "inkwell." in result.source else 50
            registry.register(
                name=result.name,
                plugin=result.plugin,
                priority=priority,
                source=result.source,
                error=result.error,
                recovery_hint=result.recovery_hint,
            )

        registries[plugin_type] = registry

    return registries


def _find_plugin_entry(
    name: str, registries: dict[str, PluginRegistry]
) -> tuple[str, PluginEntry] | None:
    """Find a plugin by name across all registries.

    Returns:
        Tuple of (plugin_type, entry) if found, None otherwise.
    """
    for plugin_type, registry in registries.items():
        entry = registry.get_entry(name)
        if entry:
            return (plugin_type, entry)
    return None


@app.command("list")
def list_plugins(
    plugin_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by plugin type: extraction, transcription, output",
    ),
    show_all: bool = typer.Option(False, "--all", "-a", help="Show all plugins including disabled"),
) -> None:
    """List installed plugins by type.

    Shows plugin status (enabled/disabled/broken), priority, and description.

    Examples:
        inkwell plugins list

        inkwell plugins list --type extraction

        inkwell plugins list --all
    """
    if plugin_type and plugin_type not in ENTRY_POINT_GROUPS:
        valid_types = ", ".join(ENTRY_POINT_GROUPS.keys())
        console.print(f"[red]✗[/red] Unknown plugin type: {plugin_type}")
        console.print(f"Valid types: {valid_types}")
        sys.exit(1)

    registries = _load_all_registries()

    if plugin_type:
        registries = {plugin_type: registries[plugin_type]}

    total_plugins = 0
    broken_plugins: list[PluginEntry] = []

    for ptype, registry in registries.items():
        entries = registry.all_entries()

        if not entries:
            continue

        if not show_all:
            entries = [e for e in entries if e.status != "disabled"]

        if not entries:
            continue

        total_plugins += len(entries)

        # Display section header
        console.print(f"\n[bold]{_get_plugin_type_label(ptype)}:[/bold]")

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Source", no_wrap=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Priority", style="dim", justify="right")
        table.add_column("Description")

        for entry in entries:
            if entry.status == "broken":
                broken_plugins.append(entry)

            description = ""
            if entry.plugin:
                description = getattr(entry.plugin, "DESCRIPTION", "")

            source_label = _get_source_label(entry.source)
            status_display = _get_status_display(entry)
            priority_display = f"[{entry.priority}]"

            table.add_row(
                entry.name,
                source_label,
                status_display,
                priority_display,
                description,
            )

        console.print(table)

    # Show broken plugins section
    if broken_plugins:
        console.print("\n[bold red]Broken Plugins:[/bold red]")
        for entry in broken_plugins:
            console.print(f"  [red]{entry.name}[/red]  {entry.error}")
            if entry.recovery_hint:
                console.print(f"    [dim]Recovery: {entry.recovery_hint}[/dim]")

    if total_plugins == 0:
        console.print("[yellow]No plugins found.[/yellow]")
        return

    # Show helpful hints
    console.print("\n[dim]To install plugins: uv add <plugin-name>[/dim]")

    # Show env var overrides if set
    extractor_override = os.environ.get("INKWELL_EXTRACTOR")
    transcriber_override = os.environ.get("INKWELL_TRANSCRIBER")

    if extractor_override or transcriber_override:
        console.print("\n[bold]Active Overrides:[/bold]")
        if extractor_override:
            console.print(f"  INKWELL_EXTRACTOR={extractor_override}")
        if transcriber_override:
            console.print(f"  INKWELL_TRANSCRIBER={transcriber_override}")


@app.command("enable")
def enable_plugin(
    name: str = typer.Argument(..., help="Plugin name to enable"),
    persist: bool = typer.Option(
        False,
        "--persist",
        "-p",
        help="Persist state to config file (survives restart)",
    ),
) -> None:
    """Enable a disabled plugin.

    Examples:
        inkwell plugins enable whisper

        inkwell plugins enable whisper --persist
    """
    registries = _load_all_registries()
    result = _find_plugin_entry(name, registries)

    if not result:
        console.print(f"[red]x[/red] Plugin '{name}' not found")
        console.print("\nUse [cyan]inkwell plugins list --all[/cyan] to see available plugins")
        sys.exit(1)

    plugin_type, entry = result

    if entry.status == "broken":
        console.print(f"[red]x[/red] Cannot enable broken plugin '{name}'")
        if entry.error:
            console.print(f"  Error: {entry.error}")
        if entry.recovery_hint:
            console.print(f"  Recovery: {entry.recovery_hint}")
        sys.exit(1)

    if entry.status == "loaded" and not persist:
        console.print(f"[yellow]Plugin '{name}' is already enabled[/yellow]")
        return

    # Enable in registry
    registry = registries[plugin_type]
    registry.enable(name)

    # Persist to config if requested
    if persist:
        config_manager = ConfigManager()
        plugin_config_manager = PluginConfigManager(config_manager)
        plugin_config_manager.set_plugin_enabled(name, enabled=True)
        console.print(f"[green]v[/green] Plugin '{name}' enabled and saved to config")
    else:
        console.print(f"[green]v[/green] Plugin '{name}' enabled")
        console.print(
            "[dim]Note: Plugin state is not persisted. Use --persist to save to config file.[/dim]"
        )


@app.command("disable")
def disable_plugin(
    name: str = typer.Argument(..., help="Plugin name to disable"),
    persist: bool = typer.Option(
        False,
        "--persist",
        "-p",
        help="Persist state to config file (survives restart)",
    ),
) -> None:
    """Disable a plugin (prevent it from being used).

    Examples:
        inkwell plugins disable gemini

        inkwell plugins disable gemini --persist
    """
    registries = _load_all_registries()
    result = _find_plugin_entry(name, registries)

    if not result:
        console.print(f"[red]x[/red] Plugin '{name}' not found")
        console.print("\nUse [cyan]inkwell plugins list[/cyan] to see available plugins")
        sys.exit(1)

    plugin_type, entry = result

    if entry.status == "disabled" and not persist:
        console.print(f"[yellow]Plugin '{name}' is already disabled[/yellow]")
        return

    if entry.status == "broken" and not persist:
        console.print(f"[yellow]Plugin '{name}' is broken (already unusable)[/yellow]")
        return

    # Disable in registry
    registry = registries[plugin_type]
    registry.disable(name)

    # Persist to config if requested
    if persist:
        config_manager = ConfigManager()
        plugin_config_manager = PluginConfigManager(config_manager)
        plugin_config_manager.set_plugin_enabled(name, enabled=False)
        console.print(f"[green]v[/green] Plugin '{name}' disabled and saved to config")
    else:
        console.print(f"[green]v[/green] Plugin '{name}' disabled")
        console.print(
            "[dim]Note: Plugin state is not persisted. Use --persist to save to config file.[/dim]"
        )


@app.command("validate")
def validate_plugin(
    name: str | None = typer.Argument(None, help="Plugin name to validate (all if omitted)"),
) -> None:
    """Validate plugin configuration.

    Runs the plugin's validate() method to check configuration
    and required resources.

    Examples:
        inkwell plugins validate

        inkwell plugins validate claude
    """
    registries = _load_all_registries()

    if name:
        result = _find_plugin_entry(name, registries)

        if not result:
            console.print(f"[red]✗[/red] Plugin '{name}' not found")
            sys.exit(1)

        plugin_type, entry = result

        if entry.status == "broken":
            console.print(f"[red]✗[/red] Plugin '{name}' failed to load")
            if entry.error:
                console.print(f"  Error: {entry.error}")
            sys.exit(1)

        if not entry.plugin:
            console.print(f"[red]✗[/red] Plugin '{name}' not loaded")
            sys.exit(1)

        try:
            entry.plugin.validate()
            console.print(f"[green]✓[/green] Plugin '{name}' validated successfully")
        except PluginValidationError as e:
            console.print(f"[red]✗[/red] Plugin '{name}' validation failed:")
            for error in e.errors:
                console.print(f"  • {error}")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]✗[/red] Plugin '{name}' validation error: {e}")
            sys.exit(1)

    else:
        validation_errors = []
        validated_count = 0

        for _plugin_type, registry in registries.items():
            for entry in registry.all_entries():
                if entry.status != "loaded" or not entry.plugin:
                    continue

                try:
                    entry.plugin.validate()
                    validated_count += 1
                except PluginValidationError as e:
                    validation_errors.append((entry.name, e.errors))
                except Exception as e:
                    validation_errors.append((entry.name, [str(e)]))

        if validation_errors:
            console.print("[bold red]Validation Failures:[/bold red]\n")
            for plugin_name, errors in validation_errors:
                console.print(f"[red]✗[/red] {plugin_name}:")
                for error in errors:
                    console.print(f"    • {error}")
            console.print(
                f"\n[dim]{validated_count} plugins validated, {len(validation_errors)} failed[/dim]"
            )
            sys.exit(1)
        else:
            console.print(f"[green]✓[/green] All {validated_count} plugins validated successfully")
