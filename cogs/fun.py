import asyncio
import datetime
import random
from typing import Optional, List, Dict, Any

import discord
from discord.ext import commands
from discord import option

from anime_api.apis import (
    AnimechanAPI,
    AnimeFactsRestAPI,
    TraceMoeAPI,
    NekosLifeAPI,
    KyokoAPI,
)

from config import config
from utils.assets import assets
from utils.database import db
from utils.metrics import tracker
from utils.ui.embed_factory import EmbedFactory
from utils.ui.fun import AskAgainButton
from utils.ui.fun_layout import FunLayoutView, create_fun_container

class Fun(commands.Cog):
    """
    Fun & Minigames: The heart of Itsumi's chaotic entertainment.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.description = "Games, anime tools, and social emotes."
        
        # API Wrappers
        self.facts_api = AnimeFactsRestAPI()
        self.quotes_api = AnimechanAPI()
        self.trace_api = TraceMoeAPI()
        self.life_api = NekosLifeAPI()
        self.kyoko_api = KyokoAPI()
        
        # Lazy-loaded data caches
        self._message_caches: Dict[str, List[str]] = {}

    # --- Internal Data Helpers ---

    async def _get_messages(self, category: str, key: str) -> List[str]:
        """Lazy-loads and caches message lists from assets."""
        cache_key = f"{category}:{key}"
        if cache_key not in self._message_caches:
            self._message_caches[cache_key] = await assets.load_message(category, key)
        return self._message_caches[cache_key]

    async def _fetch_json(self, url: str, headers: dict = None) -> Optional[dict]:
        """Safe JSON fetch with proxy rotation support."""
        # Use config proxies if available
        proxies = [config.PROXY_URL] if config.PROXY_URL else [None]
        
        for p in proxies:
            try:
                async with self.bot.session.get(url, headers=headers, timeout=5, proxy=p) as resp:
                    if resp.status == 200:
                        return await resp.json()
            except Exception:
                continue
        return None

    async def _get_anime_image(self, endpoint: str) -> Optional[str]:
        """Fetches a random image/gif from supported anime APIs."""
        waifu_im_tags = ["waifu", "maid", "marin-kitagawa", "mori-calliope", "raiden-shogun", "oppai", "selfies", "uniform"]
        
        if endpoint in waifu_im_tags:
            url = f"https://api.waifu.im/images?included_tags={endpoint}&is_nsfw=false"
            data = await self._fetch_json(url, headers={"Accept": "application/json"})
            if data and "items" in data:
                return data["items"][0]["url"]
            return None

        # Fallback to nekos.best
        url = f"https://nekos.best/api/v2/{endpoint}"
        data = await self._fetch_json(url)
        return data["results"][0]["url"] if data and "results" in data else None

    # --- Container Builders ---

    async def build_ooc_container(self) -> discord.ui.Container:
        messages = await self._get_messages("fun", "ooc")
        return create_fun_container(
            title="📸 Out of Context",
            body=f"> {random.choice(messages)}",
            accessory=AskAgainButton(is_ooc=True),
        )

    async def build_8ball_container(self, user: discord.Member, question: str) -> discord.ui.Container:
        answers = await self._get_messages("fun", "8ball")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = f"> **Question:** {question}\n> \n> **Answer:** *{random.choice(answers)}*\n\nAsked by {user.mention} | {now}"
        return create_fun_container(title="8 Balls 🎱", body=body, accessory=AskAgainButton())

    async def build_rate_container(self, thing: str) -> discord.ui.Container:
        responses = await self._get_messages("fun", "rate")
        return create_fun_container(
            title="⚖️ The Official Rating",
            body=f"**Thing:** {thing}\n\n**Rating:** {random.choice(responses)}",
            accessory=AskAgainButton(rate_thing=thing),
        )

    # --- Commands ---

    @discord.slash_command(name="backflip", description="Try to perform a backflip!")
    async def backflip(self, ctx: discord.ApplicationContext):
        success = random.random() < 0.55
        stats = await db.minigames.update_backflip(ctx.author.id, success, guild_id=ctx.guild_id or 0)
        
        category = "backflip_success" if success else "backflip_fail"
        messages = await self._get_messages("fun", category)
        
        title = "🤸 Backflip Success!" if success else "🤕 Backflip Fail!"
        body = f"{ctx.author.mention} {random.choice(messages)}\n\n"
        body += f"**Streak:** {stats['current']} 🔥 | **Best:** {stats['best']} 🏆"
        
        await ctx.respond(view=FunLayoutView(create_fun_container(title, body, accessory=AskAgainButton(is_backflip=True))))

    @discord.slash_command(name="roulette", description="Play Russian Roulette")
    async def roulette(self, ctx: discord.ApplicationContext):
        death = random.randint(1, 6) == 1
        stats = await db.minigames.update_roulette(ctx.author.id, not death, guild_id=ctx.guild_id or 0)
        
        title = "💥 BANG!" if death else "🛡️ *Click*"
        color = discord.Color.red() if death else discord.Color.green()
        body = "Rest in pieces." if death else "The chamber was empty."
        body += f"\n\n**Survival Rate:** {stats['survived']}/{stats['survived'] + stats['died']}"
        
        await ctx.respond(view=FunLayoutView(create_fun_container(title, body, color=color, accessory=AskAgainButton(is_roulette=True))))

    # (rest of commands omitted for brevity in this turn, but they follow the same pattern ...)

def setup(bot):
    bot.add_cog(Fun(bot))
