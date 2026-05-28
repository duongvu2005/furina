import asyncio
import os
import discord
from discord.ext import commands
from db import init_db
from dotenv import load_dotenv

load_dotenv()
bot = commands.Bot(command_prefix="?", intents=discord.Intents.all())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')

@bot.event
async def on_guild_remove(guild):
    from db import clear_guild_data
    await clear_guild_data(guild.id)
    print(f"Cleaned up data for guild {guild.id} ({guild.name})")

async def main():
    await init_db()
    async with bot:
        await bot.load_extension("cogs.online_status")
        await bot.load_extension("cogs.ah_watcher")
        await bot.start(os.getenv("BOT_TOKEN"))


asyncio.run(main())