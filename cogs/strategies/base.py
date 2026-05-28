import discord
from abc import ABC, abstractmethod


class ItemStrategy(ABC):
    @abstractmethod
    def get_item_id(self):
        """
        Unique item id to store in the database.
        """
        ...

    def prefilter(self, auction: dict) -> bool:
        """
        Cheap pre-NBT-parse filter. Return True if this strategy might be
        interested in the auction; False to skip. Default: parse everything.
        """
        return True

    @abstractmethod
    def parse(self, extra_attributes) -> dict | None:
        """
        Extract relevant data from ExtraAttributes NBT tag.
        Return a dict of item data, or None if this auction should be skipped.
        """
        ...

    @abstractmethod
    def fair_price(self, item_data: dict) -> int:
        """Calculate the fair price for this item given parsed item data."""
        ...

    @abstractmethod
    def make_embed(self, auction: dict, item_data: dict, fair_price: int) -> discord.Embed:
        """Build the Discord embed for an alert."""
        ...

    @abstractmethod
    def make_no_deal_embed(self) -> discord.Embed:
        """Build the Discord embed when no favorable deal is found."""
        ...