# Search Command

!!! warning "Draft stage"

    Biotope is in draft stage. Functionality may be missing or incomplete.
    The API is subject to change.

Search for resources across configured registries.

## Overview

The `biotope search` command allows you to search for MCP servers and other resources across configured registries. Currently, it supports searching the BioContext registry for MCP servers.

## Usage

```bash
biotope search <query> [OPTIONS]
```

## Arguments

- **query**: Search term to find matching resources

## Options

- `--limit, -n`: Number of results to show (default: 10)
- `--type, -t`: Resource type to search (currently only 'mcp')
- `--sort, -s`: Sort results by relevance, stars, or name (default: relevance)

## Examples

### Basic Search

Search for MCP servers containing "PubMed":

```bash
biotope search PubMed
```

### Search with Limit

Limit results to 5 servers:

```bash
biotope search python --limit 5
```

### Search by Type

Explicitly search for MCP servers:

```bash
biotope search "clinical trials" --type mcp
```

### Sort by Popularity

Sort results by GitHub star count (most popular first):

```bash
biotope search PubMed --sort stars
```

### Sort by Name

Sort results alphabetically by name:

```bash
biotope search python --sort name
```

## Output

The command displays results in a formatted table with the following columns:

- **Name**: Server name
- **Identifier**: Unique identifier (usually GitHub repository)
- **Description**: Server description (truncated if > 100 characters)
- **Keywords**: Associated keywords/tags
- **Stars**: GitHub star count (if available)

## Configuration

The search command uses registry configuration from your biotope project. The configuration is automatically set up when you run `biotope init`.

### Registry Configuration

The search command reads registry settings from `.biotope/config/biotope.yaml`:

```yaml
registries:
  mcp:
    url: "https://biocontext.ai/registry.json"
    cache_duration: 3600
```

## Error Handling

The command handles various error conditions:

- **No query provided**: Shows usage instructions
- **Not in biotope project**: Prompts to run `biotope init`
- **No registry configured**: Prompts to run `biotope init`
- **Network errors**: Displays registry error message
- **No results**: Shows "No MCP servers found" message

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

- Uses BioContext registry (https://biocontext.ai/registry.json)
- Implements caching with configurable duration (1 hour default)
- Case-insensitive search across name, description, and keywords
- Rich table formatting for clear output
- Graceful error handling for network issues
- Fetches GitHub star counts for popularity ranking
- Supports sorting by relevance, stars, or name

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