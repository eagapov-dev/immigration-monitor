"""
Reddit source - fetches posts from configured subreddits using RSS feeds.
No API credentials needed!
"""
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List

import feedparser
import requests

from sources.base import BaseSource, MonitorItem

logger = logging.getLogger(__name__)

# Subreddit → location mapping
SUBREDDIT_LOCATIONS = {
    "chicago":          "Chicago, IL",
    "newyorkcity":      "New York, NY",
    "nyc":              "New York, NY",
    "losangeles":       "Los Angeles, CA",
    "houston":          "Houston, TX",
    "dallas":           "Dallas, TX",
    "miami":            "Miami, FL",
    "florida":          "Miami, FL",
    "sanfrancisco":     "San Francisco, CA",
    "bayarea":          "San Francisco, CA",
    "seattle":          "Seattle, WA",
    "boston":           "Boston, MA",
    "atlanta":          "Atlanta, GA",
    "phoenix":          "Phoenix, AZ",
    "denver":           "Denver, CO",
    "washingtondc":     "Washington, DC",
    "baltimore":        "Washington, DC",
    "minneapolis":      "Minnesota",
    "minnesota":        "Minnesota",
    "cleveland":        "Ohio",
    "columbus":         "Ohio",
    "detroit":          "Michigan",
    "newjersey":        "New Jersey",
    "philadelphia":     "Pennsylvania",
    "charlotte":        "North Carolina",
    "indianapolis":     "Indiana",
    "lasvegas":         "Las Vegas, NV",
    "portland":         "Portland, OR",
    "sandiego":         "San Diego, CA",
    "sacramento":       "Sacramento, CA",
    "austin":           "Austin, TX",
    "sanantonio":       "San Antonio, TX",
}

LOCATIONS = {
    "Chicago, IL":       ['chicago', 'schaumburg', 'chicagoland', 'cook county', 'naperville', 'evanston'],
    "New York, NY":      ['new york', 'nyc', 'brooklyn', 'queens', 'bronx', 'manhattan', 'staten island'],
    "Los Angeles, CA":   ['los angeles', 'l.a.', 'socal', 'hollywood', 'santa monica'],
    "Houston, TX":       ['houston', 'texas'],
    "Miami, FL":         ['miami', 'fort lauderdale', 'florida', 'orlando', 'tampa fl'],
    "San Francisco, CA": ['san francisco', 'bay area', 'silicon valley'],
    "Seattle, WA":       ['seattle', 'washington state', 'bellevue wa'],
    "Boston, MA":        ['boston', 'massachusetts'],
    "Atlanta, GA":       ['atlanta', 'georgia'],
    "Phoenix, AZ":       ['phoenix', 'arizona', 'scottsdale'],
    "Denver, CO":        ['denver', 'colorado'],
    "Washington, DC":    ['washington dc', 'washington, dc', 'maryland', 'northern virginia'],
    "Minnesota":         ['minnesota', 'minneapolis'],
    "Ohio":              ['ohio', 'cleveland', 'columbus ohio'],
    "Michigan":          ['michigan', 'detroit'],
    "New Jersey":        ['new jersey'],
    "Pennsylvania":      ['pennsylvania', 'philadelphia'],
    "North Carolina":    ['north carolina', 'charlotte nc'],
    "Indiana":           ['indiana', 'indianapolis'],
}


def detect_location(text: str, subreddit: str = "") -> str:
    """Detect US location from subreddit name or text content."""
    if subreddit:
        sub_lower = subreddit.lower()
        if sub_lower in SUBREDDIT_LOCATIONS:
            return SUBREDDIT_LOCATIONS[sub_lower]

    text_lower = ' ' + text.lower() + ' '
    for location, keywords in LOCATIONS.items():
        if any(kw in text_lower for kw in keywords):
            return location

    return ""


class RedditSource(BaseSource):
    def __init__(self, config: dict):
        self.subreddits = config.get("subreddits", [])
        self.posts_limit = config.get("posts_limit", 50)
        self.lookback_multiplier = config.get("check_interval_minutes", 15) * 4
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; ImmigrationMonitor/1.0)'
        })

    async def fetch(self, lookback_hours: int) -> List[MonitorItem]:
        """Fetch new posts from all configured subreddits via RSS."""
        all_items = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        for sub_config in self.subreddits:
            sub_name = sub_config["name"]
            try:
                items = self._fetch_subreddit_rss(sub_name, cutoff)
                all_items.extend(items)
                logger.info(f"r/{sub_name}: fetched {len(items)} items via RSS")
            except Exception as e:
                logger.error(f"Error fetching r/{sub_name} RSS: {e}")

        logger.info(f"Total Reddit items fetched: {len(all_items)}")
        return all_items

    def _fetch_subreddit_rss(self, subreddit_name: str, cutoff: datetime) -> List[MonitorItem]:
        """Fetch posts from a subreddit's RSS feed."""
        items = []
        rss_url = f"https://www.reddit.com/r/{subreddit_name}/new/.rss"

        try:
            response = self.session.get(rss_url, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(f"RSS feed parsing warning for r/{subreddit_name}: {feed.bozo_exception}")

            for entry in feed.entries[:self.posts_limit]:
                try:
                    if hasattr(entry, 'published_parsed'):
                        created = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    else:
                        created = datetime.now(timezone.utc)

                    if created < cutoff:
                        continue

                    post_id_match = re.search(r'/comments/([a-z0-9]+)/', entry.link)
                    post_id = post_id_match.group(1) if post_id_match else entry.id

                    author = "unknown"
                    if hasattr(entry, 'author'):
                        author_match = re.search(r'/u/(\w+)', entry.author)
                        if author_match:
                            author = author_match.group(1)
                        else:
                            author = entry.author

                    text_content = entry.title
                    if hasattr(entry, 'summary'):
                        summary_text = re.sub(r'<[^>]+>', '', entry.summary)
                        summary_text = re.sub(r'\s+', ' ', summary_text).strip()
                        if summary_text and summary_text != entry.title:
                            text_content = f"{entry.title}\n\n{summary_text}"

                    location = detect_location(text_content, subreddit_name)

                    items.append(MonitorItem(
                        id=f"reddit_post_{post_id}",
                        source="reddit_post",
                        channel=f"r/{subreddit_name}",
                        title=entry.title,
                        text=text_content,
                        url=entry.link,
                        author=author,
                        created_at=created,
                        language="en",
                        extra={
                            "subreddit": subreddit_name,
                            "location": location,
                        },
                    ))

                except Exception as e:
                    logger.warning(f"Error parsing RSS entry: {e}")
                    continue

        except requests.RequestException as e:
            logger.error(f"Failed to fetch RSS feed for r/{subreddit_name}: {e}")

        return items
