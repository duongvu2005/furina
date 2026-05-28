# ── Schema ────────────────────────────────────────────────────────────────────
#
# guild_config
# ┌─────────────────────┬─────────┬──────────┐
# │ guild_id (PK)       │ INTEGER │ NOT NULL │
# │ online_channel_id   │ INTEGER │ nullable │
# │ ah_channel_id       │ INTEGER │ nullable │
# └─────────────────────┴─────────┴──────────┘
#          │
#          │ 1
#          │
#          ◆ many
# tracked_users                                    watched_items
# ┌─────────────────────┬─────────┬──────────┐    ┌──────────────────────┬─────────┬──────────┐
# │ guild_id (PK, FK)   │ INTEGER │ NOT NULL │    │ guild_id (PK, FK)    │ INTEGER │ NOT NULL │
# │ uuid     (PK)       │ TEXT    │ NOT NULL │    │ item_key (PK)        │ TEXT    │ NOT NULL │
# │ username            │ TEXT    │ nullable │    │ last_best_uuid       │ TEXT    │ nullable │
# │ last_status         │ INTEGER │ nullable │    └──────────────────────┴─────────┴──────────┘
# └─────────────────────┴─────────┴──────────┘
#
# Notes:
#   - last_status: 0 = offline, 1 = online, NULL = unknown
#   - last_best_uuid: NULL = not yet seen, used to deduplicate AH alerts
#   - one guild_config row per guild; INSERT OR IGNORE on first command
#   - composite PK on tracked_users/watched_items means same entry can exist across guilds
#   - item_key must match a key in STRATEGIES (e.g. "GOLDEN_DRAGON")
#
# ──────────────────────────────────────────────────────────────────────────────

import aiosqlite

DB_PATH = "bot.db"

# ────────── Setup ──────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        with open("schema.sql") as f:
            await db.executescript(f.read())
        await db.commit()


# ────────── Guild Config ──────────
async def set_online_channel(guild_id: int, channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_config (guild_id, online_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET online_channel_id = excluded.online_channel_id
        """, (guild_id, channel_id))
        await db.commit()

async def set_ah_channel(guild_id: int, channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_config (guild_id, ah_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET ah_channel_id = excluded.ah_channel_id             
        """, (guild_id, channel_id))
        await db.commit()

async def get_guild_config(guild_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def clear_guild_data(guild_id: int) -> None:
    """Wipe all data for a guild. Used when the bot is removed from a guild,
    or for explicit admin teardown."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tracked_users WHERE guild_id = ?", (guild_id,))
        await db.execute("DELETE FROM watched_items WHERE guild_id = ?", (guild_id,))
        await db.execute("DELETE FROM guild_config WHERE guild_id = ?", (guild_id,))
        await db.commit()

# ────────── Tracked Users ──────────
async def add_tracked_user(guild_id: int, uuid: str, username: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT OR IGNORE INTO tracked_users (guild_id, uuid, username, last_status)
            VALUES (?, ?, ?, NULL)
        """, (guild_id, uuid, username))
        await db.commit()
        return cursor.rowcount > 0  # False if already existed

async def remove_tracked_user(guild_id, uuid: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM tracked_users WHERE guild_id = ? AND uuid = ?",
            (guild_id, uuid)
        )
        await db.commit()
        return cursor.rowcount > 0  # True if a row was deleted

async def get_tracked_users(guild_id: int)  -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT uuid, username, last_status FROM tracked_users WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def update_user_status(guild_id: int, uuid: str, status: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE tracked_users SET last_status = ?
            WHERE guild_id = ? AND uuid = ?
        """, (int(status), guild_id, uuid))
        await db.commit()

async def clear_tracked_users(guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM tracked_users WHERE guild_id = ?", (guild_id,)
        )
        await db.commit()
        return cursor.rowcount  # number of rows deleted

# ────────── Watched Items ──────────
async def get_watched_items(guild_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT item_key, last_best_uuid FROM watched_items WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def add_watched_item(guild_id: int, item_key: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT OR IGNORE INTO watched_items (guild_id, item_key, last_best_uuid)
            VALUES (?, ?, NULL)
        """, (guild_id, item_key))
        await db.commit()
        return cursor.rowcount > 0

async def remove_watched_item(guild_id: int, item_key: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM watched_items WHERE guild_id = ? AND item_key = ?",
            (guild_id, item_key)
        )
        await db.commit()
        return cursor.rowcount > 0

async def update_last_best_uuid(guild_id: int, item_key: str, uuid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE watched_items SET last_best_uuid = ?
            WHERE guild_id = ? AND item_key = ?
        """, (uuid, guild_id, item_key))
        await db.commit()

async def clear_watched_items(guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM watched_items WHERE guild_id = ?", (guild_id,)
        )
        await db.commit()
        return cursor.rowcount
