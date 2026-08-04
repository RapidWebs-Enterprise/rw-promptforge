"""CLI entry point. Thin — delegates to optimize commands."""

import click
from rich.console import Console

from rw_promptforge import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="rw-promptforge")
def main() -> None:
    """rw-promptforge — iterative prompt and skill optimization."""
    pass


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--target-type",
    type=click.Choice(["soul", "skill"], case_sensitive=False),
    required=True,
    help="Type of target to optimize.",
)
@click.option(
    "--provider",
    type=click.Choice(["openai", "openrouter", "custom"], case_sensitive=False),
    default="openai",
    help="LLM provider for the reflection step.",
)
@click.option("--endpoint", default=None, help="Custom OpenAI-compatible endpoint URL.")
@click.option("--model", default="gpt-4o-mini", help="Model for reflection LLM.")
@click.option(
    "--max-rounds",
    default=3,
    type=int,
    help="Max reflection rounds (default: 3).",
)
@click.option(
    "--eval-command",
    default=None,
    help="Shell command to evaluate candidate. Exit 0 = pass.",
)
@click.option(
    "--save",
    is_flag=True,
    default=False,
    help="Save optimized output to a new file.",
)
def optimize(
    path: str,
    target_type: str,
    provider: str,
    endpoint: str | None,
    model: str,
    max_rounds: int,
    eval_command: str | None,
    save: bool,
) -> None:
    """Optimize a SOUL.md or skill file via reflective iteration."""
    console.print(f"[bold]rw-promptforge[/] v{__version__}")
    console.print(f"Target: [cyan]{target_type}[/] | Path: [cyan]{path}[/]")
    console.print(
        f"Provider: [cyan]{provider}[/] | Model: [cyan]{model}[/] | Max rounds: [cyan]{max_rounds}[/]"
    )
    console.print("[yellow]Core loop not yet implemented.[/]")
    # TODO: wire to optimizer.Optimizer after TDD phase