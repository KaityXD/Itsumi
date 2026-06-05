import datetime
from typing import Optional

import discord

import config


class EmbedFactory:
    """
    Standardizes the look and feel of all embeds across the bot.
    """

    SUCCESS_COLOR = discord.Color(config.SUCCESS_COLOR)
    ERROR_COLOR = discord.Color(config.ERROR_COLOR)
    WARN_COLOR = discord.Color(config.WARN_COLOR)
    INFO_COLOR = discord.Color(config.DEFAULT_COLOR)
    BOT_FOOTER = "Itsumi-pycord System"

    @staticmethod
    def _base_embed(
        title: str,
        description: str,
        color: discord.Color,
        ctx: Optional[discord.ApplicationContext] = None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.now(),
        )
        footer_text = EmbedFactory.BOT_FOOTER
        if ctx:
            footer_text += f" | Requested by {ctx.author.name}"
        embed.set_footer(text=footer_text)
        return embed

    @staticmethod
    def success(
        title: str, description: str, ctx: Optional[discord.ApplicationContext] = None
    ) -> discord.Embed:
        return EmbedFactory._base_embed(
            f"✅ {title}", description, EmbedFactory.SUCCESS_COLOR, ctx
        )

    @staticmethod
    def error(
        title: str,
        description: str,
        ctx: Optional[discord.ApplicationContext] = None,
        error_id: Optional[str] = None,
    ) -> discord.Embed:
        desc = description
        if error_id:
            desc += (
                f"\n\n**Error ID:** `{error_id}`\nPlease report this to the developer."
            )
        return EmbedFactory._base_embed(
            f"❌ {title}", desc, EmbedFactory.ERROR_COLOR, ctx
        )

    @staticmethod
    def warn(
        title: str, description: str, ctx: Optional[discord.ApplicationContext] = None
    ) -> discord.Embed:
        return EmbedFactory._base_embed(
            f"⚠️ {title}", description, EmbedFactory.WARN_COLOR, ctx
        )

    @staticmethod
    def info(
        title: str, description: str, ctx: Optional[discord.ApplicationContext] = None
    ) -> discord.Embed:
        return EmbedFactory._base_embed(
            f"ℹ️ {title}", description, EmbedFactory.INFO_COLOR, ctx
        )
