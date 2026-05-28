import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import asyncio
import time
 
from utils import parse_item_extra_attributes, format_coins
from .strategies import STRATEGIES
from db import (
    get_guild_config,
    set_ah_channel,
    get_watched_items,
    add_watched_item,
    remove_watched_item,
    update_last_best_uuid,
    clear_watched_items,
)


class AHWatcherCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.session = None
        self.latest_deals: dict[str, tuple | None] = {}
        self.last_poll_ts: float | None = None
        self.last_poll_auctions: int = 0

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        self.poll_ah.start()

    async def cog_unload(self):
        self.poll_ah.cancel()
        await self.session.close()

    # ────────── AH fetching ──────────
    async def fetch_page(self, page: int) -> dict:
        timeout = aiohttp.ClientTimeout(total=10)
        async with self.session.get(
            "https://api.hypixel.net/v2/skyblock/auctions",
            params={"page": page},
            timeout=timeout
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def fetch_all_auctions(self) -> list[dict]:
        first = await self.fetch_page(0)
        if not first.get("success"):
            return []

        total_pages  = first.get("totalPages", 1)
        all_auctions = list(first.get("auctions", []))

        for batch_start in range(1, total_pages, 10):
            batch_end = min(batch_start + 10, total_pages)
            results   = await asyncio.gather(
                *[self.fetch_page(p) for p in range(batch_start, batch_end)],
                return_exceptions=True,
            )
            for res in results:
                if isinstance(res, Exception):
                    continue
                if res.get("auctions"):
                    all_auctions.extend(res["auctions"])

        return all_auctions

    # ────────── Poll loop ──────────
    @tasks.loop(seconds=60)
    async def poll_ah(self):
        try:
            auctions = await self.fetch_all_auctions()
        except Exception as e:
            print(f"[AH] fetch error: {e}")
            return

        # build candidates: {strategy: [(diff, auction, item_data, fair_price)]}
        all_candidates: dict[int, list] = {item_id: [] for item_id in STRATEGIES.keys()}

        for auction in auctions:
            if not auction.get("bin"):
                continue

            interested = {k:v for k, v in STRATEGIES.items() if v.prefilter(auction)}
            if not interested:
                continue

            item_bytes = auction.get("item_bytes")
            if not item_bytes:
                continue

            extra = parse_item_extra_attributes(item_bytes)
            if extra is None:
                continue
    
            for item_id, strategy in interested.items():
                item_data = strategy.parse(extra)
                if item_data is None:
                    continue

                fair_price = strategy.fair_price(item_data)
                price_diff = fair_price - auction["starting_bid"]
                if price_diff <= 0:
                    continue

                all_candidates[item_id].append((price_diff, auction, item_data, fair_price))

        # Snapshot the best deal per item for ?ah list (guild-independent).
        for item_id, strategy in STRATEGIES.items():
            candidates = all_candidates[item_id]
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                _diff, best_auction, item_data, fair_price = candidates[0]
                self.latest_deals[item_id] = (best_auction, item_data, fair_price)
            else:
                self.latest_deals[item_id] = None
 
        self.last_poll_ts       = time.time()
        self.last_poll_auctions = len(auctions)

        # alert per guild
        for guild in self.bot.guilds:
            config = await get_guild_config(guild.id)
            if not config or not config["ah_channel_id"]:
                continue

            channel = self.bot.get_channel(config["ah_channel_id"])
            if channel is None:
                continue

            watched = await get_watched_items(guild.id)
            watched_keys = {row["item_key"]: row["last_best_uuid"] for row in watched}

            for item_id, strategy in STRATEGIES.items():
                if item_id not in watched_keys:
                    continue

                deal = self.latest_deals.get(item_id)
                if deal is None:
                    if watched_keys[item_id] != "NONE":
                        await update_last_best_uuid(guild.id, item_id, "NONE")
                        embed = strategy.make_no_deal_embed()
                        await channel.send(embed=embed)
                    continue

                best_auction, item_data, fair_price = deal
                best_uuid = best_auction["uuid"]

                # Only alert when the best deal changed vs. what we last alerted.
                if watched_keys[item_id] == best_uuid:
                    continue

                await update_last_best_uuid(guild.id, item_id, best_uuid)
                embed = strategy.make_embed(best_auction, item_data, fair_price)
                await channel.send(embed=embed)
                diff = fair_price - best_auction["starting_bid"]
                print(f"[AH] {strategy.display_name} diff={format_coins(diff)}")

    @poll_ah.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()

    # ────────── Commands ──────────
    @commands.hybrid_group(name="ah", description="Manage AH deal alerts")
    async def ah(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Usage: ?ah <set|watch|unwatch|summary|show|clear>")

    @ah.command(name="set", description="Set this channel to receive AH alerts")
    async def ah_set(self, ctx):
        await set_ah_channel(ctx.guild.id, ctx.channel.id)
        await ctx.send(f"AH alerts will be sent to {ctx.channel.mention}.")

    @ah.command(name="watch", description="Start watching an item for favorable deals")
    @app_commands.describe(item="Item key to watch (e.g. GOLDEN_DRAGON)")
    async def ah_watch(self, ctx, item: str):
        config = await get_guild_config(ctx.guild.id)
        if not config or not config["ah_channel_id"]:
            await ctx.send("AH channel not set. Use `?ah set` in the channel where you want alerts first.")
            return
        key = item.upper()
        if not any(item_id == key for item_id in STRATEGIES.keys()):
            await ctx.send(f"Unknown item `{key}`. No strategy registered for it.")
            return
        added = await add_watched_item(ctx.guild.id, key)
        if not added:
            await ctx.send(f"`{key}` is already being watched.")
            return
        await ctx.send(f"Now watching **{key}** for favorable deals.")

    @ah.command(name="unwatch", description="Stop watching an item")
    @app_commands.describe(item="Item key to unwatch (e.g. GOLDEN_DRAGON)")
    async def ah_unwatch(self, ctx, item: str):
        key = item.upper()
        removed = await remove_watched_item(ctx.guild.id, key)
        if not removed:
            await ctx.send(f"`{key}` is not being watched.")
            return
        await ctx.send(f"Stopped watching **{key}**.")

    @ah.command(
        name="summary",
        description="Show a compact summary of all watched items and their current best deal",
    )
    async def ah_summary(self, ctx):
        watched = await get_watched_items(ctx.guild.id)
        if not watched:
            await ctx.send("No items being watched. Use `?ah watch <item>` to add one.")
            return

        embed = discord.Embed(title="👀 Watched Items", color=0xFFAA00)
        for row in watched:
            strategy = STRATEGIES.get(row["item_key"])
            if strategy is None:
                continue
            if self.last_poll_ts is None:
                status = "⏳ Not yet polled"
            else:
                deal = self.latest_deals.get(row["item_key"])
                if deal is None:
                    status = "❌ No favorable deal"
                else:
                    best_auction, item_data, fair_price = deal
                    price    = best_auction["starting_bid"]
                    discount = fair_price - price
                    uuid     = best_auction["uuid"]
                    status = (
                        f"✅ {format_coins(price)} "
                        f"({format_coins(discount)} off) — "
                        f"[view](https://sky.coflnet.com/auction/{uuid})"
                    )
            embed.add_field(name=strategy.display_name, value=status, inline=False)

        if self.last_poll_ts is None:
            embed.set_footer(text="No scan completed yet — first poll runs within a minute.")
        else:
            ago = int(time.time() - self.last_poll_ts)
            embed.set_footer(
                text=f"Last scan {ago}s ago · {self.last_poll_auctions:,} auctions"
            )
            embed.timestamp = discord.utils.utcnow()
 
        await ctx.send(embed=embed)

    @ah.command(
        name="show",
        description="Re-post the full deal embed for every watched item into the AH channel",
    )
    async def ah_show(self, ctx):
        watched = await get_watched_items(ctx.guild.id)
        if not watched:
            await ctx.send("No items being watched. Use `?ah watch <item>` to add one.")
            return
 
        if self.last_poll_ts is None:
            await ctx.send("No scan completed yet — first poll runs within a minute.")
            return
 
        # Re-post one embed per watched item. Does NOT update last_best_uuid:
        for row in watched:
            strategy = STRATEGIES.get(row["item_key"])
            if strategy is None:
                continue
            deal = self.latest_deals.get(row["item_key"])
            if deal is None:
                embed = strategy.make_no_deal_embed()
            else:
                best_auction, item_data, fair_price = deal
                embed = strategy.make_embed(best_auction, item_data, fair_price)
            await ctx.send(embed=embed)

    @ah.command(name="clear", description="Stop watching all items in this server")
    async def ah_clear(self, ctx):
        count = await clear_watched_items(ctx.guild.id)
        if count == 0:
            await ctx.send("No items were being watched.")
            return
        await ctx.send(f"Stopped watching {count} item{'s' if count != 1 else ''}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(AHWatcherCog(bot))