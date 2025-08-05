"""BioContext registry integration."""

from typing import Dict, List, Optional
import re
from .manager import RegistryManager


class BioContextRegistry:
    """Handles BioContext registry operations."""
    
    def __init__(self, registry_manager: RegistryManager, url: str = "https://biocontext.ai/registry.json"):
        self.registry_manager = registry_manager
        self.url = url
    
    def search(self, query: str, limit: int = 10, sort: str = "relevance") -> List[Dict]:
        """Search BioContext registry for MCP servers."""
        registry_data = self.registry_manager.fetch_registry(self.url)
        
        results = []
        query_lower = query.lower()
        
        for server in registry_data:
            # Search in name, description, and keywords
            if (query_lower in server.get("name", "").lower() or
                query_lower in server.get("description", "").lower() or
                any(query_lower in keyword.lower() for keyword in server.get("keywords", []))):
                
                # Add star count if available
                server_with_stars = server.copy()
                if "codeRepository" in server:
                    stars = self._get_github_stars(server["codeRepository"])
                    if stars is not None:
                        server_with_stars["stars"] = stars
                    else:
                        server_with_stars["stars"] = "—"
                else:
                    server_with_stars["stars"] = "—"
                
                results.append(server_with_stars)
        
        # Sort results based on sort parameter
        if sort == "stars":
            # Sort by stars (descending), then by name
            results.sort(key=lambda x: (
                -int(x.get("stars", 0)) if isinstance(x.get("stars"), int) else 0,
                x.get("name", "").lower()
            ))
        elif sort == "name":
            # Sort by name
            results.sort(key=lambda x: x.get("name", "").lower())
        # relevance is default - keep original order (most relevant first)
        
        return results[:limit]
    
    def get_server(self, identifier: str) -> Optional[Dict]:
        """Get specific server by identifier."""
        registry_data = self.registry_manager.fetch_registry(self.url)
        
        for server in registry_data:
            if server.get("identifier") == identifier:
                return server
        
        return None
    
    def _get_github_stars(self, repo_url: str) -> Optional[int]:
        """Get GitHub star count for a repository URL."""
        try:
            import requests
            
            # Extract owner/repo from GitHub URL
            match = re.search(r'github\.com/([^/]+/[^/]+)', repo_url)
            if not match:
                return None
            
            repo_path = match.group(1)
            api_url = f"https://api.github.com/repos/{repo_path}"
            
            # Use a reasonable timeout to avoid hanging
            response = requests.get(api_url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                return data.get("stargazers_count", 0)
            else:
                return None
                
        except Exception:
            # Return None on any error (network, parsing, etc.)
            return None 