# Search Command

!!! warning "Draft stage"

    Biotope is in draft stage. Functionality may be missing or incomplete.
    The API is subject to change.

Search for resources across configured registries.

## Overview

The `biotope search` command allows you to search for resources across configured registries. Currently, it supports:

- **MCP Servers**: Search the BioContext registry for Model Context Protocol servers
- **Bioinformatics Tools**: Search the bio.tools registry for bioinformatics software and tools

## Usage

```bash
biotope search <query> [OPTIONS]
```

## Arguments

- **query**: Search term to find matching resources

## Options

- `--limit, -n`: Number of results to show (default: 10)
- `--type, -t`: Resource type to search (mcp, biotools). If not specified, searches all registries
- `--sort, -s`: Sort results by relevance, impact, or name (default: relevance)

## Examples

### Basic Search (All Registries)

Search across all registries for "PubMed":

```bash
biotope search PubMed
```

This will return both MCP servers and bioinformatics tools, sorted by relevance.

### Search with Limit

Limit results to 5 resources:

```bash
biotope search python --limit 5
```

### Search by Type

Search for MCP servers only:

```bash
biotope search "clinical trials" --type mcp
```

Search for bioinformatics tools only:

```bash
biotope search "sequence alignment" --type biotools
```

### Sort by Impact

Sort results by impact (GitHub stars for MCP servers, citations for bioinformatics tools):

```bash
biotope search PubMed --sort impact
```

### Sort by Name

Sort results alphabetically by name:

```bash
biotope search python --sort name
```

### Sort by Impact

Sort results by impact (GitHub stars for MCP servers, citations for bioinformatics tools):

```bash
biotope search python --sort impact
```

## Output

The command displays results in a formatted table with the following columns:

- **Name**: Resource name
- **Identifier**: Unique identifier (GitHub repository for MCP servers, biotoolsID for tools)
- **Description**: Resource description (truncated if > 100 characters)
- **Keywords**: Associated keywords/tags
- **Impact Metrics**: 
  - **Stars**: GitHub star count (MCP-only searches)
  - **Citations**: Citation count (bio.tools-only searches)
  - **Impact**: GitHub stars for MCP servers, citation counts for bioinformatics tools (combined searches)
- **Type**: Resource type (shown only when searching all registries)

## Configuration

The search command uses registry configuration from your biotope project. The configuration is automatically set up when you run `biotope init`.

### Registry Configuration

The search command reads registry settings from `.biotope/config/biotope.yaml`:

```yaml
registries:
  mcp:
    url: "https://biocontext.ai/registry.json"
    cache_duration: 3600
  biotools:
    url: "https://bio.tools/api"
    cache_duration: 3600
```

## Error Handling

The command handles various error conditions:

- **No query provided**: Shows usage instructions
- **Not in biotope project**: Prompts to run `biotope init`
- **No registry configured**: Prompts to run `biotope init`
- **Network errors**: Displays registry error message
- **No results**: Shows "No resources found" message
- **Registry-specific errors**: Graceful handling of individual registry failures

## Next Steps

After finding a suitable MCP server, you can add it to your project:

```bash
biotope add <identifier>
```

For example:

```bash
biotope add genomoncology/biomcp
```

## Implementation Details

### MCP Registry (BioContext)
- Uses BioContext registry (https://biocontext.ai/registry.json)
- Fetches GitHub star counts for popularity ranking
- Implements caching with configurable duration (1 hour default)

### Bioinformatics Tools Registry (bio.tools)
- Uses bio.tools REST API (https://bio.tools/api)
- Searches across tool names, descriptions, topics, and functions
- No star counts (bio.tools doesn't provide popularity metrics)

### Common Features
- Case-insensitive search across name, description, and keywords
- Rich table formatting for clear output
- Graceful error handling for network issues
- Supports sorting by relevance, stars, or name
- Implements caching with configurable duration (1 hour default)

### Relevance Scoring Algorithm

When using `--sort relevance` (default), results are scored based on:

- **Exact name match**: 10.0 points (highest priority)
- **Partial name match**: 8.0 points
- **Exact description match**: 5.0 points
- **Partial description match**: 3.0 points
- **Exact keyword match**: 4.0 points per keyword
- **Partial keyword match**: 2.0 points per keyword
- **Star count bonus**: Up to 2.0 points for popular servers

Results are sorted by score (highest first), then alphabetically by name.

### GitHub Star Counts

Star counts are fetched from GitHub's API. Due to rate limiting, you may need to:

1. **Set GitHub Token**: Add `GITHUB_TOKEN` environment variable
2. **Configure in Project**: Add `github_token` to your `biotope.yaml` config
3. **Accept Limitations**: Without authentication, star counts may show "—" when rate limited

Example configuration:
```yaml
# In biotope.yaml
github_token: "ghp_your_token_here"
``` 