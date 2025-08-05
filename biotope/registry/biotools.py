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
                tool["_relevance_score"] = self._calculate_composite_score(tool, query_lower)
            
            results.append(tool)
        
        # Sort results based on sort parameter
        if sort == "name":
            # Sort by name
            results.sort(key=lambda x: x.get("name", "").lower())
        elif sort == "impact":
            # Sort by citations (descending), then by name
            def get_citation_value(tool):
                citations_str = tool.get("citations", "—")
                if citations_str == "—":
                    return 0
                try:
                    return int(citations_str)
                except (ValueError, TypeError):
                    return 0
            
            results.sort(key=lambda x: (
                -get_citation_value(x),
                x.get("name", "").lower()
            ))
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

    def _get_citation_count(self, tool: Dict) -> int:
        """Get citation count for a tool."""
        publications = tool.get("publication", [])
        if publications and len(publications) > 0:
            # Find the first publication with metadata
            for pub in publications:
                metadata = pub.get("metadata")
                if metadata is not None:
                    return metadata.get("citationCount", 0)
        return 0

    def _get_tool_metrics(self, tool: Dict) -> Dict:
        """Extract comprehensive metrics for a tool."""
        citations = self._get_citation_count(tool)
        validated = tool.get("validated", 0)
        homepage_status = tool.get("homepage_status", 0)
        elixir_badge = tool.get("elixir_badge", 0)
        
        # Calculate activity score based on recency
        addition_date = tool.get("additionDate", "")
        last_update = tool.get("lastUpdate", "")
        
        # Simple activity indicator (1 if updated in last year, 0.5 if older)
        activity_score = 0.5
        if last_update:
            try:
                from datetime import datetime, timezone
                last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                days_since_update = (now - last_update_dt).days
                if days_since_update < 365:  # Updated within last year
                    activity_score = 1.0
            except:
                pass
        
        return {
            "citations": citations,
            "validated": validated,
            "homepage_status": homepage_status,
            "elixir_badge": elixir_badge,
            "activity_score": activity_score,
            "addition_date": addition_date,
            "last_update": last_update
        }

    def _calculate_composite_score(self, tool: Dict, query: str) -> float:
        """Calculate composite score based on multiple metrics."""
        metrics = self._get_tool_metrics(tool)
        
        # Base relevance score
        relevance_score = self._calculate_relevance_score(tool, query)
        
        # Citation bonus (similar to GitHub stars)
        citation_bonus = min(metrics["citations"] / 1000.0, 3.0) if metrics["citations"] > 0 else 0
        
        # Quality bonus
        quality_bonus = 0.0
        if metrics["validated"]:
            quality_bonus += 0.5
        if metrics["homepage_status"]:
            quality_bonus += 0.3
        if metrics["elixir_badge"]:
            quality_bonus += 0.5
        if metrics["activity_score"] > 0.5:
            quality_bonus += 0.2
        
        return relevance_score + citation_bonus + quality_bonus

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

        # Get metrics
        metrics = self._get_tool_metrics(tool)
        
        # Format citations for display
        citations_display = str(metrics["citations"]) if metrics["citations"] > 0 else "—"

        return {
            "name": tool.get("name", "Unknown"),
            "identifier": tool.get("biotoolsID", "Unknown"),
            "description": tool.get("description", "No description"),
            "keywords": topic_terms + function_names,
            "homepage": tool.get("homepage", ""),
            "citations": citations_display,  # Store citations with appropriate key
            "_metrics": metrics  # Store full metrics for internal use
        } 