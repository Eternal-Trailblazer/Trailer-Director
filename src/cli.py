"""CLI entry point - Gemini API mode only."""

from __future__ import annotations

import os
import click
from pathlib import Path
import yaml

from src.pipeline import Pipeline, load_config
from src.providers import ModelProvider, BudgetController, BudgetConfig, FallbackChain, GeminiProvider


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), help="Config file path")
@click.pass_context
def cli(ctx, config):
    """Autonomous Trailer Director CLI (Gemini API mode)."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


def _build_provider(config_data: dict) -> ModelProvider:
    """Build Gemini provider from config or environment. Raises on failure."""
    providers_config = config_data.get("providers", [])
    gemini_config = next((p for p in providers_config if p.get("provider_id") == "gemini"), None)

    # 1. API key from config file
    if gemini_config:
        api_key = gemini_config.get("api_key")
        model = gemini_config.get("model", "gemini-3.8-flash")
        if api_key and not api_key.startswith("YOUR_"):
            click.echo(f"[OK] Using Gemini API ({model}) from config")
            return GeminiProvider(api_key=api_key, model=model)

        # 2. API key from environment variable
        env_var = gemini_config.get("api_key_env", "GEMINI_API_KEY")
        api_key = os.getenv(env_var)
        if api_key:
            click.echo(f"[OK] Using Gemini API ({model}) from env: {env_var}")
            return GeminiProvider(api_key=api_key, model=model)

    # 3. Standard environment variables
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        click.echo("[OK] Using Gemini API from environment variable")
        return GeminiProvider(api_key=api_key, model="gemini-3.8-flash")

    raise click.ClickException(
        "No Gemini API key found. Add 'api_key' to config/default_config.yaml "
        "or set the GEMINI_API_KEY environment variable."
    )


@cli.command()
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), help="Config file path")
@click.option("--package", "-p", required=True, type=click.Path(exists=True, path_type=Path), help="Episode package path")
@click.option("--scenes", "-s", type=click.Path(exists=True, path_type=Path), help="Scene descriptions path")
@click.option("--dialogue", "-d", type=click.Path(exists=True, path_type=Path), help="Dialogue/subtitles path")
@click.option("--policies", type=click.Path(exists=True, path_type=Path), help="Rating policies path")
@click.option("--contracts", type=click.Path(exists=True, path_type=Path), help="Contracts path")
@click.option("--audiences", type=click.Path(exists=True, path_type=Path), help="Audience profiles path")
@click.option("--history", type=click.Path(exists=True, path_type=Path), help="Historic performance path")
@click.option("--costs", type=click.Path(exists=True, path_type=Path), help="Cost sheet path")
@click.option("--output", "-o", required=True, type=click.Path(path_type=Path), help="Output directory")
@click.option("--budget", type=float, help="Budget override (USD)")
@click.pass_context
def run(ctx, config, package, scenes, dialogue, policies, contracts, audiences, history, costs, output, budget):
    """Run full pipeline: ingest -> plan -> verify -> emit EDL."""
    effective_config = config or ctx.obj.get("config_path")
    config_data = load_config(effective_config)

    # Override budget if provided
    if budget:
        config_data["budget"]["total_usd"] = budget

    # Build provider (Gemini API only - no mock)
    provider = _build_provider(config_data)

    # Create fallback chain
    fallback = FallbackChain([provider])

    # Budget controller
    budget_config = BudgetConfig(**config_data["budget"])
    budget_controller = BudgetController(budget_config)

    # Create pipeline
    pipeline = Pipeline(
        model_provider=fallback,
        budget_controller=budget_controller,
        config=config_data,
        output_dir=output,
    )

    click.echo(f"Running pipeline with episode package: {package}")
    click.echo(f"Output directory: {output}")

    result = pipeline.run(
        episode_package_path=package,
        scene_descriptions_path=scenes,
        dialogue_path=dialogue,
        policies_path=policies,
        contracts_path=contracts,
        audience_profiles_path=audiences,
        historic_data_path=history,
        cost_sheet_path=costs,
    )

    # Print summary
    click.echo("\n=== Pipeline Complete ===")
    click.echo(f"Story map: {len(result.story_map.scenes)} scenes, {len(result.story_map.entities)} entities")
    click.echo(f"Spoiler facts: {len(result.spoiler_facts)}")
    click.echo(f"Rules compiled: {len(result.rules)}")
    click.echo(f"Trailers generated: {len(result.trailers)}")

    for trailer in result.trailers:
        status = trailer.validation.status.value if trailer.validation else "PENDING"
        click.echo(f"  {trailer.trailer_id} ({trailer.audience}): {status}, {trailer.duration_seconds:.1f}s, {len(trailer.segments)} segments")

    click.echo(f"\nTotal cost: ${result.cost_ledger.total_cost:.4f}")
    click.echo(f"Budget remaining: ${result.cost_ledger.budget_remaining:.4f}")
    click.echo(f"Outputs written to: {output}")


@cli.command()
@click.option("--plans", "-p", required=True, type=click.Path(exists=True, path_type=Path), help="Plans directory")
@click.pass_context
def verify(ctx, plans):
    """Verify existing trailer plans."""
    click.echo(f"Verifying plans in: {plans}")
    click.echo("Verification not yet implemented")


@cli.command()
@click.option("--event", "-e", required=True, type=click.Path(exists=True, path_type=Path), help="Change event JSON file")
@click.option("--plans", "-p", required=True, type=click.Path(exists=True, path_type=Path), help="Plans directory")
@click.pass_context
def apply_change(ctx, event, plans):
    """Apply a change event to existing plans."""
    click.echo(f"Applying change event: {event}")
    click.echo(f"To plans in: {plans}")
    click.echo("Change handling not yet implemented")


@cli.command()
@click.option("--plans", "-p", required=True, type=click.Path(exists=True, path_type=Path), help="Plans directory")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output report path")
@click.pass_context
def report(ctx, plans, output):
    """Generate validation report."""
    click.echo(f"Generating report for: {plans}")
    if output:
        click.echo(f"Writing to: {output}")
    click.echo("Report generation not yet implemented")


if __name__ == "__main__":
    cli()
