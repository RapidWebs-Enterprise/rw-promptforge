"""`rw-promptforge config` subcommand — show, init, schema."""

from __future__ import annotations

import json
from pathlib import Path

import click
import tomli_w
from rich.console import Console
from rich.table import Table

from rw_promptforge.configs.core import get_provenance
from rw_promptforge.configs.models import RootConfig

console = Console()

_CREDENTIAL_FIELDS = {"api_key", "bot_token"}


def _render_value(field_name: str, value, redact: bool = True) -> str:
    if redact and field_name in _CREDENTIAL_FIELDS:
        return "***"
    # Pydantic SecretStr
    if hasattr(value, "get_secret_value"):
        return "***" if redact else str(value.get_secret_value())
    if isinstance(value, Path):
        return str(value)
    if value is None:
        return "—"
    return str(value)


@click.group()
def config() -> None:
    """Inspect, init, or validate rw-promptforge configuration."""


@config.command("show")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option("--export", "do_export", is_flag=True, help="Write TOML without secrets to stdout")
@click.option("--provenance/--no-provenance", default=True, help="Show [source] annotation per field")
def show(as_json: bool, do_export: bool, provenance: bool) -> None:
    """Print merged configuration."""
    from rw_promptforge.configs import load_config

    cfg = load_config()
    prov = get_provenance()

    if do_export:
        # Export as TOML without secrets
        data = cfg.model_dump(mode="json")
        _strip_secrets(data)
        click.echo(tomli_w.dumps(data))
        return

    if as_json:
        console.print_json(data=_to_jsonable(cfg, prov))
        return

    table = Table(title="rw-promptforge configuration")
    table.add_column("Path", style="cyan")
    table.add_column("Value", style="white")
    if provenance:
        table.add_column("Source", style="dim")

    _walk(cfg, table, "", prov, provenance)
    console.print(table)


@config.command("init")
@click.option("--force", is_flag=True, help="Overwrite existing file")
@click.option("--path", "custom_path", type=click.Path(), default=None, help="Custom path")
def init(force: bool, custom_path: str | None) -> None:
    """Write a scaffold config.toml to ~/.config/rw-promptforge/config.toml."""
    default_path = Path.home() / ".config" / "rw-promptforge" / "config.toml"
    target = Path(custom_path) if custom_path else default_path
    target = target.expanduser()

    if target.exists() and not force:
        console.print(f"[red]Exists:[/] {target} (use --force to overwrite)")
        raise SystemExit(1)

    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".toml.tmp")
    # Render defaults as scaffold — drop Nones (tomli_w can't serialize them)
    data = RootConfig().model_dump(mode="json")
    _strip_secrets(data)
    cleaned = _prune_nones(data)
    temp.write_text(tomli_w.dumps(cleaned))
    temp.replace(target)
    console.print(f"[green]✓[/green] wrote scaffold to [cyan]{target}[/cyan]")


@config.command("schema")
def schema() -> None:
    """Print JSON Schema for all configuration fields."""
    console.print_json(data=RootConfig.model_json_schema())


# ---- helpers ------------------------------------------------------------


def _to_jsonable(cfg: RootConfig, prov: dict[str, str]) -> dict:
    """Flatten RootConfig to {leaf: {value, source}}."""

    def walk(prefix: str, obj, out: dict) -> None:
        for field in type(obj).model_fields:
            value = getattr(obj, field)
            path = f"{prefix}.{field}" if prefix else field
            meta = {}  # could include description later
            if hasattr(value, "model_fields"):
                walk(path, value, out)
            else:
                entry = {
                    "value": _render_value(field, value),
                    **meta,
                }
                if path in prov:
                    entry["source"] = prov[path]
                out[path] = entry

    result: dict = {}
    walk("", cfg, result)
    return result


def _strip_secrets(data: dict) -> None:
    """Remove credential leaves from an exported config dict."""
    for key, val in list(data.items()):
        if isinstance(val, dict):
            _strip_secrets(val)
        elif key in _CREDENTIAL_FIELDS:
            data[key] = ""

    # Drop empty dicts left behind
    for key, val in list(data.items()):
        if isinstance(val, dict) and not val:
            del data[key]


def _walk(obj, table: Table, prefix: str, prov: dict[str, str], with_prov: bool) -> None:
    """Walk a Pydantic model, adding rows to the table."""
    for field_name in type(obj).model_fields:
        value = getattr(obj, field_name)
        path = f"{prefix}.{field_name}" if prefix else field_name
        if hasattr(value, "model_fields"):
            _walk(value, table, path, prov, with_prov)
            continue
        rendered = _render_value(field_name, value)
        source = prov.get(path, "default")
        if with_prov:
            table.add_row(path, rendered, source)
        else:
            table.add_row(path, rendered)


def _prune_nones(obj):
    """Remove None values recursively — tomli_w/rendering helpers can't serialize them."""
    if isinstance(obj, dict):
        return {k: _prune_nones(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_prune_nones(v) for v in obj]
    return obj
