from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Optional, List, Tuple

import requests
from bs4 import BeautifulSoup

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> None:
        return None

load_dotenv()


@dataclass(slots=True)
class ExtractedDescription:
    url: str
    description: Optional[str]
    method: Optional[str]
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


class DescriptionExtractor:
    """
    Fetch HTML via ScraperAPI and extract product description/details/specs.
    """

    def __init__(
        self,
        *,
        scraperapi_key: Optional[str] = None,
        timeout_s: int = 30,
        device_type: str = "desktop",
        max_cost: str = "5",  # Increased from 1 to 5 (most requests cost 1-5 credits)
        min_chars: int = 80,
        max_chars: int = 1200,
        debug: bool = False,
    ) -> None:
        self.api_key = scraperapi_key or os.getenv("SCRAPER_API_KEY")
        if not self.api_key:
            raise ValueError("Missing SCRAPER_API_KEY (set env var or pass scraperapi_key=...)")

        self.timeout_s = timeout_s
        self.device_type = device_type
        self.max_cost = max_cost
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.debug = debug

    def extract(self, url: str) -> ExtractedDescription:
        url = (url or "").strip()
        if not url:
            return ExtractedDescription(url="", description=None, method=None)

        html = self._fetch_html_scraperapi(url)
        if not html:
            return ExtractedDescription(url=url, description=None, method="fetch_fail")

        if _looks_like_bot_challenge(html):
            if self.debug:
                print(f"[SCRAPER] ⚠️ Detected bot challenge page")
            return ExtractedDescription(url=url, description=None, method="blocked")

        soup = BeautifulSoup(html, "html.parser")

        # Extract meta tags first (always extract these)
        meta_title = _meta_title(soup)
        meta_description = _meta_description(soup)

        # 1) JavaScript embedded data (Shopify/themeConfig patterns)
        desc = _javascript_product_data(html)
        if _is_good(desc, self.min_chars):
            if self.debug:
                print(f"[EXTRACT] ✓ Found via JavaScript data")
            return ExtractedDescription(url=url, description=_clip(_clean(desc), self.max_chars), method="javascript", meta_title=meta_title, meta_description=meta_description)

        # 2) JSON-LD Product.description
        desc = _jsonld_product_description(soup)
        if _is_good(desc, self.min_chars):
            if self.debug:
                print(f"[EXTRACT] ✓ Found via JSON-LD")
            return ExtractedDescription(url=url, description=_clip(_clean(desc), self.max_chars), method="jsonld", meta_title=meta_title, meta_description=meta_description)

        # 3) Meta description (only as fallback, usually too short)
        desc = meta_description
        if _is_good(desc, 40):
            if self.debug:
                print(f"[EXTRACT] ✓ Found via meta tag")
            return ExtractedDescription(url=url, description=_clip(_clean(desc), self.max_chars), method="meta", meta_title=meta_title, meta_description=meta_description)

        # 4) Fuzzy section: Description / Product details / Specs
        desc = _section_by_heading(soup, min_chars=self.min_chars)
        if _is_good(desc, self.min_chars):
            if self.debug:
                print(f"[EXTRACT] ✓ Found via section heading")
            return ExtractedDescription(url=url, description=_clip(_clean(desc), self.max_chars), method="section", meta_title=meta_title, meta_description=meta_description)

        # 5) Fallback best block
        desc = _best_text_block(soup, min_chars=self.min_chars)
        if _is_good(desc, self.min_chars):
            if self.debug:
                print(f"[EXTRACT] ✓ Found via best text block")
            return ExtractedDescription(url=url, description=_clip(_clean(desc), self.max_chars), method="fallback", meta_title=meta_title, meta_description=meta_description)

        if self.debug:
            print(f"[EXTRACT] ❌ No description found with any method")
        return ExtractedDescription(url=url, description=None, method=None, meta_title=meta_title, meta_description=meta_description)

    def _fetch_html_scraperapi(self, url: str) -> Optional[str]:
        """
        Fetch HTML via ScraperAPI with proper response handling.
        
        THREE APPROACHES - Try in order:
        1. Simple request (no autoparse, no json wrapper)
        2. JSON output format (wrapped response)
        3. Autoparse enabled
        """
        
        # APPROACH 1: Simple request (RECOMMENDED)
        payload = {
            "api_key": self.api_key,
            "url": url,
            "device_type": self.device_type,
            "render": "false",  # Set to "true" if you need JavaScript rendering
        }
        
        # Only add max_cost if it's set and not "unlimited"
        if self.max_cost and self.max_cost.lower() not in ("0", "unlimited", "none", ""):
            payload["max_cost"] = self.max_cost

        try:
            if self.debug:
                print(f"\n[SCRAPER] Fetching: {url}")
                print(f"[SCRAPER] Params: device={self.device_type}, max_cost={payload.get('max_cost', 'unlimited')}")
            
            r = requests.get(
                "https://api.scraperapi.com/",
                params=payload,
                timeout=self.timeout_s
            )
            
            if self.debug:
                print(f"[SCRAPER] Status: {r.status_code}")
                print(f"[SCRAPER] Content-Type: {r.headers.get('Content-Type', 'unknown')}")
                print(f"[SCRAPER] Content length: {len(r.text)}")
                print(f"[SCRAPER] Response headers:")
                for key in ['x-scraper-cost', 'x-credit-limit-remaining', 'x-credits-used']:
                    if key in r.headers:
                        print(f"  {key}: {r.headers[key]}")
                print(f"[SCRAPER] First 200 chars: {r.text[:200]}")
            
            if r.status_code != 200:
                if self.debug:
                    print(f"[SCRAPER] ❌ Failed with status {r.status_code}")
                    print(f"[SCRAPER] Response: {r.text[:500]}")
                return None
            
            # Check if response looks like HTML
            text = r.text.strip()
            if not text:
                if self.debug:
                    print("[SCRAPER] ❌ Empty response")
                return None
            
            # If it starts with {, it might be JSON-wrapped
            if text.startswith('{'):
                try:
                    data = json.loads(text)
                    # Try common JSON response fields
                    html = data.get('html') or data.get('body') or data.get('content')
                    if html:
                        if self.debug:
                            print(f"[SCRAPER] ✓ Extracted HTML from JSON response")
                        return html
                except json.JSONDecodeError:
                    pass
            
            # Otherwise treat as raw HTML
            if self.debug:
                print(f"[SCRAPER] ✓ Got raw HTML response")
            return text
            
        except requests.Timeout:
            if self.debug:
                print(f"[SCRAPER] ❌ Timeout after {self.timeout_s}s")
            return None
        except requests.RequestException as e:
            if self.debug:
                print(f"[SCRAPER] ❌ Request error: {type(e).__name__}: {e}")
            return None
        except Exception as e:
            if self.debug:
                print(f"[SCRAPER] ❌ Unexpected error: {type(e).__name__}: {e}")
            return None


# -------------------------
# Extraction helpers
# -------------------------

_TARGET_HEADINGS = (
    "product description",
    "description",
    "overview",
    "product details",
    "details",
    "specifications",
    "specs",
    "features",
    "key features",
)

_HEADING_TAGS = ("h1", "h2", "h3", "h4", "summary", "button", "span", "div")


def _looks_like_bot_challenge(html: str) -> bool:
    """
    Check if HTML appears to be a bot/CAPTCHA challenge page.
    Be conservative - only flag obvious challenge pages.
    """
    h = (html or "").lower()
    
    # Check for actual challenge indicators
    indicators = {
        "captcha": "captcha" in h and "solve" in h,
        "access_denied": "access denied" in h and len(h) < 5000,
        "cloudflare_challenge": "checking your browser" in h or "just a moment" in h,
        "js_required": "please enable javascript" in h and "to continue" in h,
    }
    
    # Only return True if we find clear evidence
    return any(indicators.values())


def _clip(s: str, max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s


def _is_good(s: Optional[str], min_chars: int) -> bool:
    if not s:
        return False
    return len(_clean(s)) >= min_chars


def _meta_title(soup: BeautifulSoup) -> Optional[str]:
    """Extract meta title from various sources."""
    # 1. Try <title> tag first
    title_tag = soup.find("title")
    if title_tag:
        txt = title_tag.get_text().strip()
        if txt:
            return txt

    # 2. Try Open Graph title
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        txt = og_title["content"].strip()
        if txt:
            return txt

    # 3. Try Twitter title
    twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
    if twitter_title and twitter_title.get("content"):
        txt = twitter_title["content"].strip()
        if txt:
            return txt

    return None


def _meta_description(soup: BeautifulSoup) -> Optional[str]:
    """Extract meta description from various sources."""
    for attr in ("name", "property"):
        for key in ("description", "og:description", "twitter:description"):
            tag = soup.find("meta", attrs={attr: key})
            if tag and tag.get("content"):
                txt = tag["content"].strip()
                if txt:
                    return txt
    return None


def _javascript_product_data(html: str) -> Optional[str]:
    """
    Extract product description from JavaScript-embedded data.
    Common patterns:
    - window.themeConfig('product', {...})  (Shopify)
    - var product = {...}
    - window.productData = {...}
    """
    patterns = [
        # Shopify themeConfig pattern
        r"window\.themeConfig\(['\"]product['\"],\s*({.+?})\);",
        # Generic product object
        r"var\s+product\s*=\s*({.+?});",
        r"window\.product\s*=\s*({.+?});",
        r"window\.productData\s*=\s*({.+?});",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            continue
        
        try:
            json_str = match.group(1)
            # Handle potential issues with the JSON
            # Sometimes there are trailing commas or other issues
            data = json.loads(json_str)
            
            # Try multiple possible keys for description
            for key in ["description", "content", "body_html", "details"]:
                desc = data.get(key)
                if isinstance(desc, str) and desc.strip():
                    # Remove HTML tags from description
                    from html import unescape
                    desc = re.sub(r'<[^>]+>', ' ', desc)
                    desc = unescape(desc)
                    desc = re.sub(r'\s+', ' ', desc).strip()
                    if len(desc) >= 80:
                        return desc
        except (json.JSONDecodeError, KeyError, AttributeError):
            continue
    
    return None


def _jsonld_product_description(soup: BeautifulSoup) -> Optional[str]:
    for sc in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (sc.string or sc.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        for obj in _iter_jsonld(data):
            if not isinstance(obj, dict):
                continue
            t = obj.get("@type")
            types = set()
            if isinstance(t, list):
                types = {str(x).lower() for x in t}
            elif t:
                types = {str(t).lower()}

            if "product" in types:
                desc = obj.get("description")
                if isinstance(desc, str) and desc.strip():
                    return desc.strip()
    return None


def _iter_jsonld(data):
    if isinstance(data, dict):
        yield data
        g = data.get("@graph")
        if isinstance(g, list):
            for x in g:
                yield from _iter_jsonld(x)
    elif isinstance(data, list):
        for x in data:
            yield from _iter_jsonld(x)


def _section_by_heading(soup: BeautifulSoup, *, min_chars: int) -> Optional[str]:
    """Find content under headings that resemble Description/Details/Specs."""
    best: Tuple[float, str] = (0.0, "")

    for tag_name in _HEADING_TAGS:
        for el in soup.find_all(tag_name):
            label = _norm(el.get_text(" ", strip=True))
            if not label:
                continue

            score = _heading_score(label)
            if score < 0.70:
                continue

            block = _extract_near(el)
            block = _clean(block)

            if len(block) >= min_chars:
                score2 = score + min(0.15, len(block) / 4000.0)
                if score2 > best[0]:
                    best = (score2, block)

    return best[1] or None


def _heading_score(text: str) -> float:
    t = text
    best = 0.0
    for target in _TARGET_HEADINGS:
        best = max(best, _token_similarity(t, target))
    return best


def _token_similarity(a: str, b: str) -> float:
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    if not a_tokens or not b_tokens:
        return 0.0
    inter = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return inter / union


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _extract_near(heading_el) -> str:
    sib = heading_el.find_next_sibling()
    for _ in range(6):
        if sib is None:
            break
        txt = _extract_rich_text(sib)
        if len(txt) >= 40:
            return txt
        sib = sib.find_next_sibling()

    parent = heading_el.parent
    if parent:
        txt = _extract_rich_text(parent)
        if len(txt) >= 60:
            return txt

    nxt = heading_el.find_next()
    if nxt:
        return _extract_rich_text(nxt)

    return ""


def _extract_rich_text(el) -> str:
    parts: List[str] = []

    for table in el.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            th = tr.find("th")
            td = tr.find("td")
            if not td:
                continue
            k = th.get_text(" ", strip=True) if th else ""
            v = td.get_text(" ", strip=True)
            if v:
                rows.append(f"{k}: {v}".strip(": ").strip())
        if rows:
            parts.append(" | ".join(rows))

    for ul in el.find_all(["ul", "ol"]):
        items = [li.get_text(" ", strip=True) for li in ul.find_all("li")]
        items = [x for x in items if x]
        if items:
            parts.append(" • " + " • ".join(items))

    txt = el.get_text(" ", strip=True)
    if txt:
        parts.append(txt)

    return " ".join(parts).strip()


def _best_text_block(soup: BeautifulSoup, *, min_chars: int) -> Optional[str]:
    best = ""
    for tag in soup.find_all(["article", "main", "section", "div"]):
        cls = " ".join(tag.get("class", []) or []).lower()
        if any(x in cls for x in ("nav", "footer", "header", "breadcrumb", "menu")):
            continue
        txt = _clean(tag.get_text(" ", strip=True))
        if len(txt) >= min_chars and len(txt) > len(best):
            best = txt
    return best or None


__all__ = ["DescriptionExtractor", "ExtractedDescription"]