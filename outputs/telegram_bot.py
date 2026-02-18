"""
Telegram output - sends classified immigration questions
to a notification channel/group.
"""
import logging
from typing import Optional
from datetime import datetime

from outputs.base import BaseOutput
from sources.base import MonitorItem

logger = logging.getLogger(__name__)


class TelegramOutput(BaseOutput):
    def __init__(self, bot_token: str, channel_id: int, max_per_hour: int = 30):
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.max_per_hour = max_per_hour
        self._bot = None

    async def _get_bot(self):
        if self._bot is None:
            from telegram import Bot
            self._bot = Bot(token=self.bot_token)
        return self._bot

    def _format_message(
        self,
        item: MonitorItem,
        category: Optional[str],
        urgency: Optional[str],
        summary: Optional[str],
        draft_response: Optional[str],
    ) -> str:
        """Format a notification message."""
        source_emoji = {
            "reddit_post": "🔴",
            "reddit_comment": "💬",
            "telegram": "✈️",
        }.get(item.source, "📝")

        urgency_emoji = {
            "high": "🔥",
            "medium": "⚡",
            "low": "💡",
        }.get(urgency, "")

        category_labels = {
            "visa": "🛂 Visa",
            "asylum": "🛡 Asylum",
            "deportation": "⚠️ Deportation",
            "green_card": "💚 Green Card",
            "work": "💼 Work Permit",
            "family": "👨‍👩‍👧 Family",
            "citizenship": "🇺🇸 Citizenship",
            "tps": "🔄 TPS/DACA",
            "other": "📋 Other",
        }
        category_label = category_labels.get(category, "📋 Other")

        preview = item.text[:500]
        if len(item.text) > 500:
            preview += "..."

        location = item.extra.get("location", "")
        is_chicago = location == "Chicago, IL"
        if is_chicago:
            location_label = "📍 Chicago, IL ⭐"
        elif location:
            location_label = f"📍 {location}"
        else:
            location_label = ""

        # group_name label with context for reddit comments
        group_label = item.channel
        if item.source == "reddit_comment" and item.extra.get("parent_title"):
            group_label += f" (re: {item.extra['parent_title'][:50]})"

        lines = [
            f"{source_emoji} **{group_label}** {urgency_emoji}",
            f"📂 {category_label}{' | ' + location_label if location_label else ''}",
            "",
            f"📝 {preview}",
            "",
        ]

        if summary:
            lines.append(f"📌 *{summary}*")
            lines.append("")

        if draft_response:
            lines.append(f"✏️ **Draft response:**")
            lines.append(draft_response)
            lines.append("")

        lines.append(f"🔗 [Open source]({item.url})")
        lines.append(f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}")

        return "\n".join(lines)

    async def send(self, item: MonitorItem, result, db) -> bool:
        """Send a notification to the Telegram channel."""
        if db:
            count = db.get_notifications_count_last_hour()
            if count >= self.max_per_hour:
                logger.warning(
                    f"Rate limit reached ({count}/{self.max_per_hour} per hour). Skipping."
                )
                return False

        message = self._format_message(
            item=item,
            category=result.category,
            urgency=result.urgency,
            summary=result.summary,
            draft_response=result.draft_response,
        )

        try:
            bot = await self._get_bot()
            await bot.send_message(
                chat_id=self.channel_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            logger.info(f"Notification sent: {item.source} - {item.channel}")
            return True

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            try:
                plain_message = message.replace("**", "").replace("*", "")
                bot = await self._get_bot()
                await bot.send_message(
                    chat_id=self.channel_id,
                    text=plain_message,
                    disable_web_page_preview=True,
                )
                return True
            except Exception as e2:
                logger.error(f"Retry also failed: {e2}")
                return False

    async def send_stats(self, stats: dict):
        """Send daily statistics summary."""
        message = (
            "📊 **Daily Stats**\n\n"
            f"Total processed: {stats.get('total_processed', 0)}\n"
            f"Total notified: {stats.get('total_notified', 0)}\n"
            f"Today processed: {stats.get('today_processed', 0)}\n\n"
            "By source:\n"
        )
        for source, count in stats.get("by_source", {}).items():
            message += f"  - {source}: {count}\n"

        try:
            bot = await self._get_bot()
            await bot.send_message(
                chat_id=self.channel_id,
                text=message,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Failed to send stats: {e}")
