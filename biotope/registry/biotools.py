"""BioTools registry integration."""

from typing import Dict, List, Optional
import re
from .manager import RegistryManager


class BioToolsRegistry:
    """Handles BioTools registry operations."""
    
    def __init__(self, registry_manager: RegistryManager, base_url: str = "https://bio.tools/api"):
        self.registry_manager = registry_manager
        self.base_url = base_url
    
    def search(self, query: str, limit: int = 10, sort: str = "relevance") -> List[Dict]:
        """Search BioTools registry for bioinformatics tools."""
        # Fetch tools from bio.tools API
        tools_data = self._fetch_tools(query, limit)
        
        results = []
        query_lower = query.lower()
        
        for tool in tools_data:
            # Calculate relevance score
            if sort == "relevance":
                tool["_relevance_score"] = self._calculate_relevance_score(tool, query_lower)
            
            results.append(tool)
        
        # Sort results based on sort parameter
        if sort == "name":
            # Sort by name
            results.sort(key=lambda x: x.get("name", "").lower())
        elif sort == "relevance":
            # Sort by relevance score (descending), then by name
            results.sort(key=lambda x: (
                -x.get("_relevance_score", 0),
                x.get("name", "").lower()
            ))
        
        return results[:limit]
    
    def get_tool(self, biotools_id: str) -> Optional[Dict]:
        """Get specific tool by biotoolsID."""
        try:
            import requests
            
            url = f"{self.base_url}/tool/{biotools_id}?format=json"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception:
            return None
    
    def _fetch_tools(self, query: str, limit: int) -> List[Dict]:
        """Fetch tools from bio.tools API with search."""
        try:
            import requests
            
            # Search bio.tools API
            url = f"{self.base_url}/tool"
            params = {
                "format": "json",
                "page": 1,
                "pageSize": limit * 2,  # Fetch more to allow for filtering
                "q": query
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data.get("list", [])
            
        except Exception:
            return []
    
    def _calculate_relevance_score(self, tool: Dict, query: str) -> float:
        """Calculate relevance score for a tool based on query."""
        score = 0.0
        
        # Exact name match (highest weight)
        if query in tool.get("name", "").lower():
            score += 10.0
        
        # Partial name match
        elif any(word in tool.get("name", "").lower() for word in query.split()):
            score += 8.0
        
        # Exact description match
        if query in tool.get("description", "").lower():
            score += 5.0
        
        # Partial description match
        elif any(word in tool.get("description", "").lower() for word in query.split()):
            score += 3.0
        
        # Topic matches (bio.tools specific)
        topics = tool.get("topic", [])
        for topic in topics:
            topic_term = topic.get("term", "").lower()
            if query in topic_term:
                score += 4.0  # Topic match
            elif any(word in topic_term for word in query.split()):
                score += 2.0  # Partial topic match
        
        # Function matches (bio.tools specific)
        functions = tool.get("function", [])
        for func in functions:
            if isinstance(func, dict):
                func_name = func.get("name", "").lower()
                if query in func_name:
                    score += 3.0  # Function match
                elif any(word in func_name for word in query.split()):
                    score += 1.5  # Partial function match
        
        return score
    
    def _format_tool_for_display(self, tool: Dict) -> Dict:
        """Format tool data for display in search results."""
        # Extract topic terms for display
        topics = tool.get("topic", [])
        topic_terms = [topic.get("term", "") for topic in topics if isinstance(topic, dict)]
        
        # Extract function names for display
        functions = tool.get("function", [])
        function_names = []
        for func in functions:
            if isinstance(func, dict):
                func_name = func.get("name", "")
                if func_name:
                    function_names.append(func_name)
        
        return {
            "name": tool.get("name", "Unknown"),
            "identifier": tool.get("biotoolsID", "Unknown"),
            "description": tool.get("description", "No description"),
            "keywords": topic_terms + function_names,
            "homepage": tool.get("homepage", ""),
            "stars": "—"  # bio.tools doesn't have star counts
        } 