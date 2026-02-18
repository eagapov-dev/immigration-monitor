"""
Telegram source - fetches messages from configured groups/chats and channels.
Uses Telethon (Telegram client API) to read messages.

Note: This uses a USER account (not a bot), because bots can only
see messages in groups where they are added as members.

Groups vs Channels:
- Groups: two-way chats where members ask questions (source="telegram")
- Channels: one-way broadcasts by admins (source="telegram_channel")
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List

from telethon import TelegramClient
from telethon.tl.types import Message, Channel
from telethon.errors import (
    ChannelPrivateError,
    ChatAdminRequiredError,
    FloodWaitError,
)

from sources.base import BaseSource, MonitorItem

logger = logging.getLogger(__name__)


class TelegramSource(BaseSource):
    def __init__(self, config: dict):
        self.api_id = int(config["api_id"])
        self.api_hash = config["api_hash"]
        self.phone = config["phone"]
        self.session_name = config.get("session_name", "immigration_monitor")
        self.groups = config.get("groups", [])
        self.channels = config.get("channels", [])
        self.messages_limit = config.get("messages_limit", 100)
        self.client = None

    async def connect(self):
        """Connect to Telegram."""
        self.client = TelegramClient(
            self.session_name, self.api_id, self.api_hash
        )
        await self.client.start(phone=self.phone)
        logger.info("Telegram client connected")

    async def disconnect(self):
        """Disconnect from Telegram."""
        if self.client:
            await self.client.disconnect()

    async def fetch(self, lookback_hours: int) -> List[MonitorItem]:
        """Fetch new messages from all configured groups and channels."""
        if not self.client or not self.client.is_connected():
            await self.connect()

        all_items = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        for group_config in self.groups:
            try:
                items = await self._fetch_entity(group_config, cutoff, source_type="telegram")
                all_items.extend(items)
                logger.info(
                    f"TG group {group_config.get('name', 'unknown')}: fetched {len(items)} items"
                )
                await asyncio.sleep(1)
            except FloodWaitError as e:
                logger.warning(f"Flood wait: {e.seconds}s. Sleeping...")
                await asyncio.sleep(e.seconds + 1)
            except ChannelPrivateError:
                logger.warning(
                    f"Cannot access private group: {group_config.get('name', 'unknown')}"
                )
            except ChatAdminRequiredError:
                logger.warning(
                    f"Admin required for: {group_config.get('name', 'unknown')}"
                )
            except Exception as e:
                logger.error(
                    f"Error fetching group {group_config.get('name', 'unknown')}: {e}"
                )

        for channel_config in self.channels:
            try:
                items = await self._fetch_entity(channel_config, cutoff, source_type="telegram_channel")
                all_items.extend(items)
                logger.info(
                    f"TG channel {channel_config.get('name', 'unknown')}: fetched {len(items)} items"
                )
                await asyncio.sleep(1)
            except FloodWaitError as e:
                logger.warning(f"Flood wait: {e.seconds}s. Sleeping...")
                await asyncio.sleep(e.seconds + 1)
            except ChannelPrivateError:
                logger.warning(
                    f"Cannot access private channel: {channel_config.get('name', 'unknown')}"
                )
            except Exception as e:
                logger.error(
                    f"Error fetching channel {channel_config.get('name', 'unknown')}: {e}"
                )

        logger.info(f"Total Telegram items fetched: {len(all_items)}")
        return all_items

    async def _fetch_entity(
        self, entity_config: dict, cutoff: datetime, source_type: str
    ) -> List[MonitorItem]:
        """Fetch messages from a single group or channel."""
        items = []

        username = entity_config.get("username")
        invite_link = entity_config.get("invite_link")
        entity_name = entity_config.get("name", username or "Unknown")
        lang = entity_config.get("language", "ru")
        is_channel = source_type == "telegram_channel"

        try:
            if username:
                entity = await self.client.get_entity(username)
            elif invite_link:
                entity = await self.client.get_entity(invite_link)
            else:
                logger.warning(f"No username or invite_link for: {entity_name}")
                return []
        except Exception as e:
            logger.error(f"Cannot resolve entity for {entity_name}: {e}")
            return []

        # For channels use entity title as default author
        channel_title = getattr(entity, "title", entity_name)

        async for message in self.client.iter_messages(
            entity, limit=self.messages_limit, offset_date=None
        ):
            if not isinstance(message, Message):
                continue

            if not message.text:
                continue

            created = (
                message.date.replace(tzinfo=timezone.utc)
                if message.date.tzinfo is None
                else message.date
            )
            if created < cutoff:
                break

            if username:
                url = f"https://t.me/{username}/{message.id}"
            else:
                url = f"https://t.me/c/{entity.id}/{message.id}"

            # Channels: author is the channel itself; groups: individual sender
            if is_channel:
                author = channel_title
            else:
                author = "Unknown"
                if message.sender:
                    try:
                        sender = await message.get_sender()
                        if hasattr(sender, "first_name"):
                            author = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                        elif hasattr(sender, "title"):
                            author = sender.title
                    except Exception:
                        pass

            # Reply context (groups only; channels use linked discussion groups)
            is_reply = message.reply_to is not None
            reply_text = None
            if not is_channel and is_reply and message.reply_to:
                try:
                    reply_msg = await self.client.get_messages(
                        entity, ids=message.reply_to.reply_to_msg_id
                    )
                    if reply_msg and reply_msg.text:
                        reply_text = reply_msg.text[:200]
                except Exception:
                    pass

            items.append(MonitorItem(
                id=f"tg_{entity.id}_{message.id}",
                source=source_type,
                channel=entity_name,
                title="",
                text=message.text,
                url=url,
                author=author,
                created_at=created,
                language=lang,
                extra={
                    "username": username,
                    "is_reply": is_reply,
                    "reply_to_text": reply_text,
                },
            ))

        return items
