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
                
                # Calculate relevance score
                if sort == "relevance":
                    server_with_stars["_relevance_score"] = self._calculate_relevance_score(
                        server_with_stars, query_lower
                    )
                
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
        elif sort == "relevance":
            # Sort by relevance score (descending), then by name
            results.sort(key=lambda x: (
                -x.get("_relevance_score", 0),
                x.get("name", "").lower()
            ))
        
        return results[:limit]
    
    def _calculate_relevance_score(self, server: Dict, query: str) -> float:
        """Calculate relevance score for a server based on query."""
        score = 0.0
        
        # Exact name match (highest weight)
        if query in server.get("name", "").lower():
            score += 10.0
        
        # Partial name match
        elif any(word in server.get("name", "").lower() for word in query.split()):
            score += 8.0
        
        # Exact description match
        if query in server.get("description", "").lower():
            score += 5.0
        
        # Partial description match
        elif any(word in server.get("description", "").lower() for word in query.split()):
            score += 3.0
        
        # Keyword matches
        keywords = server.get("keywords", [])
        exact_keyword_matches = sum(1 for keyword in keywords if query in keyword.lower())
        partial_keyword_matches = sum(1 for keyword in keywords 
                                    if any(word in keyword.lower() for word in query.split()))
        
        score += exact_keyword_matches * 4.0
        score += partial_keyword_matches * 2.0
        
        # Star count bonus (small boost for popular servers)
        stars = server.get("stars", 0)
        if isinstance(stars, int) and stars > 0:
            # More generous scaling for biomedical repos (typically 10-500 stars)
            # 100 stars = 1.0 bonus, 500 stars = 2.0 bonus
            score += min(stars / 100.0, 3.0)  # Cap at 3.0 bonus
        
        return score
    
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
            
            # Prepare headers for GitHub API
            headers = {
                'User-Agent': 'biotope/1.0',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Add GitHub token if available (for higher rate limits)
            github_token = self._get_github_token()
            if github_token:
                headers['Authorization'] = f'token {github_token}'
            
            # Use a reasonable timeout to avoid hanging
            response = requests.get(api_url, headers=headers, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("stargazers_count", 0)
            elif response.status_code == 403:
                # Rate limited - return None gracefully
                return None
            else:
                return None
                
        except Exception:
            # Return None on any error (network, parsing, etc.)
            return None
    
    def _get_github_token(self) -> Optional[str]:
        """Get GitHub token from environment or config."""
        import os
        
        # Check environment variable first
        token = os.environ.get('GITHUB_TOKEN')
        if token:
            return token
        
        # Check for GitHub token in biotope config
        try:
            from biotope.validation import load_biotope_config
            from biotope.utils import find_biotope_root
            
            biotope_root = find_biotope_root()
            if biotope_root:
                config = load_biotope_config(biotope_root)
                return config.get('github_token')
        except Exception:
            pass
        
        return None 