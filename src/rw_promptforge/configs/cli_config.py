"""`rw-promptforge config` subcommand — show, init, schema, doctor, set."""

from __future__ import annotations

import json
from pathlib import Path

import click
import tomli
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
    pass


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


@config.command("doctor")
@click.option("--endpoint", default=None, help="Override ML endpoint for connectivity test")
@click.option("--timeout", default=5.0, type=float, help="Timeout for connectivity test (seconds)")
def doctor(endpoint: str | None, timeout: float) -> None:
    """Validate configuration and test RW_InferenceEngine connectivity."""
    from rw_promptforge.configs import load_config
    import httpx

    console.print("[bold]Configuration Doctor[/bold]\n")

    cfg = load_config()
    console.print("[green]✓[/green] Config validation passed")

    issues = []
    if not cfg.llm.provider:
        issues.append("llm.provider not set")
    if not cfg.llm.model:
        issues.append("llm.model not set")
    if not cfg.session_db.path:
        issues.append("session_db.path not set")

    if issues:
        for issue in issues:
            console.print(f"[yellow]⚠[/yellow] {issue}")
    else:
        console.print("[green]✓[/green] Required fields present")

    if cfg.ml.enabled:
        test_endpoint = endpoint or cfg.ml.endpoint
        console.print(f"\n[dim]Testing RW_IE connectivity: {cfg.ml.endpoint}[/dim]")
        try:
            client = httpx.Client(timeout=httpx.Timeout(timeout))
            resp = httpx.get(f"{cfg.ml.endpoint}/health", timeout=timeout)
            resp.raise_for_status()
            health = resp.json()
            console.print(f"[green]✓[/green] RW_IE reachable — status: {health.get('status', 'unknown')}")
            if "models" in health:
                console.print(f"[dim]  Models: {', '.join(health['models'])}[/dim]")
        except httpx.ConnectError:
            console.print(f"[red]✗[/red] RW_IE unreachable at {cfg.ml.endpoint}")
        except httpx.TimeoutException:
            console.print(f"[red]✗[/red] RW_IE timeout after {timeout}s")
        except Exception as e:
            console.print(f"[red]✗[/red] RW_IE error: {e}")
    else:
        console.print("\n[dim]ML mode disabled — skipping RW_IE connectivity test[/dim]")

    prov = get_provenance()
    source_counts: dict[str, int] = {}
    for src in prov.values():
        source_counts[src] = source_counts.get(src, 0) + 1
    console.print("\n[dim]Provenance summary:[/dim]")
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        console.print(f"  {src}: {count} fields")


@config.command("set")
@click.argument("key", type=str)
@click.argument("value", type=str)
@click.option("--path", "custom_path", type=click.Path(), default=None, help="Config file to edit (default: user-level ~/.config/rw-promptforge/config.toml)")
@click.option("--force", is_flag=True, help="Create file if it doesn't exist")
def set_cmd(key: str, value: str, custom_path: str | None, force: bool) -> None:
    """Set a configuration value in the user-level config file.

    KEY uses dot notation: optimizer.max_rounds, ml.endpoint, etc.
    VALUE is parsed as JSON (numbers, booleans, strings, arrays, objects).
    """
    import json

    default_path = Path.home() / ".config" / "rw-promptforge" / "config.toml"
    target = Path(custom_path) if custom_path else Path.home() / ".config" / "rw-promptforge" / "config.toml"
    target = target.expanduser()

    if target.exists():
        with open(target, "rb") as f:
            data = tomli.load(f)
    else:
        if not force:
            console.print(f"[red]Config file not found:[/] {target} (use --force to create)")
            raise SystemExit(1)
        data = {}

    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        console.print(f"[red]Invalid JSON value:[/] {value}")
        raise SystemExit(1)

    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = parsed_value

    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".toml.tmp")
    temp.write_text(tomli_w.dumps(data))
    temp.replace(target)

    console.print(f"[green]✓[/green] Set [cyan]{key}[/cyan] = {json.dumps(parsed_value)} in [cyan]{target}[/cyan]")


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
            meta = {}
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
    for key, val in list(data.items()):
        if isinstance(val, dict):
            _strip_secrets(val)
        elif key in _CREDENTIAL_FIELDS:
            data[key] = ""

    for key, val in list(data.items()):
        if isinstance(val, dict) and not val:
            del data[key]


def _walk(obj, table: Table, prefix: str, prov: dict[str, str], with_prov: bool) -> None:
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
    if isinstance(obj, dict):
        return {k: _prune_nones(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_prune_nones(v) for v in obj]
    return obj