#!/usr/bin/env python3
"""Quick test script for Reddit monitor - fetches posts from r/immigration."""
import logging
import asyncio
import yaml
from sources.reddit import RedditSource

# Setup logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # Load config
    logger.info("Loading config...")
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Create Reddit monitor
    logger.info("Creating Reddit monitor...")
    reddit_config = config.get("reddit", {})
    monitor = RedditSource(reddit_config)

    # Fetch new posts from last 24 hours
    logger.info("Fetching posts from last 24 hours...")
    items = asyncio.run(monitor.fetch(lookback_hours=24))

    # Display results
    logger.info(f"\n{'='*60}")
    logger.info(f"Found {len(items)} posts total")
    logger.info(f"{'='*60}\n")

    if items:
        # Show first 5 items
        for i, item in enumerate(items[:5], 1):
            print(f"\n--- Post {i} ---")
            print(f"Channel: {item.channel}")
            print(f"Title: {item.title}")
            print(f"Author: u/{item.author}")
            print(f"Created: {item.created_at}")
            print(f"URL: {item.url}")
            print(f"Text preview: {item.text[:200]}...")
            print(f"ID: {item.id}")
    else:
        logger.warning("No items found!")

if __name__ == "__main__":
    main()
