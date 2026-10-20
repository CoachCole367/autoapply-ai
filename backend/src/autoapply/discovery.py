"""Public board feeds only; no arbitrary user-supplied network endpoints."""

import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx


def canonical_url(url):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError("Expected a public HTTPS job URL")
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_")]
    return urlunsplit(("https", p.hostname.lower(), p.path.rstrip("/"), urlencode(sorted(query)), ""))


def plain(value):
    return re.sub(r"<[^>]*>", " ", html.unescape(html.unescape(value or ""))).strip()


def endpoint(provider, slug):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", slug):
        raise ValueError("Invalid board slug")
    return {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
        "lever": f"https://api.lever.co/v0/postings/{slug}?mode=json",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
    }[provider]


def parse(provider, data):
    rows = data if provider == "lever" else data["jobs"]
    output = []
    for r in rows:
        if provider == "ashby" and not r.get("isListed", True):
            continue
        if provider == "greenhouse":
            title, location, url = r["title"], r.get("location", {}).get("name", ""), r["absolute_url"]
            description = plain(r.get("content", ""))
        elif provider == "lever":
            title, location = r["text"], r.get("categories", {}).get("location", "")
            url = r.get("applyUrl") or r["hostedUrl"]
            description = (
                r.get("descriptionPlain", "")
                + "\n"
                + "\n".join(f"{x.get('text', '')}: {plain(x.get('content', ''))}" for x in r.get("lists", []))
                + "\n"
                + plain(r.get("additionalPlain", ""))
            )
        else:
            title, location = r["title"], r.get("location", "")
            url = r.get("applyUrl") or r["jobUrl"]
            description = r.get("descriptionPlain") or plain(r.get("descriptionHtml", ""))
        output.append(
            dict(
                external_id=str(r["id"]),
                title=title,
                location=location,
                url=canonical_url(url),
                description=description,
            )
        )
    return output


def discover(provider, slug, client=None):
    def fetch(c):
        response = c.get(endpoint(provider, slug))
        response.raise_for_status()
        return parse(provider, response.json())

    if client is not None:
        return fetch(client)
    with httpx.Client(timeout=30, follow_redirects=False, headers={"User-Agent": "AutoApplyAI/0.1"}) as c:
        return fetch(c)
