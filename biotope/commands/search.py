"""Search command implementation."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from biotope.utils import find_biotope_root
from biotope.validation import load_biotope_config
from biotope.registry.manager import RegistryManager
from biotope.registry.biocontext import BioContextRegistry


@click.command()
@click.argument("query", required=False)
@click.option("--limit", "-n", default=10, help="Number of results to show")
@click.option("--type", "-t", help="Resource type to search (currently only 'mcp')")
@click.option("--sort", "-s", type=click.Choice(["relevance", "stars", "name"]), default="relevance", help="Sort results by relevance, stars, or name")
def search(query: Optional[str], limit: int, type: Optional[str], sort: str) -> None:
    """
    Search for resources across configured registries.
    
    Currently supports searching the BioContext registry for MCP servers.
    """
    if not query:
        click.echo("❌ No search query provided. Use 'biotope search <query>'")
        raise click.Abort
    
    # Find biotope project root
    biotope_root = find_biotope_root()
    if not biotope_root:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort
    
    # Load project configuration
    try:
        config = load_biotope_config(biotope_root)
    except Exception as e:
        click.echo(f"❌ Failed to load project configuration: {e}")
        raise click.Abort
    
    # Get registry configuration
    registries = config.get("registries", {})
    mcp_registry = registries.get("mcp", {})
    
    if not mcp_registry:
        click.echo("❌ No MCP registry configured. Please run 'biotope init' to set up registry configuration.")
        raise click.Abort
    
    # Initialize registry manager
    registry_manager = RegistryManager(biotope_root)
    
    # Search BioContext registry
    try:
        registry_url = mcp_registry.get("url", "https://biocontext.ai/registry.json")
        biocontext = BioContextRegistry(registry_manager, registry_url)
        results = biocontext.search(query, limit, sort)
    except ValueError as e:
        click.echo(f"❌ Registry error: {e}")
        raise click.Abort
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}")
        raise click.Abort
    
    if not results:
        click.echo(f"🔍 No MCP servers found matching '{query}'")
        return
    
    # Display results
    console = Console()
    table = Table(title=f"MCP Servers matching '{query}'")
    
    table.add_column("Name", style="cyan")
    table.add_column("Identifier", style="green")
    table.add_column("Description", style="white")
    table.add_column("Keywords", style="yellow")
    table.add_column("Stars", style="magenta")
    
    for server in results:
        name = server.get("name", "Unknown")
        identifier = server.get("identifier", "Unknown")
        description = server.get("description", "No description")
        keywords = ", ".join(server.get("keywords", []))
        stars = server.get("stars", "—")
        
        # Truncate long descriptions
        if len(description) > 100:
            description = description[:97] + "..."
        
        table.add_row(name, identifier, description, keywords, str(stars))
    
    console.print(table)
    click.echo(f"\n💡 Found {len(results)} MCP server(s). Use 'biotope add <identifier>' to add one.") 