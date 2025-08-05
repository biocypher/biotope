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

## Output

The command displays results in a formatted table with the following columns:

- **Name**: Server name
- **Identifier**: Unique identifier (usually GitHub repository)
- **Description**: Server description (truncated if > 100 characters)
- **Keywords**: Associated keywords/tags

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