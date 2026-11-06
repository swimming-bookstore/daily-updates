#!/usr/bin/env python3
"""Build the coding-agent, LLM, and daily Japanese YouTube reels."""

import sys
from datetime import datetime, timedelta, timezone

from reel.agents import draw as draw_agents
from reel.core import render
from reel.data import load_agents, load_models
from reel.japanese import draw as draw_japanese
from reel.japanese import clip_length as japanese_length
from reel.japanese import load_japanese
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


def want(slug):
    only = sys.argv[1:]
    if not only:
        return True
    return any(arg == slug or arg in slug for arg in only)


def main():
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    if want("claude_code_version_update"):
        agents = load_agents(today, yesterday)
        dump(agents)
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
    if want("llm_models_update"):
        models = load_models(today, yesterday)
        dump(models)
        print(
            "wrote",
            render(models, today, "llm_models_update", "LLM Models Update", draw_models),
            flush=True,
        )
    if want("japanese_youtube"):
        videos, video_day = load_japanese()
        print(f"japanese youtube {video_day}", flush=True)
        dump(videos)
        print(
            "wrote",
            render(
                videos,
                video_day,
                "japanese_youtube",
                "Japanese Video Update",
                draw_japanese,
                duration=japanese_length(videos),
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
