"""Abstract base collector."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import RawSignal


class BaseCollector(ABC):
    def __init__(self, config: dict):
        self.config = config

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...

    @abstractmethod
    async def collect(self) -> list[RawSignal]:
        ...
