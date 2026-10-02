"""Version sources for coding agents and LLM models."""

import re

from .core import fetch_json


AGENT_SOURCES = [
    {
        "name": "Claude Code",
        "github": "https://api.github.com/repos/anthropics/claude-code/releases/latest",
    },
    {"name": "Codex", "npm": "https://registry.npmjs.org/@openai/codex"},
    {"name": "Pi", "npm": "https://registry.npmjs.org/@earendil-works/pi-coding-agent"},
    {"name": "OpenClaw", "npm": "https://registry.npmjs.org/openclaw"},
    {
        "name": "Hermes Agent",
        "github": "https://api.github.com/repos/NousResearch/hermes-agent/releases/latest",
    },
    {"name": "Cline", "npm": "https://registry.npmjs.org/cline"},
]

MODEL_SOURCES = [
    {"name": "Claude Fable", "provider": "anthropic", "family": "claude-fable", "icon": "claude"},
    {"name": "Claude Opus", "provider": "anthropic", "family": "claude-opus", "icon": "claude"},
    {"name": "Claude Sonnet", "provider": "anthropic", "family": "claude-sonnet", "icon": "claude"},
    {"name": "GPT Astra", "provider": "openai", "family": "gpt-astra", "icon": "openai"},
    {"name": "GPT Sol", "provider": "openai", "family": "gpt-sol", "icon": "openai"},
    {"name": "Gemini Flash", "provider": "google", "family": "gemini-flash", "icon": "gemini"},
    {"name": "Grok", "provider": "xai", "family": "grok", "icon": "grok"},
]


def latest_version(data):
    skip = ("darwin", "linux", "win32", "arm64", "x64")
    times = data.get("time", {})
    versions = [
        v
        for v in times
        if v not in ("modified", "created") and not any(part in v for part in skip)
    ]
    if not versions:
        return data["dist-tags"]["latest"]
    return max(versions, key=lambda v: times[v])


def load_npm(src):
    data = fetch_json(src["npm"])
    version = latest_version(data)
    published = data["time"][version]
    return version, published


def load_github(src):
    import urllib.request

    try:
        data = fetch_json(src["github"])
        version = (data.get("tag_name") or "").lstrip("v")
        name = data.get("name") or ""
        if " v" in name:
            version = name.split(" v", 1)[1].split(" ", 1)[0].split("(", 1)[0]
        published = data.get("published_at") or ""
        return version, published
    except Exception:
        html_url = src["github"].replace("https://api.github.com/repos/", "https://github.com/")
        req = urllib.request.Request(html_url, headers={"User-Agent": "updates-reel"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", "ignore")
            final = resp.geturl()
        tag = final.rsplit("/", 1)[-1].lstrip("v")
        version = tag
        m = re.search(r"Hermes Agent v([0-9]+\.[0-9]+\.[0-9]+)", html)
        if m:
            version = m.group(1)
        published = ""
        m = re.search(r'datetime="([0-9T:\-Z]+)"', html)
        if m:
            published = m.group(1)
        return version, published


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
        version, published = load_github(src) if src.get("github") else load_npm(src)
        items.append(pack_item(src["name"], version, published, today, yesterday))
    return items


def latest_model(models, src):
    family = src.get("family")
    if family:
        matches = [m for m in models.values() if m.get("family") == family]
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
