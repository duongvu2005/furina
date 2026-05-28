import aiohttp
import base64
import io
import nbt.nbt


async def get_uuid(username: str) -> str | None:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.mojang.com/users/profiles/minecraft/{username}"
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["id"]
    return None


def parse_item_extra_attributes(item_bytes_b64: str):
    """
    Decode item_bytes and return the ExtraAttributes compound tag, or None on failure.

    Structure verified empirically:
      nbt_file            -> root compound with one TAG_List("i")
      [0]                 -> the inventory list
      [0]                 -> the single item compound {id, Count, tag, Damage}
      ["tag"]             -> Minecraft item tag compound
      ["ExtraAttributes"] -> Hypixel custom data (id, uuid, petInfo, etc.)
    """
    try:
        raw = base64.b64decode(item_bytes_b64)
        nbt_file = nbt.nbt.NBTFile(fileobj=io.BytesIO(raw))
        return nbt_file[0][0]["tag"]["ExtraAttributes"]
    except Exception:
        return None