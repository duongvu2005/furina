from .base import ItemStrategy
from .dragon import DragonStrategy

STRATEGIES: dict[str, ItemStrategy] = {
    "GOLDEN_DRAGON": DragonStrategy(
        pet_id        = "GOLDEN_DRAGON",
        display_name  = "Golden Dragon",
        base_price    = 627_000_000,
        xp_rate       = 1.8,
        color         = 0xFFAA00,
        icon_url      = "https://sky.shiiyu.moe/api/head/2e9f9b1fc014166cb46a093e5349b2bf6edd201b680d62e48dbf3af9b0459116"
    ),
    "ROSE_DRAGON": DragonStrategy(
        pet_id        = "ROSE_DRAGON",
        display_name  = "Rose Dragon",
        base_price    = 570_000_000,
        xp_rate       = 2.0,
        color         = 0xFF55AA,
        icon_url      = "https://sky.shiiyu.moe/api/head/9b7c3de075a2bb238ef51431206b10d586cb2a5b1cc41fe851cc5f0b02d357c7"
    ),
    "JADE_DRAGON": DragonStrategy(
        pet_id        = "JADE_DRAGON",
        display_name  = "Jade Dragon",
        base_price    = 545_000_000,
        xp_rate       = 0.65,
        color         = 0x00CC66,
        icon_url      = "https://sky.shiiyu.moe/api/head/4099589796de185787ab92c3066d0d0af832ffad7153a42bb2e2d23598e7ea60"
    ),
}