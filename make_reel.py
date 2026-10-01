#!/usr/bin/env python3
"""Build the coding-agent glass reel and the LLM HUD reel."""

from datetime import datetime, timedelta, timezone

from reel.agents import draw as draw_agents
from reel.core import render
from reel.data import load_agents, load_models
from reel.models import draw as draw_models


def dump(items):
    for item in items:
        if item["fresh"]:
            mark = "UPDATED"
        elif item["yesterday"]:
            mark = "UPDATED YESTERDAY"
        else:
            mark = "quiet"
        print(f"{item['name']} {item['version']} {item['published']} {mark}", flush=True)


def main():
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    agents = load_agents(today, yesterday)
    models = load_models(today, yesterday)
    dump(agents)
    dump(models)
    print(
        "wrote",
        render(
            agents,
            today,
            "claude_code_version_update",
            "Claude Code Version Update",
            draw_agents,
        ),
        flush=True,
    )
    print(
        "wrote",
        render(models, today, "llm_models_update", "LLM Models Update", draw_models),
        flush=True,
    )


if __name__ == "__main__":
    main()
