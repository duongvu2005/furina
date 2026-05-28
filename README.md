# Furina

A Discord bot for tracking Hypixel SkyBlock player online status and
auction-house deals on configurable items.

## Features

- **Player tracking** — get notified in Discord when tracked players log on
  or off Hypixel.
- **Auction house alerts** — get notified when a favorable BIN appears for
  watched items. Currently supports the three dragon pets (Golden, Rose,
  Jade); the strategy interface is pluggable for new item types.

## Setup

1. Clone the repo and install dependencies:
```
   pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in:
   - `BOT_TOKEN` — your Discord bot token
   - `HYPIXEL_API` — your Hypixel API key (request one in-game with `/api new`)

3. Run:
```
   python main.py
```

The bot auto-creates `bot.db` on first run and syncs slash commands to all
guilds it's in.

## Commands

All commands work as both prefix (`?`) and slash (`/`) invocations.

### Player tracking

| Command | Description |
|---|---|
| `?track set` | Set the current channel to receive online/offline notifications |
| `?track add <username>` | Start tracking a Minecraft player |
| `?track remove <username>` | Stop tracking a player |
| `?track list` | Show all tracked players and their current status |
| `?track clear` | Stop tracking all players in this server |

### Auction house alerts

| Command | Description |
|---|---|
| `?ah set` | Set the current channel to receive AH alerts |
| `?ah watch <item_key>` | Start watching an item for favorable BINs (e.g. `GOLDEN_DRAGON`) |
| `?ah unwatch <item_key>` | Stop watching an item |
| `?ah summary` | Show a compact summary of all watched items and their best current deal |
| `?ah show` | Re-post the full per-item embeds to the AH channel |
| `?ah clear` | Stop watching all items in this server |

You must `?track set` / `?ah set` a channel before adding players or items.

## Adding new AH item strategies

The AH watcher is built around a strategy pattern. To support a new item:

1. Create a new class in `cogs/strategies/` that subclasses `ItemStrategy`
   (see `base.py`). Implement `parse`, `fair_price`, `make_embed`, and
   `make_no_deal_embed`. Optionally override `prefilter` to skip irrelevant
   auctions before the NBT decode.
2. Register the strategy in `cogs/strategies/__init__.py` under a unique
   `item_key`.

The poll loop will pick it up automatically.

## Architecture

- `main.py` — bot entry point, loads cogs.
- `db.py` — async SQLite access (guild config, tracked users, watched items).
- `schema.sql` — table definitions.
- `cogs/online_status.py` — player tracking via Hypixel's `/v2/status`.
- `cogs/ah_watcher.py` — auction-house polling, candidate filtering, alert
  dispatch.
- `cogs/strategies/` — per-item pricing and rendering logic.
- `utils/` — Mojang UUID lookup, NBT parsing, coin formatting.