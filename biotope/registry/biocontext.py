"""BioContext registry integration."""

import re
from typing import Dict, List, Optional

from .manager import RegistryManager


class BioContextRegistry:
    """Handles BioContext registry operations."""

    def __init__(self, registry_manager: RegistryManager, url: str = "https://biocontext.ai/registry.json"):
        self.registry_manager = registry_manager
        self.url = url

    def search(self, query: str, limit: int = 10, sort: str = "relevance") -> List[Dict]:
        """Search BioContext registry for MCP servers using rank-based aggregation."""
        registry_data = self.registry_manager.fetch_registry(self.url)

        results = []
        query_lower = query.lower()

        # Compute raw scores for all aspects
        for server in registry_data:
            # Search in name, description, and keywords
            if (
                query_lower in server.get("name", "").lower()
                or query_lower in server.get("description", "").lower()
                or any(query_lower in keyword.lower() for keyword in server.get("keywords", []))
            ):
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

                # Ensure identifier is present for ranking
                server_with_stars["identifier"] = server_with_stars.get(
                    "identifier", server_with_stars.get("name", "unknown")
                )

                # Calculate raw scores
                server_with_stars["_relevance_score"] = self._calculate_relevance_score(server_with_stars, query_lower)
                server_with_stars["_impact_score"] = (
                    server_with_stars.get("stars", 0) if isinstance(server_with_stars.get("stars"), int) else 0
                )
                server_with_stars["_quality_score"] = self._calculate_quality_score(server_with_stars)

                results.append(server_with_stars)

        # Assign ranks for each aspect (1 = best)
        def rank_servers(servers, key, reverse=True):
            # reverse=True: higher score = better rank
            sorted_servers = sorted(servers, key=lambda s: s[key], reverse=reverse)
            ranks = {}
            last_score = None
            last_rank = 0
            for idx, server in enumerate(sorted_servers):
                score = server[key]
                if score != last_score:
                    last_rank = idx + 1
                    last_score = score
                ranks[server["identifier"]] = last_rank
            return ranks

        relevance_ranks = rank_servers(results, "_relevance_score", reverse=True)
        impact_ranks = rank_servers(results, "_impact_score", reverse=True)
        quality_ranks = rank_servers(results, "_quality_score", reverse=True)

        # Average the ranks (equal weights)
        for server in results:
            server["_avg_rank"] = (
                relevance_ranks[server["identifier"]]
                + impact_ranks[server["identifier"]]
                + quality_ranks[server["identifier"]]
            ) / 3.0

        # Sort by average rank (ascending)
        results.sort(key=lambda x: (x["_avg_rank"], x.get("name", "").lower()))

        # If sort == "impact", sort by impact only
        if sort == "impact":
            results.sort(
                key=lambda x: (
                    -int(x.get("stars", 0)) if isinstance(x.get("stars"), int) else 0,
                    x.get("name", "").lower(),
                )
            )
        # If sort == "name", sort by name only
        elif sort == "name":
            results.sort(key=lambda x: x.get("name", "").lower())
        # If sort == "relevance", use the rank-based order (already sorted)

        return results[:limit]

    def _calculate_relevance_score(self, server: Dict, query: str) -> float:
        """Calculate relevance score for a server based on query."""
        score = 0.0

        # Exact name match (reduced weight)
        if query in server.get("name", "").lower():
            score += 5.0

        # Partial name match
        elif any(word in server.get("name", "").lower() for word in query.split()):
            score += 4.0

        # Exact description match
        if query in server.get("description", "").lower():
            score += 2.5

        # Partial description match
        elif any(word in server.get("description", "").lower() for word in query.split()):
            score += 1.5

        # Keyword matches
        keywords = server.get("keywords", [])
        exact_keyword_matches = sum(1 for keyword in keywords if query in keyword.lower())
        partial_keyword_matches = sum(
            1 for keyword in keywords if any(word in keyword.lower() for word in query.split())
        )

        score += exact_keyword_matches * 2.0
        score += partial_keyword_matches * 1.0

        return score

    def _calculate_quality_score(self, server: Dict) -> float:
        """Calculate quality score for an MCP server."""
        score = 0.0

        # Quality indicators for MCP servers
        if server.get("description") and len(server.get("description", "")) > 50:
            score += 0.3  # Good description
        if server.get("keywords") and len(server.get("keywords", [])) > 2:
            score += 0.2  # Good keyword coverage
        if server.get("codeRepository"):
            score += 0.3  # Has code repository
        stars = server.get("stars", 0)
        if isinstance(stars, int) and stars > 10:
            score += 0.2  # Popular server

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
            match = re.search(r"github\.com/([^/]+/[^/]+)", repo_url)
            if not match:
                return None

            repo_path = match.group(1)
            api_url = f"https://api.github.com/repos/{repo_path}"

            # Prepare headers for GitHub API
            headers = {"User-Agent": "biotope/1.0", "Accept": "application/vnd.github.v3+json"}

            # Add GitHub token if available (for higher rate limits)
            github_token = self._get_github_token()
            if github_token:
                headers["Authorization"] = f"token {github_token}"

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
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            return token

        # Check for GitHub token in biotope config
        try:
            from biotope.utils import find_biotope_root
            from biotope.validation import load_biotope_config

            biotope_root = find_biotope_root()
            if biotope_root:
                config = load_biotope_config(biotope_root)
                return config.get("github_token")
        except Exception:
            pass

        return None
