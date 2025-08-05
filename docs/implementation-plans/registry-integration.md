# Implementation Plan: BioContext Registry Integration

*First step: Enable biotope users to search the BioContext registry*

## Overview

This implementation plan covers the first phase of registry integration in biotope, focusing on integrating the BioContext registry (https://biocontext.ai/registry.json) to enable users to search for MCP servers.

## Goals

1. **Registry Integration**: Fetch and parse BioContext registry JSON
2. **Search Functionality**: Implement `biotope search` command
3. **Caching**: Implement efficient caching of registry data
4. **User Experience**: Provide rich, informative search results

## Implementation Steps

### Step 1: Create Registry Infrastructure

#### 1.1 Create Registry Manager
**File**: `biotope/registry/__init__.py`

```python
"""Registry management for biotope."""

from pathlib import Path
from typing import Dict, List, Optional
import json
import requests
from datetime import datetime, timedelta

class RegistryManager:
    """Manages registry operations for biotope."""
    
    def __init__(self, biotope_root: Path):
        self.biotope_root = biotope_root
        self.cache_dir = biotope_root / ".biotope" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_registry(self, url: str, cache_duration: int = 3600) -> List[Dict]:
        """Fetch registry data with caching."""
        cache_file = self.cache_dir / f"registry_{hash(url)}.json"
        
        # Check cache first
        if cache_file.exists():
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age.total_seconds() < cache_duration:
                try:
                    with open(cache_file) as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass
        
        # Fetch from remote
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            registry_data = response.json()
            
            # Cache the result
            with open(cache_file, 'w') as f:
                json.dump(registry_data, f)
            
            return registry_data
        except (requests.RequestException, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to fetch registry from {url}: {e}")
```

#### 1.2 Create BioContext Registry Handler
**File**: `biotope/registry/biocontext.py`

```python
"""BioContext registry integration."""

from typing import Dict, List, Optional
from . import RegistryManager

class BioContextRegistry:
    """Handles BioContext registry operations."""
    
    def __init__(self, registry_manager: RegistryManager):
        self.registry_manager = registry_manager
        self.url = "https://biocontext.ai/registry.json"
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Search BioContext registry for MCP servers."""
        registry_data = self.registry_manager.fetch_registry(self.url)
        
        results = []
        query_lower = query.lower()
        
        for server in registry_data:
            # Search in name, description, and keywords
            if (query_lower in server.get("name", "").lower() or
                query_lower in server.get("description", "").lower() or
                any(query_lower in keyword.lower() for keyword in server.get("keywords", []))):
                
                results.append(server)
                
                if len(results) >= limit:
                    break
        
        return results
    
    def get_server(self, identifier: str) -> Optional[Dict]:
        """Get specific server by identifier."""
        registry_data = self.registry_manager.fetch_registry(self.url)
        
        for server in registry_data:
            if server.get("identifier") == identifier:
                return server
        
        return None
```

### Step 2: Implement Search Command

#### 2.1 Create Search Command
**File**: `biotope/commands/search.py`

```python
"""Search command implementation."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from biotope.utils import find_biotope_root
from biotope.registry import RegistryManager
from biotope.registry.biocontext import BioContextRegistry


@click.command()
@click.argument("query", required=False)
@click.option("--limit", "-n", default=10, help="Number of results to show")
@click.option("--type", "-t", help="Resource type to search (currently only 'mcp')")
def search(query: Optional[str], limit: int, type: Optional[str]) -> None:
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
    
    # Initialize registry manager
    registry_manager = RegistryManager(biotope_root)
    
    # Search BioContext registry
    biocontext = BioContextRegistry(registry_manager)
    results = biocontext.search(query, limit)
    
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
    
    for server in results:
        name = server.get("name", "Unknown")
        identifier = server.get("identifier", "Unknown")
        description = server.get("description", "No description")
        keywords = ", ".join(server.get("keywords", []))
        
        # Truncate long descriptions
        if len(description) > 100:
            description = description[:97] + "..."
        
        table.add_row(name, identifier, description, keywords)
    
    console.print(table)
    click.echo(f"\n💡 Found {len(results)} MCP server(s). Use 'biotope add <identifier>' to add one.")
```

#### 2.2 Add Search Command to CLI
**File**: `biotope/cli.py`

```python
# Add import
from biotope.commands.search import search

# Add to command group
cli.add_command(search)
```

### Step 3: Update Project Configuration

#### 3.1 Add Registry Configuration to Init
**File**: `biotope/commands/init.py`

Update the `create_project_structure` function to include registry configuration:

```python
# Add to biotope_config dictionary
biotope_config["registries"] = {
    "mcp": {
        "url": "https://biocontext.ai/registry.json",
        "cache_duration": 3600
    }
}
```

### Step 4: Testing

#### 4.1 Create Test Files
**File**: `tests/commands/test_search.py`

```python
"""Test search command functionality."""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from biotope.commands.search import search


@pytest.fixture
def mock_registry_data():
    """Mock BioContext registry data."""
    return [
        {
            "name": "BioMCP",
            "identifier": "genomoncology/biomcp",
            "description": "A Model Context Protocol server for bioinformatics",
            "keywords": ["PubMed", "ClinicalTrials", "MyVariant", "python"]
        },
        {
            "name": "AACT MCP",
            "identifier": "navisbio/AACT_MCP",
            "description": "Clinical trials data access",
            "keywords": ["AACT", "python"]
        }
    ]


def test_search_command_success(biotope_project, mock_registry_data):
    """Test successful search command."""
    runner = CliRunner()
    
    with patch("biotope.registry.RegistryManager.fetch_registry") as mock_fetch:
        mock_fetch.return_value = mock_registry_data
        
        result = runner.invoke(search, ["PubMed"])
        
        assert result.exit_code == 0
        assert "BioMCP" in result.output
        assert "genomoncology/biomcp" in result.output


def test_search_command_no_results(biotope_project):
    """Test search with no results."""
    runner = CliRunner()
    
    with patch("biotope.registry.RegistryManager.fetch_registry") as mock_fetch:
        mock_fetch.return_value = []
        
        result = runner.invoke(search, ["nonexistent"])
        
        assert result.exit_code == 0
        assert "No MCP servers found" in result.output


def test_search_command_no_query(biotope_project):
    """Test search without query."""
    runner = CliRunner()
    
    result = runner.invoke(search, [])
    
    assert result.exit_code != 0
    assert "No search query provided" in result.output
```

### Step 5: Documentation Updates

#### 5.1 Update API Documentation
**File**: `docs/api-docs/search.md`

```markdown
# Search Command

Search for resources across configured registries.

## Usage

```bash
biotope search <query>
```

## Options

- `--limit, -n`: Number of results to show (default: 10)
- `--type, -t`: Resource type to search (currently only 'mcp')

## Examples

```bash
# Search for PubMed-related MCP servers
biotope search "PubMed"

# Search with custom limit
biotope search "clinical" --limit 5
```

## Output

The command displays results in a table format showing:
- Name of the MCP server
- Identifier (for use with `biotope add`)
- Description
- Keywords
```

## Implementation Tasks

### Task 1: Registry Infrastructure
- [x] Create registry management infrastructure (`RegistryManager`)
- [x] Implement BioContext registry handler (`BioContextRegistry`)
- [x] Add basic caching functionality

### Task 2: Search Command
- [ ] Implement search command (`biotope/commands/search.py`)
- [ ] Add search command to CLI (`biotope/cli.py`)
- [ ] Create comprehensive tests (`tests/commands/test_search.py`)

### Task 3: Configuration Integration
- [ ] Update project configuration to include registry settings
- [ ] Add registry configuration to init command

### Task 4: Documentation & Polish
- [ ] Write API documentation (`docs/api-docs/search.md`)
- [ ] Update user guides and examples
- [ ] Integration testing and error handling improvements

## Success Criteria

1. **Functional Search**: Users can search BioContext registry
2. **Rich Results**: Search results show relevant information
3. **Caching**: Registry data is cached efficiently
4. **Error Handling**: Graceful handling of network issues
5. **User Experience**: Clear, helpful output and error messages

## Future Enhancements

After this implementation, the next steps would be:
1. **Add Command**: Implement `biotope add` for MCP servers
2. **Multiple Registries**: Support for KG registry
3. **Advanced Filtering**: Category, language, and other filters
4. **Interactive Search**: Rich interactive search interface

This implementation provides the foundation for registry integration while keeping the scope focused and achievable. 