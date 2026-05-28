import json
import time
import discord
from .base import ItemStrategy
from utils import format_coins

# ────────── XP / level math ──────────
_CUM_XP = [
    0, 660, 1390, 2190, 3070, 4030, 5080, 6230, 7490, 8870,
    10380, 12030, 13830, 15790, 17920, 20230, 22730, 25430, 28350, 31510,
    34930, 38630, 42630, 46980, 51730, 56930, 62630, 68930, 75930, 83730,
    92430, 102130, 112930, 124930, 138230, 152930, 169130, 186930, 206430, 227730,
    250930, 276130, 303530, 333330, 365730, 400930, 439130, 480530, 525330, 573730,
    625930, 682130, 742530, 807330, 876730, 950930, 1030130, 1114830, 1205530, 1302730,
    1406930, 1518630, 1638330, 1766530, 1903730, 2050430, 2207130, 2374830, 2554530, 2747230,
    2953930, 3175630, 3413330, 3668030, 3940730, 4232430, 4544130, 4877830, 5235530, 5619230,
    6030930, 6472630, 6949330, 7466030, 8027730, 8639430, 9306130, 10032830, 10824530, 11686230,
    12622930, 13639630, 14741330, 15933030, 17219730, 18606430, 20103130, 21719830, 23466530, 25353230,
]

_HATCH_XP         = 25_353_230
_POST_HATCH_LVL102 = _HATCH_XP + 5_555
_POST_HATCH_PER_LVL = 1_886_700
_MAX_XP           = 210_255_385

def _xp_to_level(xp: float) -> float:
    if xp <= 0:
        return 1.0
    if xp <= _HATCH_XP:
        for i in range(99):
            if xp < _CUM_XP[i + 1]:
                frac = (xp - _CUM_XP[i]) / (_CUM_XP[i + 1] - _CUM_XP[i])
                return i + 1 + frac
        return 101.0
    if xp < _POST_HATCH_LVL102:
        frac = (xp - _HATCH_XP) / 5_555
        return 101.0 + frac
    post = xp - _POST_HATCH_LVL102
    return min(102.0 + post / _POST_HATCH_PER_LVL, 200.0)


# ────────── Strategy ──────────
class DragonStrategy(ItemStrategy):
    def __init__(self, pet_id, display_name, base_price, xp_rate, color, icon_url):
        self.pet_id       = pet_id
        self.display_name = display_name
        self.base_price   = base_price
        self.xp_rate      = xp_rate
        self.color        = color
        self.icon_url     = icon_url

    def get_item_id(self):
        return self.pet_id

    def prefilter(self, auction) -> bool:
        return True

    def parse(self, extra_attributes) -> dict | None:
        try:
            item_id = str(extra_attributes["id"])
            if item_id != "PET":
                return None
            pet_info = json.loads(str(extra_attributes["petInfo"]))
            pet_type = pet_info.get("type", "")
            if pet_type != self.pet_id:
                return None
            pet_xp   = float(pet_info.get("exp", 0))
            level    = _xp_to_level(pet_xp)
            candy_used = int(pet_info.get("candyUsed", 0))
            return {"pet_type": pet_type, "pet_xp": pet_xp, "level": level, "candy_used": candy_used}
        except Exception:
            return None

    def fair_price(self, item_data: dict) -> int:
        xp = item_data["pet_xp"]
        return int(self.base_price + min(xp, _MAX_XP) * self.xp_rate)

    def make_embed(self, auction: dict, item_data: dict, fair_price: int) -> discord.Embed:
        price    = auction["starting_bid"]
        discount = fair_price - price
        pct      = (discount / fair_price * 100) if fair_price > 0 else 0

        ends_ms   = auction.get("end", 0)
        time_left = max(0, ends_ms - int(time.time() * 1000))
        hours     = time_left // 3_600_000
        minutes   = (time_left % 3_600_000) // 60_000

        embed = discord.Embed(
            title=f"{self.display_name} — Favorable BIN!",
            color=self.color,
        )
        embed.set_thumbnail(url=self.icon_url)

        embed.add_field(name="Level",      value=f"**{item_data['level']:.1f}**",                    inline=True)
        embed.add_field(name="Pet XP",     value=f"{item_data['pet_xp']:,.0f}",                      inline=True)
        embed.add_field(name="Listed BIN", value=f"**{format_coins(price)}**",                       inline=True)
        embed.add_field(name="Fair price", value=format_coins(fair_price),                           inline=True)
        embed.add_field(name="Discount",   value=f"**{format_coins(discount)} ({pct:.1f}% off)**",   inline=True)
        embed.add_field(name="Ends in",    value=f"{hours}h {minutes}m",                             inline=True)

        if item_data["candy_used"] > 0:
            embed.add_field(name="⚠️ Candy Used", value=f"{item_data['candy_used']}/10", inline=True)

        embed.add_field(
            name="View",
            value=f"[sky.coflnet.com](https://sky.coflnet.com/auction/{auction['uuid']})",
            inline=False,
        )
        embed.set_footer(text=f"Auction {auction['uuid'][:8]}…  |  base {format_coins(self.base_price)} + {self.xp_rate} coins/XP")
        embed.timestamp = discord.utils.utcnow()
        return embed

    def make_no_deal_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{self.display_name} — No Favorable Deal",
            description="No favorable BIN found this poll.",
            color=self.color,
        )
        embed.set_thumbnail(url=self.icon_url)
        embed.timestamp = discord.utils.utcnow()
        return embed
