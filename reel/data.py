"""Version sources for coding agents and LLM models."""

import json
import re

from .core import fetch_json


AGENT_SOURCES = [
    {
        "name": "Claude Code",
        "releases": "https://github.com/anthropics/claude-code/releases",
    },
    {
        "name": "Codex",
        "releases": "https://github.com/openai/codex/releases",
        "stable": True,
    },
    {"name": "Pi", "releases": "https://github.com/earendil-works/pi/releases"},
    {
        "name": "OpenClaw",
        "releases": "https://github.com/openclaw/openclaw/releases",
        "app": True,
    },
    {
        "name": "Hermes Agent",
        "releases": "https://github.com/NousResearch/hermes-agent/releases",
        "semver": True,
    },
    {
        "name": "Cline",
        "marketplace": "https://marketplace.visualstudio.com/items?itemName=saoudrizwan.claude-dev",
    },
]

MODEL_SOURCES = [
    {"name": "Claude Fable", "provider": "anthropic", "family": "claude-fable", "icon": "claude"},
    {"name": "Claude Opus", "provider": "anthropic", "family": "claude-opus", "icon": "claude"},
    {"name": "GPT Astra", "provider": "openai", "family": "gpt-astra", "icon": "openai"},
    {"name": "GPT Sol", "provider": "openai", "family": "gpt-sol", "icon": "openai"},
    {"name": "Gemini Flash", "provider": "google", "family": "gemini-flash", "icon": "gemini"},
    {"name": "Grok", "provider": "xai", "family": "grok", "icon": "grok", "exclude": "imagine"},
]


def is_prerelease(version):
    return re.search(r"(?:alpha|beta|rc|preview|canary)", version, re.I) is not None


def fetch_html(url):
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "updates-reel"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "ignore")


def github_releases(repo):
    url = f"https://api.github.com/repos/{repo}/releases?per_page=100"
    req_headers = {
        "User-Agent": "updates-reel",
        "Accept": "application/vnd.github+json",
    }
    import urllib.request

    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def page_date(url):
    match = re.search(r'datetime="([0-9T:\-Z]+)"', fetch_html(url))
    return match.group(1) if match else ""


def release_entries(html):
    entries = []
    seen = set()
    for href, text in re.findall(r'href="([^"]+/releases/tag/[^"]+)"[^>]*>([^<]*)', html):
        label = re.sub(r"\s+", " ", text).strip()
        if not label or label.lower() == "read more" or href in seen:
            continue
        seen.add(href)
        entries.append({"label": label, "href": href})
    return entries


def pick_release(src, entries):
    if src.get("app"):
        apps = [
            entry
            for entry in entries
            if re.fullmatch(r"openclaw [0-9]+\.[0-9]+\.[0-9]+", entry["label"])
        ]
        if not apps:
            raise RuntimeError("no openclaw app release")
        return max(apps, key=lambda entry: [int(n) for n in entry["label"].split()[-1].split(".")])
    if src.get("semver"):
        for entry in entries:
            match = re.search(r"v(\d+\.\d+\.\d+)", entry["label"])
            if match and not is_prerelease(entry["label"]):
                return {"label": match.group(1), "href": entry["href"]}
    for entry in entries:
        label = entry["label"].lstrip("v")
        if src.get("stable") and is_prerelease(label):
            continue
        if re.search(r"\d", label):
            return {"label": label, "href": entry["href"]}
    raise RuntimeError(f"no release matched {src['name']}")


def repo_from_releases(url):
    match = re.search(r"github\.com/([^/]+/[^/]+)/releases", url)
    if not match:
        raise RuntimeError(f"not a github releases url: {url}")
    return match.group(1)


def api_entries(releases, repo):
    entries = []
    for rel in releases:
        if rel.get("draft"):
            continue
        label = (rel.get("name") or rel.get("tag_name") or "").strip()
        tag = rel.get("tag_name") or ""
        if not label or not tag:
            continue
        entries.append(
            {
                "label": label,
                "href": f"/{repo}/releases/tag/{tag}",
                "published": rel.get("published_at") or "",
                "prerelease": bool(rel.get("prerelease")),
            }
        )
    return entries


def load_releases(src):
    repo = repo_from_releases(src["releases"])
    try:
        entries = api_entries(github_releases(repo), repo)
    except Exception:
        entries = release_entries(fetch_html(src["releases"]))
    picked = pick_release(src, entries)
    version = picked["label"].split()[-1].lstrip("v")
    published = picked.get("published") or page_date("https://github.com" + picked["href"])
    return {"version": version, "published": published}


def load_marketplace(src):
    html = fetch_html(src["marketplace"])
    versions = re.findall(r'"version"\s*:\s*"(\d+\.\d+\.\d+)"', html)
    if not versions:
        raise RuntimeError(f"no marketplace version for {src['name']}")
    match = re.search(r'"lastUpdated"\s*:\s*"([^"]+)"', html)
    published = match.group(1) if match else ""
    try:
        from email.utils import parsedate_to_datetime

        published = parsedate_to_datetime(published).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        pass
    return {"version": versions[0], "published": published}


def pack_item(name, version, published, today, yesterday, icon=None):
    day = (published or "")[:10]
    item = {
        "name": name,
        "version": version,
        "published": published,
        "day": day,
        "fresh": day == today,
        "yesterday": day == yesterday,
    }
    if icon:
        item["icon"] = icon
    return item


def load_agents(today, yesterday):
    items = []
    for src in AGENT_SOURCES:
        found = load_marketplace(src) if src.get("marketplace") else load_releases(src)
        items.append(
            pack_item(src["name"], found["version"], found["published"], today, yesterday)
        )
    return items


def latest_model(models, src):
    family = src.get("family")
    if family:
        skip = src.get("exclude")
        matches = [
            m
            for m in models.values()
            if m.get("family") == family
            and not (skip and skip in (m.get("id") or "").lower())
            and not (skip and skip in (m.get("name") or "").lower())
        ]
        if not matches:
            raise RuntimeError(f"missing family {src['provider']}/{family}")
        return max(matches, key=lambda m: m.get("release_date") or "")
    model = models.get(src["id"])
    if not model:
        raise RuntimeError(f"missing model {src['provider']}/{src['id']}")
    return model


def load_models(today, yesterday):
    catalog = fetch_json("https://models.dev/api.json")
    items = []
    for src in MODEL_SOURCES:
        provider = catalog.get(src["provider"], {})
        model = latest_model(provider.get("models", {}), src)
        published = model.get("release_date") or model.get("last_updated") or ""
        name = model.get("name") or src["name"]
        items.append(pack_item(name, name, published, today, yesterday, icon=src["icon"]))
    items.sort(key=lambda item: item["published"] or "", reverse=True)
    return items
