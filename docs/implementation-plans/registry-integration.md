# Implementation Plan: BioContext Registry Integration

*Phase 1 Complete: Search functionality with star count ranking*

## Overview

This implementation plan covers registry integration in biotope, focusing on integrating the BioContext registry (https://biocontext.ai/registry.json) to enable users to search for and add MCP servers.

## Completed Goals (Phase 1)

1. ✅ **Registry Integration**: Fetch and parse BioContext registry JSON
2. ✅ **Search Functionality**: Implement `biotope search` command with rich results
3. ✅ **Star Count Ranking**: GitHub star count display and sorting
4. ✅ **Caching**: Implement efficient caching of registry data
5. ✅ **User Experience**: Provide rich, informative search results with sorting

## Current Implementation Status

### ✅ Completed Features

#### Registry Infrastructure
- **RegistryManager**: Handles registry fetching with caching
- **BioContextRegistry**: BioContext-specific registry operations
- **Caching**: Configurable cache duration with automatic cleanup

#### Search Command
- **Basic Search**: Search across name, description, and keywords
- **Star Count Display**: Shows GitHub stars for each MCP server
- **Sorting Options**: 
  - `--sort relevance` (default): Search relevance order
  - `--sort stars`: Sort by GitHub stars (highest first)
  - `--sort name`: Sort alphabetically by name
- **Rich Output**: Formatted tables with star counts
- **Error Handling**: Network timeouts, API failures, graceful degradation

#### Configuration Integration
- **Project Config**: Registry settings in `biotope.yaml`
- **Init Integration**: Registry configuration during project initialization
- **Status Integration**: MCP registry status in `biotope status`

#### Testing & Documentation
- **Comprehensive Tests**: Unit tests for registry and search functionality
- **API Documentation**: Complete search command documentation
- **Error Scenarios**: Network failures, API errors, malformed data

### 🎯 Next Phase Goals (Phase 2)

1. **Add Command**: Implement `biotope add` for MCP servers
2. **Git Integration**: Clone repositories as submodules or direct clones
3. **Metadata Management**: Create Croissant ML metadata for MCP servers
4. **Validation**: Ensure MCP servers are properly structured

## Implementation Tasks

### ✅ Task 1: Registry Infrastructure (COMPLETED)
- [x] Create registry management infrastructure (`RegistryManager`)
- [x] Implement BioContext registry handler (`BioContextRegistry`)
- [x] Add basic caching functionality
- [x] Add GitHub star count fetching
- [x] Implement sorting algorithms

### ✅ Task 2: Search Command (COMPLETED)
- [x] Implement search command (`biotope/commands/search.py`)
- [x] Add search command to CLI (`biotope/cli.py`)
- [x] Create comprehensive tests (`tests/commands/test_search.py`)
- [x] Add star count display and sorting
- [x] Implement error handling and timeouts

### ✅ Task 3: Configuration Integration (COMPLETED)
- [x] Update project configuration to include registry settings
- [x] Add registry configuration to init command
- [x] Integrate MCP status into `biotope status`

### ✅ Task 4: Documentation & Polish (COMPLETED)
- [x] Write API documentation (`docs/api-docs/search.md`)
- [x] Update user guides and examples
- [x] Integration testing and error handling improvements
- [x] Add comprehensive unit tests for star fetching

### 🚧 Task 5: Add Command Implementation (NEXT)
- [ ] Extend `biotope add` to handle MCP server identifiers
- [ ] Implement Git clone/submodule functionality for local servers
- [ ] Add remote endpoint support for hosted MCP servers
- [ ] Create MCP-specific metadata templates
- [ ] Add validation for MCP server structure
- [ ] Update `biotope status` to show added MCP servers
- [ ] Implement server type detection (local vs remote)

### 🔮 Task 6: Advanced Features (FUTURE)
- [ ] Multiple registry support (KG registry)
- [ ] Advanced filtering (category, language, etc.)
- [ ] Interactive search interface
- [ ] MCP server validation and testing
- [ ] Integration with MCP client libraries

## Success Criteria

### ✅ Phase 1 Achievements
1. **Functional Search**: Users can search BioContext registry with rich results
2. **Star Count Ranking**: Popular servers are highlighted and sortable
3. **Caching**: Registry data is cached efficiently with configurable duration
4. **Error Handling**: Graceful handling of network issues and API failures
5. **User Experience**: Clear, helpful output with sorting options

### 🎯 Phase 2 Goals
1. **Add Functionality**: Users can add MCP servers to their projects
2. **Git Integration**: Proper version control for MCP server code
3. **Remote Endpoint Support**: Support for hosted MCP servers
4. **Metadata Management**: Consistent metadata for MCP servers
5. **Validation**: Ensure added servers are properly structured

### 🔧 MCP Server Types

#### Local Servers (Current BioContext Registry)
- **Source**: GitHub repositories
- **Deployment**: Local installation required
- **Action**: Git clone + local setup
- **Example**: `genomoncology/biomcp`
- **Metadata**: Repository URL, local path, setup instructions

#### Remote Servers (Future Enhancement)
- **Source**: Hosted endpoints
- **Deployment**: Already running remotely
- **Action**: Add endpoint configuration
- **Example**: `https://mcp.biocontext.ai/mcp/`
- **Metadata**: Endpoint URL, authentication, API documentation

## Current Usage Examples

### Search with Star Ranking
```bash
# Search for PubMed servers, sorted by popularity
biotope search PubMed --sort stars

# Search for Python servers, sorted by name
biotope search python --sort name

# Basic search (relevance sorted)
biotope search "clinical trials"
```

### Status Integration
```bash
# Check MCP registry status
biotope status
```

### Proposed Add Command Workflow

#### For Local Servers
```bash
# Search for servers
biotope search PubMed --sort stars

# Add local server (clones repository)
biotope add genomoncology/biomcp

# Status shows local MCP servers
biotope status
```

#### For Remote Servers (Future)
```bash
# Add remote server (configures endpoint)
biotope add biocontext.ai/pubmed-mcp --endpoint https://api.biocontext.ai/pubmed

# Status shows both local and remote servers
biotope status
```

### Implementation Considerations

#### Local Server Integration
- **Git Clone**: Clone repository to `.biotope/mcp-servers/`
- **Setup Scripts**: Run installation/setup scripts if available
- **Dependencies**: Handle Python/Node.js dependencies
- **Configuration**: Generate MCP client configuration

#### Remote Server Integration
- **Endpoint Validation**: Test endpoint connectivity
- **Authentication**: Handle API keys and authentication
- **Configuration**: Store endpoint URLs and credentials
- **Health Checks**: Monitor endpoint availability

## Future Enhancements

After Phase 2 implementation, the next steps would be:
1. **Multiple Registries**: Support for KG registry and other registries
2. **Advanced Filtering**: Category, language, and other filters
3. **Interactive Search**: Rich interactive search interface
4. **MCP Validation**: Validate MCP server compatibility and structure
5. **Integration Testing**: Test MCP servers with actual MCP clients

This implementation provides a solid foundation for registry integration with a focus on user experience and reliability. 