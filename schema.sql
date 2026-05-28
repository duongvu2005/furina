CREATE TABLE IF NOT EXISTS guild_config (
    guild_id          INTEGER PRIMARY KEY,
    online_channel_id INTEGER,
    ah_channel_id     INTEGER
);

CREATE TABLE IF NOT EXISTS tracked_users (
    guild_id    INTEGER,
    uuid        TEXT,
    username    TEXT,
    last_status INTEGER,
    PRIMARY KEY (guild_id, uuid),
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id)
);

CREATE TABLE IF NOT EXISTS watched_items (
    guild_id       INTEGER,
    item_key       TEXT,
    last_best_uuid TEXT,
    PRIMARY KEY (guild_id, item_key),
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id)
);