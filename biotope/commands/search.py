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
from biotope.registry.biotools import BioToolsRegistry


@click.command()
@click.argument("query", required=False)
@click.option("--limit", "-n", default=10, help="Number of results to show")
@click.option("--type", "-t", help="Resource type to search (mcp, biotools)")
@click.option("--sort", "-s", type=click.Choice(["relevance", "impact", "name"]), default="relevance", help="Sort results by relevance, impact, or name")
def search(query: Optional[str], limit: int, type: Optional[str], sort: str) -> None:
    """
    Search for resources across configured registries.
    """
    if not query:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
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
    
    # Determine which registries to search
    search_type = type  # None means search all registries
    
    if search_type == "mcp":
        # Search only MCP registry
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
            registry_name = "MCP Servers"
        except ValueError as e:
            click.echo(f"❌ Registry error: {e}")
            raise click.Abort
        except Exception as e:
            click.echo(f"❌ Unexpected error: {e}")
            raise click.Abort
    
    elif search_type == "biotools":
        # Search only bio.tools registry
        # Initialize registry manager
        registry_manager = RegistryManager(biotope_root)
        
        # Search bio.tools registry
        try:
            biotools = BioToolsRegistry(registry_manager)
            raw_results = biotools.search(query, limit, sort)
            
            # Format results for display
            results = []
            for tool in raw_results:
                formatted_tool = biotools._format_tool_for_display(tool)
                results.append(formatted_tool)
            
            registry_name = "Bioinformatics Tools"
        except Exception as e:
            click.echo(f"❌ bio.tools API error: {e}")
            raise click.Abort
    
    elif search_type is None:
        # Search all available registries
        all_results = []
        registry_manager = RegistryManager(biotope_root)
        
        # Search MCP registry if configured
        mcp_registry = registries.get("mcp", {})
        if mcp_registry:
            try:
                registry_url = mcp_registry.get("url", "https://biocontext.ai/registry.json")
                biocontext = BioContextRegistry(registry_manager, registry_url)
                mcp_results = biocontext.search(query, limit, sort)
                
                # Add registry type to results for identification
                for result in mcp_results:
                    result["_registry_type"] = "mcp"
                    result["_registry_name"] = "MCP Server"
                
                all_results.extend(mcp_results)
            except Exception as e:
                click.echo(f"⚠️  MCP registry error: {e}")
        
        # Search bio.tools registry
        try:
            biotools = BioToolsRegistry(registry_manager)
            raw_biotools_results = biotools.search(query, limit, sort)
            
            # Format and add bio.tools results
            for tool in raw_biotools_results:
                formatted_tool = biotools._format_tool_for_display(tool)
                formatted_tool["_registry_type"] = "biotools"
                formatted_tool["_registry_name"] = "Bioinformatics Tool"
                all_results.append(formatted_tool)
        except Exception as e:
            click.echo(f"⚠️  bio.tools API error: {e}")
        
        # Sort combined results
        if sort == "relevance":
            # Preserve the registry's ranking order (which already considers impact and relevance)
            # The results are already in the correct order from the registry
            pass
        elif sort == "impact":
            # Sort by impact (stars for MCP, citations for bio.tools)
            def get_impact_value(result):
                # MCP servers use "stars", bio.tools use "citations"
                impact_str = result.get("stars", result.get("citations", "—"))
                if impact_str == "—":
                    return 0
                try:
                    return int(impact_str)
                except (ValueError, TypeError):
                    return 0
            
            all_results.sort(key=lambda x: (
                -get_impact_value(x),
                x.get("name", "").lower()
            ))
        elif sort == "name":
            all_results.sort(key=lambda x: x.get("name", "").lower())
        
        results = all_results[:limit]
        registry_name = "All Resources"
    
    else:
        click.echo(f"❌ Unknown registry type: {search_type}. Supported types: mcp, biotools")
        raise click.Abort
    
    if not results:
        click.echo(f"🔍 No {registry_name.lower()} found matching '{query}'")
        return
    
    # Display results
    console = Console()
    table = Table(title=f"{registry_name} matching '{query}'")
    
    table.add_column("Name", style="cyan")
    table.add_column("Identifier", style="green")
    table.add_column("Description", style="white")
    table.add_column("Keywords", style="yellow")
    
    # Smart column labeling based on search type
    if search_type == "mcp":
        table.add_column("Stars", style="magenta")
    elif search_type == "biotools":
        table.add_column("Citations", style="magenta")
    else:  # Combined search
        table.add_column("Impact", style="magenta")
        table.add_column("Type", style="blue")
    
    for server in results:
        name = server.get("name", "Unknown")
        identifier = server.get("identifier", "Unknown")
        description = server.get("description", "No description")
        keywords = ", ".join(server.get("keywords", []))
        
        # Get impact value based on registry type
        if search_type == "mcp":
            impact_value = server.get("stars", "—")
        elif search_type == "biotools":
            impact_value = server.get("citations", "—")
        else:  # Combined search
            # MCP servers use "stars", bio.tools use "citations"
            impact_value = server.get("stars", server.get("citations", "—"))
        
        # Truncate long descriptions
        if len(description) > 100:
            description = description[:97] + "..."
        
        if search_type == "mcp":
            table.add_row(name, identifier, description, keywords, str(impact_value))
        elif search_type == "biotools":
            table.add_row(name, identifier, description, keywords, str(impact_value))
        else:  # Combined search
            registry_type = server.get("_registry_name", "Unknown")
            table.add_row(name, identifier, description, keywords, str(impact_value), registry_type)
    
    console.print(table)
    
    if search_type == "mcp":
        click.echo(f"\n💡 Found {len(results)} MCP server(s). Use 'biotope add <identifier>' to add one.")
    elif search_type == "biotools":
        click.echo(f"\n💡 Found {len(results)} bioinformatics tool(s). Visit bio.tools for more details.")
    elif search_type is None:
        # Count results by type
        mcp_count = sum(1 for r in results if r.get("_registry_type") == "mcp")
        biotools_count = sum(1 for r in results if r.get("_registry_type") == "biotools")
        
        click.echo(f"\n💡 Found {len(results)} resource(s): {mcp_count} MCP server(s), {biotools_count} bioinformatics tool(s)")
        click.echo("   Impact: GitHub stars for MCP servers, citation counts for bioinformatics tools")
        click.echo("   Use 'biotope add <identifier>' for MCP servers, or visit bio.tools for tool details.") 