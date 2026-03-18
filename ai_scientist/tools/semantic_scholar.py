import os
import re
import time
import warnings
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Union

import requests

from ai_scientist.tools.base_tool import BaseTool

# arXiv API: free, no key required. Use 3s delay between calls to be polite.
ARXIV_API_BASE = "https://export.arxiv.org/api/query"
ARXIV_REQUEST_DELAY_SEC = 3.0


def _arxiv_search_papers(query: str, max_results: int = 10) -> Optional[List[Dict]]:
    """Search arXiv API (free, no API key). Returns same shape as S2 for format_papers."""
    if not query or not query.strip():
        return None
    # Build query: search in title and abstract
    search_query = f"all:{query.strip().replace(' ', '+')}"
    params = {
        "search_query": search_query,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    try:
        rsp = requests.get(ARXIV_API_BASE, params=params, timeout=30)
        rsp.raise_for_status()
    except requests.RequestException as e:
        print(f"arXiv API request failed: {e}")
        return None
    # Parse Atom XML
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(rsp.content)
    papers = []
    for entry in root.findall("atom:entry", ns):
        if entry.find("atom:title", ns) is None:
            continue
        title = entry.find("atom:title", ns)
        title_text = (title.text or "").strip().replace("\n", " ")
        summary = entry.find("atom:summary", ns)
        abstract = (summary.text or "").strip().replace("\n", " ") if summary is not None else "No abstract available."
        published = entry.find("atom:published", ns)
        year = "N/A"
        if published is not None and published.text:
            m = re.search(r"(\d{4})", published.text)
            if m:
                year = m.group(1)
        authors_elems = entry.findall("atom:author", ns)
        authors = [{"name": (a.find("atom:name", ns).text or "Unknown").strip()} for a in authors_elems]
        papers.append({
            "title": title_text,
            "authors": authors,
            "venue": "arXiv",
            "year": year,
            "abstract": abstract,
            "citationCount": None,
        })
    time.sleep(ARXIV_REQUEST_DELAY_SEC)
    return papers if papers else None


class SemanticScholarSearchTool(BaseTool):
    def __init__(
        self,
        name: str = "SearchSemanticScholar",
        description: str = (
            "Search for relevant literature using Semantic Scholar. "
            "Provide a search query to find relevant papers."
        ),
        max_results: int = 10,
    ):
        parameters = [
            {
                "name": "query",
                "type": "str",
                "description": "The search query to find relevant papers.",
            }
        ]
        super().__init__(name, description, parameters)
        self.max_results = max_results
        self.S2_API_KEY = os.getenv("S2_API_KEY")
        if not self.S2_API_KEY:
            warnings.warn(
                "No Semantic Scholar API key found. Using arXiv as fallback for literature search. "
                "Set the S2_API_KEY environment variable to use Semantic Scholar instead."
            )

    def use_tool(self, query: str) -> Optional[str]:
        papers = self.search_for_papers(query)
        if papers:
            return self.format_papers(papers)
        else:
            return "No papers found."

    def search_for_papers(self, query: str) -> Optional[List[Dict]]:
        if not query:
            return None
        # When no API key, skip S2 to avoid 429 rate limits; use arXiv directly.
        if not self.S2_API_KEY:
            print("Using arXiv (no S2_API_KEY).")
            return _arxiv_search_papers(query, self.max_results)
        headers = {"X-API-KEY": self.S2_API_KEY}
        try:
            rsp = requests.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                headers=headers,
                params={
                    "query": query,
                    "limit": self.max_results,
                    "fields": "title,authors,venue,year,abstract,citationCount",
                },
                timeout=30,
            )
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as e:
            print(f"Semantic Scholar request failed: {e}. Falling back to arXiv.")
            return _arxiv_search_papers(query, self.max_results)
        print(f"Response Status Code: {rsp.status_code}")
        print(f"Response Content: {rsp.text[:500]}")
        if rsp.status_code == 429:
            print("Semantic Scholar rate limit (429). Falling back to arXiv.")
            return _arxiv_search_papers(query, self.max_results)
        rsp.raise_for_status()
        results = rsp.json()
        total = results.get("total", 0)
        if total == 0:
            return None
        papers = results.get("data", [])
        papers.sort(key=lambda x: x.get("citationCount", 0) or 0, reverse=True)
        return papers

    def format_papers(self, papers: List[Dict]) -> str:
        paper_strings = []
        for i, paper in enumerate(papers):
            authors = ", ".join(
                [author.get("name", "Unknown") for author in paper.get("authors", [])]
            )
            paper_strings.append(
                f"""{i + 1}: {paper.get("title", "Unknown Title")}. {authors}. {paper.get("venue", "Unknown Venue")}, {paper.get("year", "Unknown Year")}.
Number of citations: {paper.get("citationCount") if paper.get("citationCount") is not None else "N/A"}
Abstract: {paper.get("abstract", "No abstract available.")}"""
            )
        return "\n\n".join(paper_strings)


def search_for_papers(query, result_limit=10) -> Union[None, List[Dict]]:
    """Search literature. Uses Semantic Scholar when S2_API_KEY is set; on 429 or no key, uses arXiv."""
    S2_API_KEY = os.getenv("S2_API_KEY")
    if not query:
        return None
    if not S2_API_KEY:
        warnings.warn(
            "No Semantic Scholar API key found. Using arXiv for literature search."
        )
        return _arxiv_search_papers(query, result_limit)
    headers = {"X-API-KEY": S2_API_KEY}
    try:
        rsp = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            headers=headers,
            params={
                "query": query,
                "limit": result_limit,
                "fields": "title,authors,venue,year,abstract,citationStyles,citationCount",
            },
            timeout=30,
        )
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
        return _arxiv_search_papers(query, result_limit)
    print(f"Response Status Code: {rsp.status_code}")
    print(f"Response Content: {rsp.text[:500]}")
    if rsp.status_code == 429:
        print("Semantic Scholar rate limit (429). Using arXiv.")
        return _arxiv_search_papers(query, result_limit)
    rsp.raise_for_status()
    results = rsp.json()
    total = results.get("total", 0)
    time.sleep(1.0)
    if not total:
        return None
    return results["data"]
