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


# Register config subcommand group (loaded late to keep `main` importable fast)
def _register_config():
    from rw_promptforge.configs.cli_config import config as config_group

    main.add_command(config_group, "config")


_register_config()


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
    "--endpoint", default=None, help="Custom OpenAI-compatible endpoint URL.")
@click.option("--model", default="gpt-4o-mini", help="Model for reflection LLM.")
@click.option(
    "--skill",
    default=None,
    help="Explicit skill name for trace scoping (overrides path-derived name).",
)
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
    help="Path to few-shot example files",
)
@click.option(
    "--frontier-size",
    default=5,
    show_default=True,
    help="Number of candidate solutions to evaluate each round",
)
@click.option(
    "--convergence-threshold",
    default=0.01,
    show_default=True,
    type=float,
    help="Minimum normalized score change to continue iterating",
)
@click.option(
    "--no-reverse-audit",
    is_flag=True,
    help="Disable reverse audit after each round",
)
@click.option(
    "--max-growth",
    default=1.5,
    show_default=True,
    type=float,
    help="Maximum allowed prompt size growth factor",
)
@click.option(
    "--output", "-o",
    help="Output path for optimized artifact (default: prompt output to stdout)",
)
@click.option(
    "--on-overflow",
    type=click.Choice(["retry", "fail"]),
    default=None,
    help="Overflow strategy: retry | fail (default: retry)",
)
@click.option(
    "--ml-mode",
    is_flag=True,
    default=None,
    help=(
        "Enable ML enhancements (clustering, classification, reranking) "
        "via RW_InferenceEngine. Requires: pip install 'rw-promptforge[ml]'. "
        "Falls back to token-based methods if dependencies or endpoints "
        "are unavailable."
    ),
)
@click.option(
    "--ml-endpoint",
    default=None,
    help="RW_InferenceEngine endpoint (default: http://srv1:8300).",
)
@click.option(
    "--min-traces",
    default=None,
    type=int,
    help="Minimum failure traces needed before clustering/classification activates (default: 10).",
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
    skill: str | None,
    examples: str | None,
    frontier_size: int,
    convergence_threshold: float,
    no_reverse_audit: bool,
    max_growth: float,
    output: str | None,
    on_overflow: str | None,
    ml_mode: bool | None,
    ml_endpoint: str | None,
    min_traces: int | None,
) -> None:
    """Optimize a SOUL.md or skill file via reflective iteration."""
    from rw_promptforge.configs import load_config
    from rw_promptforge.configs.cli_loader import cli_overrides_from_locals

    # Build CLI override dict from the flags the user actually passed.
    cli_overrides = cli_overrides_from_locals(locals())
    _config = load_config(cli_overrides=cli_overrides)

    # Unpack for use below. config.ml.enabled is bool; flag value None means
    # "user didn't pass" → falls back to config/env/file.
    ml_mode = _config.ml.enabled
    ml_endpoint = _config.ml.endpoint
    min_traces = _config.ml.min_traces
    # on_overflow default moved to None so we can distinguish "default" from
    # "explicitly passed"; the actual default is 'retry' (matches pre-config).
    if on_overflow is None:
        on_overflow = "retry"

    # LLM provider: CLI > config > env
    if endpoint is None:
        endpoint = _config.llm.endpoint
    if not model:
        model = _config.llm.model
    if provider is None:
        provider = _config.llm.provider
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

    reflector = Reflector(provider_obj, on_overflow=on_overflow)

    # ML mode: build a separate Provider for embed/rerank against RW_IE
    # (the chat-completions provider is the LLM for reflection; that's separate).
    ml_ctx = None
    if ml_mode:
        try:
            from rw_promptforge.cache import EmbeddingCache
            from rw_promptforge.provider import Provider as _MLProvider

            ml_provider = _MLProvider.from_ml_env()
            if ml_endpoint:
                ml_provider.endpoint = ml_endpoint.rstrip("/") + "/v1"
            ml_provider._cache = EmbeddingCache()
            ml_ctx = {
                "provider": ml_provider,
                "min_traces": min_traces,
            }
            console.print(
                f"[dim]ML mode: [cyan]{ml_provider.embedding_model}[/] @ "
                f"[cyan]{ml_provider.endpoint}[/] · min-traces={min_traces}[/dim]"
            )
        except ImportError as e:
            console.print(
                f"[yellow]⚠️  ML mode requested but dependencies missing:[/] {e}\n"
                "    Install with: pip install 'rw-promptforge[ml]'. "
                "Continuing without ML."
            )
            ml_mode = False

    # v2.1: load few-shot examples when provided
    example_list = None
    if examples:
        example_list = load_examples(examples)
        console.print(f"[dim]Examples: {summarize_examples(example_list)}[/dim]")

    output_path = output or (path + ".optimized" if save else None)
    optimizer = Optimizer(
        provider=provider_obj,
        reflector=reflector,
        output_path=output_path,
        learning_log_strategy=learning_log,
        post_mutation_verify=post_mutation_verify,
        examples=example_list,
        optimizer_config=_config.optimizer,  # layered-config-driven
        ml_context=ml_ctx,
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

    # Use --skill flag if provided, otherwise derive from path
    skill_name = skill or path.split("/")[-1].replace("-", "_").replace(".", "_")

    if target_type == "skill":
        result = optimizer.optimize_skill(path, skill_name=skill_name)
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
