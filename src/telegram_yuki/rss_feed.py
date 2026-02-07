"""Podcast RSS feed manager — episodes.json + feed.xml generation.

Maintains a JSON registry of episodes and regenerates an RSS feed (feed.xml)
compatible with Yandex.Music and VK Podcasts requirements.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from feedgen.feed import FeedGenerator

logger = logging.getLogger(__name__)

PODCASTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "yuki_podcasts")
EPISODES_FILE = os.path.join(PODCASTS_DIR, "episodes.json")
FEED_FILE = os.path.join(PODCASTS_DIR, "feed.xml")

# Podcast metadata
PODCAST_TITLE = "AI Corporation Podcast"
PODCAST_DESCRIPTION = (
    "AI Corporation — подкаст о технологиях, бизнесе и искусственном интеллекте. "
    "Генерируется AI-агентом Юки Пак."
)
PODCAST_AUTHOR = "AI Corporation"
PODCAST_EMAIL = "tim.zinin@gmail.com"
PODCAST_LANGUAGE = "ru"
PODCAST_CATEGORY = "Technology"


class PodcastRSSManager:
    """Manages podcast episode registry and RSS feed generation."""

    def __init__(self, base_url: Optional[str] = None):
        self._base_url = base_url or os.getenv("PODCAST_BASE_URL", "")
        os.makedirs(PODCASTS_DIR, exist_ok=True)

    def _load_episodes(self) -> list[dict]:
        """Load episodes from JSON registry."""
        if not os.path.exists(EPISODES_FILE):
            return []
        try:
            with open(EPISODES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load episodes.json: {e}")
            return []

    def _save_episodes(self, episodes: list[dict]) -> None:
        """Save episodes to JSON registry."""
        with open(EPISODES_FILE, "w", encoding="utf-8") as f:
            json.dump(episodes, f, ensure_ascii=False, indent=2)

    def add_episode(
        self,
        title: str,
        description: str,
        audio_filename: str,
        duration_sec: int,
        episode_number: Optional[int] = None,
    ) -> dict:
        """Add a new episode and regenerate feed.

        Returns the episode dict.
        """
        episodes = self._load_episodes()

        if episode_number is None:
            episode_number = len(episodes) + 1

        episode = {
            "episode_number": episode_number,
            "title": title,
            "description": description,
            "audio_filename": audio_filename,
            "duration_sec": duration_sec,
            "published": datetime.now(timezone.utc).isoformat(),
        }

        episodes.append(episode)
        self._save_episodes(episodes)

        self._regenerate_feed(episodes)

        logger.info(f"Episode #{episode_number} added: {title}")
        return episode

    def _regenerate_feed(self, episodes: Optional[list[dict]] = None) -> str:
        """Rebuild feed.xml from episodes registry.

        Returns path to feed.xml.
        """
        if episodes is None:
            episodes = self._load_episodes()

        fg = FeedGenerator()
        fg.load_extension("podcast")

        # Channel metadata
        fg.title(PODCAST_TITLE)
        fg.description(PODCAST_DESCRIPTION)
        fg.author({"name": PODCAST_AUTHOR, "email": PODCAST_EMAIL})
        fg.language(PODCAST_LANGUAGE)
        fg.generator("AI Corporation Podcast Generator")

        if self._base_url:
            fg.link(href=f"{self._base_url}/feed.xml", rel="self")
            fg.link(href=self._base_url, rel="alternate")

        # iTunes/Podcast extensions (required by Yandex.Music and VK)
        fg.podcast.itunes_author(PODCAST_AUTHOR)
        fg.podcast.itunes_summary(PODCAST_DESCRIPTION)
        fg.podcast.itunes_category(PODCAST_CATEGORY)
        fg.podcast.itunes_explicit("no")
        fg.podcast.itunes_owner(name=PODCAST_AUTHOR, email=PODCAST_EMAIL)

        # Episodes (newest first)
        for ep in sorted(episodes, key=lambda e: e["episode_number"], reverse=True):
            fe = fg.add_entry()
            fe.id(f"ai-corp-ep-{ep['episode_number']}")
            fe.title(ep["title"])
            fe.description(ep["description"])

            pub_date = datetime.fromisoformat(ep["published"])
            fe.published(pub_date)

            # Audio enclosure
            if self._base_url:
                audio_url = f"{self._base_url}/audio/{ep['audio_filename']}"
                fe.enclosure(audio_url, 0, "audio/mpeg")

            # iTunes episode metadata
            fe.podcast.itunes_duration(ep["duration_sec"])
            fe.podcast.itunes_episode(ep["episode_number"])
            fe.podcast.itunes_episode_type("full")

        # Write feed
        fg.rss_file(FEED_FILE, pretty=True)
        logger.info(f"RSS feed regenerated: {FEED_FILE} ({len(episodes)} episodes)")

        return FEED_FILE

    def get_episode_count(self) -> int:
        """Return total number of episodes."""
        return len(self._load_episodes())

    def get_feed_path(self) -> str:
        """Return absolute path to feed.xml."""
        return FEED_FILE

    def get_episodes(self) -> list[dict]:
        """Return all episodes."""
        return self._load_episodes()
