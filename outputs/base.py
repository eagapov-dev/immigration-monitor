"""
Base class for monitor outputs.
"""
from sources.base import MonitorItem


class BaseOutput:
    async def send(self, item: MonitorItem, result, db) -> bool:
        raise NotImplementedError
