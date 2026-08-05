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
    "--beam-size",
    default=1,
    type=int,
    help="Candidate beam per round (v2.1, default: 1).",
)
@click.option(
    "--metric",
    type=click.Choice(
        ["llm", "exact_match", "rouge_l", "rouge_2", "bleu", "tool_call_valid"],
        case_sensitive=False,
    ),
    default="llm",
    help="Programmatic metric for frontier ranking (v2.1, default: llm).",
)
@click.option(
    "--examples",
    default=None,
    type=str,
    help="JSONL of few-shot examples (prompt/model_response/target_response or rubrics).",
)
@click.option(
    "--frontier-size",
    default=5,
    type=int,
    help="Max candidates kept on the frontier (v2.1, default: 5).",
)
@click.option(
    "--convergence-threshold",
    default=0.8,
    type=float,
    help="Convergence score for hard stop (v2.2, default: 0.8).",
)
@click.option(
    "--no-reverse-audit",
    is_flag=True,
    default=False,
    help="Skip the reverse audit gates (v2.2, risky — for exploration).",
)
@click.option(
    "--max-growth",
    default=1.5,
    type=float,
    help="Growth cap as multiplier of original size (v2.2, default: 1.5).",
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
    beam_size: int,
    metric: str,
    examples: str | None,
    frontier_size: int,
    convergence_threshold: float,
    no_reverse_audit: bool,
    max_growth: float,
    output: str | None,
) -> None:
    """Optimize a SOUL.md or skill file via reflective iteration."""
    from rw_promptforge.optimizer import Optimizer
    from rw_promptforge.provider import Provider
    from rw_promptforge.reflector.engine import Reflector
    from rw_promptforge.targets.examples import load_examples, summarize_examples

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

    # v2.1: load few-shot examples when provided
    example_list = None
    if examples:
        example_list = load_examples(examples)
        console.print(f"[dim]Examples: {summarize_examples(example_list)}[/dim]")

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
        beam_size=beam_size,
        metric=metric,
        examples=example_list,
        frontier_size=frontier_size,
        convergence_threshold=convergence_threshold,
        no_reverse_audit=no_reverse_audit,
        max_growth=max_growth,
    )

    if beam_size > 1:
        console.print(f"[dim]Beam: {beam_size} variants/round · Metric: {metric}[/dim]")
    if convergence_threshold != 0.8:
        console.print(f"[dim]Convergence threshold: {convergence_threshold}[/dim]")
    if no_reverse_audit:
        console.print("[dim]Reverse audit: [bold red]DISABLED[/bold red][/dim]")
    if max_growth != 1.5:
        console.print(f"[dim]Growth cap: {max_growth}×[/dim]")

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

    if result.frontier:
        console.print(f"\n[bold]Frontier ({len(result.frontier)} candidates):[/bold]")
        for i, cand in enumerate(result.frontier, start=1):
            console.print(
                f"  #{i} · rank {cand.rank_score:.3f} · composite {cand.scores.composite:.2f}"
                f" · metric {cand.metric_score:.3f} · Δsize {cand.size_delta:.2f}×"
                f" · round {cand.round_generated}"
            )
        if result.metric_type != "llm":
            console.print(f"  Metric: [cyan]{result.metric_type}[/] = {result.metric_score:.3f}")

    if result.learning_log:
        console.print("\n[bold]Learning Log:[/bold]")
        for entry in result.learning_log[-3:]:  # Last 3
            console.print(f"  - {entry.attempted_change[:60]}...")
            console.print(f"    Outcome: {entry.observed_outcome}")

    if output_path:
        console.print(f"\n[bold]Output saved to:[/bold] [cyan]{output_path}[/cyan]")

    provider_obj.close()