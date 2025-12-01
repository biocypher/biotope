"""BioTools registry integration."""

from typing import Dict, List, Optional
import re
from .manager import RegistryManager
import math


class BioToolsRegistry:
    """Handles BioTools registry operations."""
    
    def __init__(self, registry_manager: RegistryManager, base_url: str = "https://bio.tools/api"):
        self.registry_manager = registry_manager
        self.base_url = base_url
    
    def search(self, query: str, limit: int = 10, sort: str = "relevance") -> List[Dict]:
        """Search BioTools registry for bioinformatics tools using rank-based aggregation."""
        # Fetch tools from bio.tools API
        tools_data = self._fetch_tools(query, limit)
        
        results = []
        query_lower = query.lower()
        
        # Compute raw scores for all aspects
        for tool in tools_data:
            # Ensure identifier is present for ranking
            tool["identifier"] = tool.get("biotoolsID", tool.get("name", "unknown"))
            tool["_relevance_score"] = self._calculate_relevance_score(tool, query_lower)
            tool["_composite_method_score"] = self._calculate_composite_score(tool, query_lower, tools_data)
            metrics = self._get_tool_metrics(tool)
            tool["_impact_score"] = metrics["citations"]
            tool["_quality_score"] = (
                (0.3 if metrics["validated"] else 0) +
                (0.2 if metrics["homepage_status"] else 0) +
                (0.3 if metrics["elixir_badge"] else 0) +
                (0.2 if metrics["activity_score"] > 0.5 else 0)
            )
            results.append(tool)
        
        # Direct weighted scoring instead of rank-based aggregation
        max_relevance = max([t["_relevance_score"] for t in results]) if results else 1
        max_impact = max([t["_impact_score"] for t in results]) if results else 1
        max_quality = max([t["_quality_score"] for t in results]) if results else 1
        
        for tool in results:
            # Normalize scores to 0-1 range
            normalized_relevance = tool["_relevance_score"] / max_relevance if max_relevance > 0 else 0
            normalized_impact = tool["_impact_score"] / max_impact if max_impact > 0 else 0
            normalized_quality = tool["_quality_score"] / max_quality if max_quality > 0 else 0
            
            # Weighted combination: 15% relevance, 70% impact, 15% quality
            tool["_composite_score"] = (
                0.15 * normalized_relevance +
                0.70 * normalized_impact +
                0.15 * normalized_quality
            )
        
        # Sort by impact score first, then by relevance (prioritize high-impact tools)
        results.sort(key=lambda x: (-x["_impact_score"], -x["_relevance_score"], x.get("name", "").lower()))
        
        # If sort == "impact", sort by impact only
        if sort == "impact":
            results.sort(key=lambda x: (-x["_impact_score"], x.get("name", "").lower()))
        # If sort == "name", sort by name only
        elif sort == "name":
            results.sort(key=lambda x: x.get("name", "").lower())
        # If sort == "composite", use _calculate_composite_score method (25% relevance, 45% impact, 30% quality)
        elif sort == "composite":
            results.sort(key=lambda x: (-x["_composite_method_score"], x.get("name", "").lower()))
        # If sort == "relevance", use the composite score order (already sorted above)
        
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
        
        # Exact name match (reduced weight)
        if query in tool.get("name", "").lower():
            score += 5.0
        
        # Partial name match
        elif any(word in tool.get("name", "").lower() for word in query.split()):
            score += 4.0
        
        # Exact description match
        if query in tool.get("description", "").lower():
            score += 2.5
        
        # Partial description match
        elif any(word in tool.get("description", "").lower() for word in query.split()):
            score += 1.5
        
        # Topic matches (bio.tools specific)
        topics = tool.get("topic", [])
        for topic in topics:
            topic_term = topic.get("term", "").lower()
            if query in topic_term:
                score += 2.0  # Topic match
            elif any(word in topic_term for word in query.split()):
                score += 1.0  # Partial topic match
        
        # Function matches (bio.tools specific)
        functions = tool.get("function", [])
        for func in functions:
            if isinstance(func, dict):
                func_name = func.get("name", "").lower()
                if query in func_name:
                    score += 1.5  # Function match
                elif any(word in func_name for word in query.split()):
                    score += 0.75  # Partial function match
        
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
        """Extract comprehensive metrics for a tool using available bio.tools API data."""
        citations = self._get_citation_count(tool)
        validated = tool.get("validated", 0)
        homepage_status = tool.get("homepage_status", 0)
        elixir_badge = tool.get("elixir_badge", 0)
        
        # Enhanced activity scoring based on recency and tool age
        addition_date = tool.get("additionDate", "")
        last_update = tool.get("lastUpdate", "")
        
        # Calculate activity score based on multiple factors
        activity_score = 0.0
        tool_age_score = 0.0
        recency_score = 0.0
        
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            
            # Calculate tool age (how long it's been in bio.tools)
            if addition_date:
                addition_dt = datetime.fromisoformat(addition_date.replace('Z', '+00:00'))
                tool_age_days = (now - addition_dt).days
                # Tools older than 2 years get a small bonus (established)
                if tool_age_days > 730:  # 2 years
                    tool_age_score = 0.3
                elif tool_age_days > 365:  # 1 year
                    tool_age_score = 0.2
                else:
                    tool_age_score = 0.1  # New tools get small bonus
            
            # Calculate recency score (how recently updated)
            if last_update:
                last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                days_since_update = (now - last_update_dt).days
                if days_since_update < 30:  # Updated in last month
                    recency_score = 1.0
                elif days_since_update < 90:  # Updated in last 3 months
                    recency_score = 0.8
                elif days_since_update < 365:  # Updated in last year
                    recency_score = 0.5
                else:
                    recency_score = 0.2  # Not updated recently
            
            activity_score = tool_age_score + recency_score
        except:
            activity_score = 0.5  # Fallback
        
        # Additional quality indicators from bio.tools API
        maturity = tool.get("maturity", "")
        confidence_flag = tool.get("confidence_flag", 0)
        documentation = tool.get("documentation", "")
        download = tool.get("download", "")
        elixir_platform = tool.get("elixirPlatform", "")
        elixir_node = tool.get("elixirNode", "")
        
        # Calculate comprehensive quality score
        quality_indicators = 0.0
        if validated:
            quality_indicators += 0.2
        if homepage_status:
            quality_indicators += 0.1
        if elixir_badge:
            quality_indicators += 0.2
        if elixir_platform or elixir_node:
            quality_indicators += 0.1  # ELIXIR association
        if documentation:
            quality_indicators += 0.1  # Has documentation
        if download:
            quality_indicators += 0.1  # Has download link
        if maturity and maturity.lower() in ["production", "stable"]:
            quality_indicators += 0.2  # Production-ready
        if confidence_flag:
            quality_indicators += 0.1  # High confidence
        
        return {
            "citations": citations,
            "validated": validated,
            "homepage_status": homepage_status,
            "elixir_badge": elixir_badge,
            "activity_score": activity_score,
            "tool_age_score": tool_age_score,
            "recency_score": recency_score,
            "quality_indicators": quality_indicators,
            "maturity": maturity,
            "confidence_flag": confidence_flag,
            "addition_date": addition_date,
            "last_update": last_update
        }

    def _calculate_composite_score(self, tool: Dict, query: str, all_tools: List[Dict] = None) -> float:
        """Calculate composite score based on multiple metrics with weighted ranking."""
        metrics = self._get_tool_metrics(tool)
        
        # Base relevance score (0-20 range)
        relevance_score = self._calculate_relevance_score(tool, query)
        
        # Normalize relevance score to 0-1 range using percentile ranking
        if all_tools:
            all_relevance_scores = [self._calculate_relevance_score(t, query) for t in all_tools]
            if all_relevance_scores:
                max_relevance = max(all_relevance_scores)
                normalized_relevance = relevance_score / max_relevance if max_relevance > 0 else 0
            else:
                normalized_relevance = 0
        else:
            normalized_relevance = min(relevance_score / 20.0, 1.0)
        
        # Quality score (0-1 range) - now uses comprehensive quality indicators
        quality_score = metrics["quality_indicators"]
        
        # Enhanced impact scoring with fallback for missing citations
        impact_score = 0.0
        if all_tools and metrics["citations"] > 0:
            # Calculate relative citation ranking
            all_citations = [self._get_citation_count(t) for t in all_tools]
            max_citations = max(all_citations) if all_citations else 1
            impact_score = metrics["citations"] / max_citations
        elif metrics["citations"] > 0:
            # Fallback: use log scale for absolute citations
            impact_score = min(math.log10(metrics["citations"] + 1) / 4.0, 1.0)
        else:
            # No citations available - use activity and quality as impact proxy
            # This helps tools with good activity/quality but no citations
            impact_score = (metrics["activity_score"] + quality_score) / 2.0
        
        # Weighted combination: 25% relevance, 45% impact, 30% quality
        # Adjusted weights to give more importance to quality when citations are missing
        composite_score = (
            0.25 * normalized_relevance +
            0.45 * impact_score +
            0.30 * quality_score
        )
        
        return composite_score

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