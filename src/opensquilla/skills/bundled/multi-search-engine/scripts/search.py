"""Query multiple search engines and emit a normalized JSON result list."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (compatible; OpenSquilla-multi-search-engine/0.1)"
)
TIMEOUT_S = 8.0


@dataclass
class Result:
    engine: str
    title: str
    url: str
    snippet: str
    rank: int


@dataclass
class EngineError:
    engine: str
    reason: str


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.8"},
        follow_redirects=True,
        timeout=TIMEOUT_S,
    )


def _ddg_search(query: str, limit: int) -> list[Result]:
    with _client() as client:
        response = client.post("https://html.duckduckgo.com/html/", data={"q": query})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results: list[Result] = []
        for idx, item in enumerate(soup.select("div.result")[:limit], start=1):
            title_el = item.select_one("a.result__a")
            snippet_el = item.select_one("a.result__snippet")
            if title_el is None:
                continue
            results.append(
                Result(
                    engine="duckduckgo",
                    title=title_el.get_text(strip=True),
                    url=title_el.get("href", ""),
                    snippet=snippet_el.get_text(strip=True) if snippet_el is not None else "",
                    rank=idx,
                )
            )
        return results


def _brave_search(query: str, limit: int) -> list[Result]:
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY not set; skipping")
    with _client() as client:
        response = client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": limit},
            headers={"X-Subscription-Token": api_key},
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("web", {}).get("results", []) or []
        results: list[Result] = []
        for idx, item in enumerate(items[:limit], start=1):
            results.append(
                Result(
                    engine="brave",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    rank=idx,
                )
            )
        return results


def _tavily_search(query: str, limit: int) -> list[Result]:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not set; skipping")
    with _client() as client:
        response = client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": limit,
            },
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("results", []) or []
        results: list[Result] = []
        for idx, item in enumerate(items[:limit], start=1):
            results.append(
                Result(
                    engine="tavily",
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    rank=idx,
                )
            )
        return results


ENGINES: dict[str, Callable[[str, int], list[Result]]] = {
    "duckduckgo": _ddg_search,
    "brave": _brave_search,
    "tavily": _tavily_search,
}


def search_all(
    query: str,
    engines: list[str],
    limit: int,
    strict: bool,
) -> dict[str, object]:
    results: list[dict[str, object]] = []
    errors: list[EngineError] = []
    for name in engines:
        handler = ENGINES.get(name)
        if handler is None:
            errors.append(EngineError(name, "unknown engine"))
            if strict:
                break
            continue
        try:
            for r in handler(query, limit):
                results.append(r.__dict__)
        except Exception as exc:  # network, key missing, parser breaks — keep going
            errors.append(EngineError(name, str(exc)))
            if strict:
                break
    return {
        "query": query,
        "results": results,
        "errors": [e.__dict__ for e in errors],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-engine web search.")
    parser.add_argument("--query", required=True)
    parser.add_argument(
        "--engines",
        default="duckduckgo",
        help="Comma-separated engine list (duckduckgo,brave,tavily)",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--strict", action="store_true", help="Fail on first engine error")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="(default; kept for clarity)")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    payload = search_all(args.query, engines, args.limit, args.strict)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out is not None:
        args.out.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
