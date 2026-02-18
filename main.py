"""
Immigration Monitor - Main orchestrator.

Runs Reddit and Telegram monitors on schedule,
classifies posts, sends notifications to Telegram channel.

Usage:
    python main.py                  # Run continuously
    python main.py --once           # Run once and exit
    python main.py --stats          # Show statistics
    python main.py --test-notify    # Send a test notification
"""
import asyncio
import logging
import argparse
import signal
import sys
import os
import json
from datetime import datetime

import yaml

from database import Database
from classifiers import Classifier
from sources.reddit import RedditSource
from sources.telegram import TelegramSource
from outputs.telegram_bot import TelegramOutput


def setup_logging(config: dict):
    log_config = config.get("logging", {})
    log_level = getattr(logging, log_config.get("level", "INFO"))
    log_file = log_config.get("file", "logs/monitor.log")

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ImmigrationMonitor:
    def __init__(self, config: dict):
        self.config = config
        self.db = Database(config.get("database", {}).get("path", "data/processed.db"))
        self.classifier = Classifier(config.get("classification", {}))

        notif_config = config.get("notifications", {})
        self.include_draft = notif_config.get("include_draft_response", True)
        self.min_text_length = notif_config.get("min_text_length", 30)

        # Initialize sources
        self.sources = []
        reddit_config = config.get("reddit", {})
        if reddit_config.get("subreddits"):
            self.sources.append(RedditSource(reddit_config))
            logger.info("Reddit source initialized (RSS mode - no API needed)")

        tg_config = config.get("telegram", {})
        if tg_config.get("api_id") and tg_config["api_id"] != "YOUR_API_ID":
            self.sources.append(TelegramSource(tg_config))
            logger.info("Telegram source initialized")

        # Initialize outputs
        self.outputs = []
        notif_config = config.get("notifications", {})
        if tg_config.get("bot_token"):
            self.outputs.append(TelegramOutput(
                bot_token=tg_config.get("bot_token", ""),
                channel_id=tg_config.get("notification_channel_id", 0),
                max_per_hour=notif_config.get("max_per_hour", 30),
            ))

        # Keep reference to TelegramOutput for test-notify and stats
        self._tg_output = self.outputs[0] if self.outputs else None

        self._running = True

    async def process_source(self, source, lookback_hours: int):
        """Universal source processor."""
        source_name = type(source).__name__
        logger.info(f"=== Processing {source_name} ===")

        try:
            items = await source.fetch(lookback_hours)
        except Exception as e:
            logger.error(f"{source_name} fetch error: {e}")
            return

        new_count = 0
        notified_count = 0

        for item in items:
            if self.db.is_processed(item.id):
                continue

            if len(item.text) < self.min_text_length:
                self.db.mark_processed(
                    item.id, item.source, item.channel, item.text, item.url
                )
                continue

            result = self.classifier.classify(
                text=item.text,
                source_lang=item.language,
                include_draft=self.include_draft,
            )

            location = item.extra.get("location", "")

            classification_json = json.dumps({
                "is_relevant": result.is_relevant,
                "is_question": result.is_question,
                "category": result.category,
                "urgency": result.urgency,
                "location": location,
            })
            self.db.mark_processed(
                item.id, item.source, item.channel, item.text, item.url,
                classification=classification_json,
            )
            new_count += 1

            # Channels broadcast content (no questions expected) — relevance is enough
            is_actionable = result.is_relevant and (
                result.is_question or item.source == "telegram_channel"
            )
            if is_actionable:
                for output in self.outputs:
                    sent = await output.send(item, result, self.db)
                    if sent:
                        self.db.mark_notified(item.id)
                        notified_count += 1
                        await asyncio.sleep(1)
                        break  # Only notify once per item even if multiple outputs

        logger.info(f"{source_name}: {new_count} new items, {notified_count} notifications sent")

    async def run_once(self):
        """Run a single check cycle."""
        logger.info(f"--- Cycle started at {datetime.utcnow().isoformat()} ---")

        # Connect sources that require it
        for source in self.sources:
            await source.connect()

        reddit_config = self.config.get("reddit", {})
        telegram_config = self.config.get("telegram", {})

        for source in self.sources:
            if isinstance(source, RedditSource):
                lookback = reddit_config.get("check_interval_minutes", 15) * 4
                lookback_hours = max(lookback / 60, 1)
                await self.process_source(source, int(lookback_hours))
            elif isinstance(source, TelegramSource):
                lookback_hours = telegram_config.get("lookback_hours", 2)
                await self.process_source(source, lookback_hours)

        self.db.cleanup_old_records(days=30)
        logger.info(f"--- Cycle completed ---\n")

    async def run_forever(self):
        """Run monitor continuously on schedule."""
        logger.info("Immigration Monitor started. Press Ctrl+C to stop.")

        for source in self.sources:
            await source.connect()

        reddit_config = self.config.get("reddit", {})
        telegram_config = self.config.get("telegram", {})

        reddit_interval = reddit_config.get("check_interval_minutes", 15) * 60
        telegram_interval = telegram_config.get("check_interval_minutes", 30) * 60

        has_reddit = any(isinstance(s, RedditSource) for s in self.sources)
        has_telegram = any(isinstance(s, TelegramSource) for s in self.sources)

        min_interval = min(
            reddit_interval if has_reddit else float("inf"),
            telegram_interval if has_telegram else float("inf"),
        )
        if min_interval == float("inf"):
            logger.error("No sources configured. Exiting.")
            return

        last_run = {type(s).__name__: 0 for s in self.sources}

        while self._running:
            now = asyncio.get_event_loop().time()

            try:
                for source in self.sources:
                    name = type(source).__name__
                    if isinstance(source, RedditSource):
                        interval = reddit_interval
                        lookback_hours = max(reddit_config.get("check_interval_minutes", 15) * 4 / 60, 1)
                    else:
                        interval = telegram_interval
                        lookback_hours = telegram_config.get("lookback_hours", 2)

                    if (now - last_run[name]) >= interval:
                        await self.process_source(source, int(lookback_hours))
                        last_run[name] = now

            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)

            await asyncio.sleep(60)

    def stop(self):
        self._running = False

    async def cleanup(self):
        for source in self.sources:
            await source.disconnect()
        self.db.close()


async def main():
    parser = argparse.ArgumentParser(description="Immigration Monitor")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--test-notify", action="store_true", help="Send test notification")
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config)

    monitor = ImmigrationMonitor(config)

    def signal_handler(sig, frame):
        logger.info("Shutdown signal received...")
        monitor.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if args.stats:
            stats = monitor.db.get_stats()
            print("\n📊 Immigration Monitor Statistics:")
            print(f"  Total processed: {stats['total_processed']}")
            print(f"  Total notified:  {stats['total_notified']}")
            print(f"  Today processed: {stats['today_processed']}")
            print("  By source:")
            for source, count in stats.get("by_source", {}).items():
                print(f"    {source}: {count}")
            return

        if args.test_notify:
            if monitor._tg_output:
                from sources.base import MonitorItem
                from classifiers import ClassificationResult
                from datetime import timezone

                test_item = MonitorItem(
                    id="test_001",
                    source="reddit_post",
                    channel="r/test",
                    title="Test",
                    text="This is a test notification from Immigration Monitor 🤖",
                    url="https://reddit.com/r/test",
                    author="test",
                    created_at=datetime.now(timezone.utc),
                )
                test_result = ClassificationResult(
                    is_relevant=True,
                    is_question=True,
                    category="other",
                    urgency="low",
                    summary="Test notification",
                )
                await monitor._tg_output.send(test_item, test_result, None)
            print("✅ Test notification sent!")
            return

        if args.once:
            await monitor.run_once()
        else:
            await monitor.run_forever()

    finally:
        await monitor.cleanup()
        logger.info("Monitor stopped.")


if __name__ == "__main__":
    asyncio.run(main())
