"""CLI entry point — delegates to optimizer."""

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
@click.option("--endpoint", default=None, help="Custom OpenAI-compatible endpoint URL.")
@click.option("--model", default="gpt-4o-mini", help="Model for reflection LLM.")
@click.option(
    "--max-rounds",
    default=3,
    type=int,
    help="Max reflection rounds (default: 3, max: 20).",
)
@click.option(
    "--save",
    is_flag=True,
    default=False,
    help="Save optimized output to {path}.optimized.",
)
@click.option(
    "--learning-log",
    type=click.Choice(["none", "ancestors", "neighborhood-2"], case_sensitive=False),
    default="none",
    help="Learning log strategy (default: none).",
)
@click.option(
    "--post-mutation-verify",
    is_flag=True,
    default=False,
    help="Enable post-mutation verification filter.",
)
def optimize(
    path: str,
    target_type: str,
    provider: str,
    endpoint: str | None,
    model: str,
    max_rounds: int,
    save: bool,
    learning_log: str,
    post_mutation_verify: bool,
) -> None:
    """Optimize a SOUL.md or skill file via reflective iteration."""
    from rw_promptforge.optimizer import Optimizer
    from rw_promptforge.provider import Provider
    from rw_promptforge.reflector.engine import Reflector

    console.print(f"[bold]rw-promptforge[/] v{__version__}")
    console.print(f"Target: [cyan]{target_type}[/] | Path: [cyan]{path}[/]")
    info = f"Provider: [cyan]{provider}[/] | Model: [cyan]{model}[/]"
    console.print(f"{info} | Max rounds: [cyan]{max_rounds}[/]")

    # Build provider
    import os
    if endpoint:
        api_key = (
            os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or ""
        )
        provider_obj = Provider(endpoint=endpoint, model=model, api_key=api_key)
    else:
        provider_obj = Provider.from_env(model=model)

    reflector = Reflector(provider_obj)

    output = path + ".optimized" if save else None
    optimizer = Optimizer(
        provider=provider_obj,
        reflector=reflector,
        max_rounds=max_rounds,
        output_path=output,
        learning_log_strategy=learning_log,
        post_mutation_verify=post_mutation_verify,
    )

    console.print("\n[bold]Optimizing...[/bold]")

    if target_type == "skill":
        result = optimizer.optimize_skill(path, skill_name=path.split("/")[-1])
    else:  # soul
        result = optimizer.optimize_soul(path)

    if result.converged:
        console.print(
            f"\n[bold green]✅ Converged in {result.rounds} round(s)[/bold green]"
        )
    else:
        console.print(
            f"\n[bold yellow]⚠️  Did not converge after {result.rounds} rounds[/bold yellow]"
        )

    console.print(f"\nFailures found: {result.failures_found}")

    if result.learning_log:
        console.print("\n[bold]Learning Log:[/bold]")
        for entry in result.learning_log:
            console.print(f"  - {entry.attempted_change[:70]}...")
            console.print(f"    Outcome: {entry.observed_outcome}")

    if save and output:
        console.print(f"\n[bold]Output saved to:[/bold] [cyan]{output}[/cyan]")

    provider_obj.close()
