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
@click.option(
    "--hypothesis-first",
    is_flag=True,
    default=False,
    help="Use 2-step reflection (diagnose → fix) for complex artifacts.",
)
@click.option(
    "--semantic-threshold",
    default=0.95,
    type=float,
    help="Cosine/Jaccard similarity threshold for convergence (default: 0.95).",
)
@click.option(
    "--gain-threshold",
    default=0.02,
    type=float,
    help="Minimum composite score gain to continue (default: 0.02).",
)
@click.option(
    "--stability-threshold",
    default=0.05,
    type=float,
    help="Max multiplier magnitude before considering category stable (default: 0.05).",
)
@click.option(
    "--min-rounds",
    default=2,
    type=int,
    help="Minimum rounds before convergence can trigger (default: 2).",
)
@click.option(
    "--output",
    default=None,
    type=str,
    help="Save optimized output to a separate file (instead of overwriting).",
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
    hypothesis_first: bool,
    semantic_threshold: float,
    gain_threshold: float,
    stability_threshold: float,
    min_rounds: int,
    output: str | None,
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

    output_path = output or (path + ".optimized" if save else None)
    optimizer = Optimizer(
        provider=provider_obj,
        reflector=reflector,
        max_rounds=max_rounds,
        output_path=output_path,
        learning_log_strategy=learning_log,
        post_mutation_verify=post_mutation_verify,
        semantic_threshold=semantic_threshold,
        gain_threshold=gain_threshold,
        stability_threshold=stability_threshold,
        min_rounds=min_rounds,
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

    if result.categories:
        console.print(f"\n[bold]Category Scores:[/bold]")
        console.print(f"  Composite: {result.composite_score:.2f}")

    if result.learning_log:
        console.print("\n[bold]Learning Log:[/bold]")
        for entry in result.learning_log[-3:]:  # Last 3
            console.print(f"  - {entry.attempted_change[:60]}...")
            console.print(f"    Outcome: {entry.observed_outcome}")

    if output_path:
        console.print(f"\n[bold]Output saved to:[/bold] [cyan]{output_path}[/cyan]")

    provider_obj.close()