"""
Web 工具 - WebSearch, WebFetch
基于 DScode 的 WebSearchTool, WebFetchTool
"""

import json
import re
import requests
from html import unescape
from urllib.parse import quote_plus

from tools.base import Tool


class WebSearchTool(Tool):
    """网络搜索"""

    name = "web_search"
    description = """Search the web for information. Returns a list of search results 
    with titles, URLs, and snippets. Use this for accessing information beyond 
    your knowledge cutoff."""

    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query"
            },
            "allowed_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Only include results from these domains"
            },
            "blocked_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Exclude results from these domains"
            }
        },
        "required": ["query"]
    }

    def execute(self, query: str, allowed_domains: list = None,
                blocked_domains: list = None) -> str:
        try:
            # 使用 DuckDuckGo Instant Answer API (免费，无需 key)
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            }

            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()

            results = []

            # Abstract
            if data.get("AbstractText"):
                results.append(f"Summary: {data['AbstractText']}")
                if data.get("AbstractURL"):
                    results.append(f"Source: {data['AbstractURL']}")

            # Related Topics
            topics = data.get("RelatedTopics", [])
            for topic in topics[:10]:
                if isinstance(topic, dict):
                    text = topic.get("Text", "")
                    url_top = topic.get("FirstURL", "")
                    if text:
                        # 清理 HTML
                        clean_text = re.sub(r"<[^>]+>", "", text)
                        results.append(f"- {clean_text}")
                        if url_top:
                            results.append(f"  {url_top}")

            if not results:
                return f"No search results found for: {query}"

            return "\n".join(results[:30])

        except Exception as e:
            return f"Search error: {str(e)}"


class WebFetchTool(Tool):
    """获取网页内容"""

    name = "web_fetch"
    description = """Fetch and extract content from a URL. Returns the page content 
    as plain text. Use this to read documentation, articles, and web pages."""

    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch content from"
            },
            "prompt": {
                "type": "string",
                "description": "What information to extract from the page"
            }
        },
        "required": ["url"]
    }

    def execute(self, url: str, prompt: str = "") -> str:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)

            if not resp.ok:
                return f"Error: HTTP {resp.status_code} when fetching {url}"

            # 简单提取文本
            content_type = resp.headers.get("content-type", "")

            if "text/html" in content_type:
                text = self._extract_text(resp.text)
            else:
                text = resp.text

            # 限制返回长度
            max_length = 10000
            if len(text) > max_length:
                text = text[:max_length] + f"\n... (truncated, {len(text)} total chars)"

            return f"Content from {url}:\n\n{text}"

        except requests.Timeout:
            return f"Error: Timeout fetching {url}"
        except Exception as e:
            return f"Error fetching URL: {str(e)}"

    def _extract_text(self, html: str) -> str:
        """简单提取 HTML 文本"""
        # 移除 script 和 style
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

        # 移除 HTML 标签
        text = re.sub(r"<[^>]+>", " ", text)

        # 解码 HTML 实体
        text = unescape(text)

        # 清理空白
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)

        return text.strip()
