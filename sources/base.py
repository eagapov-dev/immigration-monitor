"""
Base classes for monitor sources.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class MonitorItem:
    id: str
    source: str       # 'reddit_post', 'reddit_comment', 'telegram'
    channel: str      # r/immigration, @group, etc.
    title: str
    text: str
    url: str
    author: str
    created_at: datetime
    language: str = "en"
    extra: dict = field(default_factory=dict)  # source-specific data


class BaseSource:
    async def fetch(self, lookback_hours: int) -> List[MonitorItem]:
        raise NotImplementedError

    async def connect(self):
        pass

    async def disconnect(self):
        pass
