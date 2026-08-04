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
@click.argument("path", type=click.Path(exists=True, resolve_path=True))
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
@click.option(
    "--endpoint", default=None, help="Custom OpenAI-compatible endpoint URL."
)
@click.option(
    "--model", default="gpt-4o-mini", help="Model for reflection LLM."
)
@click.option(
    "--max-rounds",
    default=3,
    type=int,
    help="Max reflection rounds (default: 3, max: 20).",
)
@click.option(
    "--eval-command",
    required=True,
    help="Shell command to evaluate candidate. Use {path} placeholder. Exit 0 = pass.",
)
@click.option(
    "--save",
    is_flag=True,
    default=False,
    help="Save optimized output to {path}.optimized.",
)
def optimize(
    path: str,
    target_type: str,
    provider_name: str,
    endpoint: str | None,
    model: str,
    max_rounds: int,
    eval_command: str,
    save: bool,
) -> None:
    """Optimize a SOUL.md or skill file via reflective iteration."""
    from rw_promptforge.evaluator.shell import ShellEvaluator
    from rw_promptforge.optimizer import Optimizer
    from rw_promptforge.provider import Provider
    from rw_promptforge.reflector.engine import Reflector

    console.print(f"[bold]rw-promptforge[/] v{__version__}")
    console.print(f"Target: [cyan]{target_type}[/] | Path: [cyan]{path}[/]")
    info = f"Provider: [cyan]{provider_name}[/] | Model: [cyan]{model}[/]"
    console.print(f"{info} | Max rounds: [cyan]{max_rounds}[/]")

    # Build provider
    if endpoint:
        api_key = ""
        provider_obj = Provider(endpoint=endpoint, model=model, api_key=api_key)
    else:
        provider_obj = Provider.from_env(model=model)

    evaluator = ShellEvaluator(command_template=eval_command)
    reflector = Reflector(provider_obj)

    output = path + ".optimized" if save else None
    optimizer = Optimizer(
        provider=provider_obj,
        evaluator=evaluator,
        reflector=reflector,
        eval_command=eval_command,
        max_rounds=max_rounds,
        output_path=output,
    )

    console.print("\n[bold]Optimizing...[/bold]")
    result = optimizer.optimize(path)

    if result.converged:
        console.print(
            f"\n[bold green]✅ Converged in {result.rounds} round(s)[/bold green]"
        )
    else:
        console.print(
            f"\n[bold yellow]⚠️  Did not converge after {result.rounds} rounds[/bold yellow]"
        )

    for rnum, eval_res in result.history:
        status = "PASS" if eval_res.passed else "FAIL"
        color = "green" if eval_res.passed else "red"
        console.print(
            f"  Round {rnum}: [{color}]{status}[/{color}]"
            f" (exit={eval_res.exit_code}, {eval_res.elapsed:.1f}s)"
        )

    if save and output:
        console.print(
            f"\n[bold]Output saved to:[/bold] [cyan]{output}[/cyan]"
        )

    provider_obj.close()
