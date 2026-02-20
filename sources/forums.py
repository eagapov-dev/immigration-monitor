"""
Forum source - fetches posts from immigration forums via RSS feeds.
Currently supports VisaJourney.com.
No API credentials needed!
"""
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List

import feedparser
import requests

from sources.base import BaseSource, MonitorItem
from sources.reddit import detect_location

logger = logging.getLogger(__name__)


class ForumSource(BaseSource):
    def __init__(self, config: dict):
        self.forums = config.get("forums", [])
        self.posts_limit = config.get("posts_limit", 25)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; ImmigrationMonitor/1.0)',
        })

    async def fetch(self, lookback_hours: int) -> List[MonitorItem]:
        """Fetch new posts from all configured forum RSS feeds."""
        all_items = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        for forum_config in self.forums:
            name = forum_config.get("name", forum_config.get("url", "?"))
            try:
                items = self._fetch_forum_rss(forum_config, cutoff)
                all_items.extend(items)
                logger.info(f"{name}: fetched {len(items)} items via RSS")
            except Exception as e:
                logger.error(f"Error fetching {name} RSS: {e}")

        logger.info(f"Total forum items fetched: {len(all_items)}")
        return all_items

    def _fetch_forum_rss(self, forum_config: dict, cutoff: datetime) -> List[MonitorItem]:
        """Fetch posts from a single forum RSS feed."""
        items = []
        rss_url = forum_config["url"]
        forum_name = forum_config.get("name", rss_url)
        language = forum_config.get("language", "en")

        try:
            response = self.session.get(rss_url, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(f"RSS parsing warning for {forum_name}: {feed.bozo_exception}")

            for entry in feed.entries[:self.posts_limit]:
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        created = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        created = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                    else:
                        created = datetime.now(timezone.utc)

                    if created < cutoff:
                        continue

                    # Use guid if available, otherwise hash the link
                    guid = getattr(entry, 'id', '') or getattr(entry, 'guid', '') or entry.link
                    post_id = re.sub(r'[^\w]', '_', guid)

                    author = "unknown"
                    if hasattr(entry, 'author') and entry.author:
                        author = entry.author

                    # Combine title + cleaned description
                    title = getattr(entry, 'title', '')
                    text_content = title
                    summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                    if summary:
                        clean_summary = re.sub(r'<[^>]+>', '', summary)
                        clean_summary = re.sub(r'\s+', ' ', clean_summary).strip()
                        if clean_summary and clean_summary != title:
                            text_content = f"{title}\n\n{clean_summary}"

                    location = detect_location(text_content)

                    items.append(MonitorItem(
                        id=f"forum_{post_id}",
                        source="forum_post",
                        channel=forum_name,
                        title=title,
                        text=text_content,
                        url=entry.link,
                        author=author,
                        created_at=created,
                        language=language,
                        extra={
                            "forum": forum_name,
                            "location": location,
                        },
                    ))

                except Exception as e:
                    logger.warning(f"Error parsing forum RSS entry: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"Failed to fetch RSS feed for {forum_name}: {e}")

        return items
