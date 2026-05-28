import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import os
from db import (
    get_guild_config,
    set_online_channel,
    add_tracked_user,
    remove_tracked_user,
    get_tracked_users,
    update_user_status,
    clear_tracked_users,
)
from utils import get_uuid


class OnlineStatusCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        self.poll_status.start()

    async def cog_unload(self):
        self.poll_status.cancel()
        await self.session.close() 

    # ────────── Poll loop ──────────
    @tasks.loop(seconds=60)
    async def poll_status(self):
        for guild in self.bot.guilds:
            config = await get_guild_config(guild.id)
            if not config or not config["online_channel_id"]:
                continue
        
            channel = self.bot.get_channel(config["online_channel_id"])
            if channel is None:
                continue
            
            users = await get_tracked_users(guild.id)
            for user in users:
                try:
                    timeout = aiohttp.ClientTimeout(total=10)
                    async with self.session.get(
                        "https://api.hypixel.net/v2/status",
                        params={"uuid": user["uuid"]},
                        headers={"API-Key": os.getenv("HYPIXEL_API")},
                        timeout=timeout
                    ) as resp:
                        if resp.status != 200:
                            print(f"[Online] Hypixel API HTTP {resp.status} for {user['username']}")
                            continue
                        payload = await resp.json()
                except Exception as e:
                    print(f"[Online] failed to fetch {user['username']}: {e}")
                    continue

                session = payload.get("session")
                if not payload.get("success") or session is None:
                    continue  # API error or no session data -> leave status untouched

                current_status = bool(session.get("online", False))
                last_status = None if user["last_status"] is None else bool(user["last_status"])

                if last_status is None:
                    status_text = "online" if current_status else "offline"
                    await channel.send(f"{user['username']} is currently {status_text}!")
                elif last_status != current_status:
                    status_text = "logged on" if current_status else "logged off"
                    await channel.send(f"{user['username']} has {status_text}!")

                await update_user_status(guild.id, user["uuid"], current_status)

    @poll_status.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()

    # ────────── Commands ──────────
    @commands.hybrid_group(name="track", description="Manage player online status tracking")
    async def track(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Usage: ?track <set|add|remove|list|clear>")

    @track.command(name="set", description="Set this channel to receive online status notifications")
    async def track_set(self, ctx):
        await set_online_channel(ctx.guild.id, ctx.channel.id)
        await ctx.send(f"Online status notifications will be sent to {ctx.channel.mention}.")

    @track.command(name="add", description="Add a player to track")
    @app_commands.describe(username="Minecraft username")
    async def track_add(self, ctx, username: str):
        config = await get_guild_config(ctx.guild.id)
        if not config or not config["online_channel_id"]:
            await ctx.send("Online channel not set. Use `?track set` in the channel where you want notifications first.")
            return
        uuid = await get_uuid(username)
        if uuid is None:
            await ctx.send(f"Could not find player `{username}`.")
            return
        added = await add_tracked_user(ctx.guild.id, uuid, username)
        if not added:
            await ctx.send(f"**{username}** is already being tracked.")
            return
        await ctx.send(f"Now tracking **{username}**.")

    @track.command(name="remove", description="Remove a player from the tracking list")
    @app_commands.describe(username="Minecraft username")
    async def track_remove(self, ctx, username: str):
        uuid = await get_uuid(username)
        if uuid is None:
            await ctx.send(f"Could not find player `{username}`.")
            return
        removed = await remove_tracked_user(ctx.guild.id, uuid)
        if not removed:
            await ctx.send(f"**{username}** is not being tracked.")
            return
        await ctx.send(f"Removed **{username}** from the tracking list.")

    @track.command(name="list", description="Show all currently tracked players and their status")
    async def track_list(self, ctx):
        users = await get_tracked_users(ctx.guild.id)
        if not users:
            await ctx.send("No players are being tracked. Use `?track add <username>` to add one.")
            return

        embed = discord.Embed(title="Tracked Players", color=0x55ff55)
        for user in users:
            if user["last_status"] is None:
                status = "⏳ Unknown"
            elif user["last_status"]:
                status = "🟢 Online"
            else:
                status = "🔴 Offline"
            embed.add_field(name=user["username"], value=status, inline=False)

        await ctx.send(embed=embed)

    @track.command(name="clear", description="Stop tracking all players in this server")
    async def track_clear(self, ctx):
        count = await clear_tracked_users(ctx.guild.id)
        if count == 0:
            await ctx.send("No players were being tracked.")
            return
        await ctx.send(f"Stopped tracking {count} player{'s' if count != 1 else ''}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(OnlineStatusCog(bot))
