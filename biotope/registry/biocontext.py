"""BioContext registry integration."""

from typing import Dict, List, Optional
from .manager import RegistryManager


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