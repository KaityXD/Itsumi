import datetime
from typing import Dict, Optional

import discord

from config import config


class EmbedFactory:
    """
    Standardizes the look and feel of all embeds across the bot.
    """

    SUCCESS_COLOR = discord.Color(config.SUCCESS_COLOR)
    ERROR_COLOR = discord.Color(config.ERROR_COLOR)
    WARN_COLOR = discord.Color(config.WARN_COLOR)
    INFO_COLOR = discord.Color(config.DEFAULT_COLOR)
    PURPLE_COLOR = discord.Color.from_rgb(163, 114, 251)
    BOT_FOOTER = "Itsumi-pycord System"

    @staticmethod
    def _base_embed(
        title: str,
        description: str,
        color: discord.Color,
        ctx: Optional[discord.ApplicationContext] = None,
        ephemeral: bool = False,
        image_url: Optional[str] = None,
    ) -> discord.Embed:
        from utils.registry import registry

        r_id = registry.register_response(
            "EMBED", 
            {"title": title, "description": description}, 
            interaction=ctx,
            ephemeral=ephemeral
        )

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.now(),
        )
        if image_url:
            embed.set_image(url=image_url)

        footer_text = EmbedFactory.BOT_FOOTER
        if ctx:
            user = ctx.user if isinstance(ctx, discord.Interaction) else ctx.author
            footer_text += f" | Requested by {user.name}"

        footer_text += f" | Type: Embed | r-id: {r_id}"
        embed.set_footer(text=footer_text)

        return embed

    @staticmethod
    def custom(
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[discord.Color] = None,
        ctx: Optional[discord.ApplicationContext] = None,
        footer: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> discord.Embed:
        """
        Creates a clean, user-facing embed without system footprints (timestamps, 'Requested by').
        Still registers the response for forensic tracking.
        """
        from utils.registry import registry
        
        r_id = registry.register_response(
            "CUSTOM_EMBED", 
            {"title": title, "description": description}, 
            interaction=ctx
        )

        embed = discord.Embed(
            title=title,
            description=description,
            color=color or EmbedFactory.INFO_COLOR
        )
        if image_url:
            embed.set_image(url=image_url)
        
        # We append the r-id so that forensic tools can extract it, 
        # but we omit timestamps and 'Requested by' to keep it clean.
        footer_text = footer if footer else ""
        if footer_text:
            footer_text += f" | r-id: {r_id}"
        else:
            footer_text = f"r-id: {r_id}"
            
        embed.set_footer(text=footer_text)
        
        return embed

    @staticmethod
    def system(
        title: str,
        fields: Dict[str, str],
        ctx: Optional[discord.ApplicationContext] = None,
        color: Optional[discord.Color] = None,
        ephemeral: bool = False,
    ) -> discord.Embed:
        """
        Creates a clean, field-heavy embed aesthetic based on the provided reference.
        """
        from utils.registry import registry

        r_id = registry.register_response(
            "SYSTEM_EMBED", 
            {"title": title, "fields": fields}, 
            interaction=ctx,
            ephemeral=ephemeral
        )

        embed = discord.Embed(
            title=title,
            color=color or EmbedFactory.PURPLE_COLOR,
            timestamp=datetime.datetime.now(),
        )

        # Re-order fields to ensure User/Moderator are side-by-side if they exist
        # and Reason is below them.
        ordered_fields = {}
        # First pass: User/Moderator/ID
        for key in ["User", "Moderator", "ID", "Type"]:
            if key in fields:
                ordered_fields[key] = fields[key]
        
        # Second pass: Everything else except Reason/Time
        for key, value in fields.items():
            if key not in ordered_fields and key not in ["Reason", "Time"]:
                ordered_fields[key] = value
        
        # Third pass: Reason
        if "Reason" in fields:
            ordered_fields["Reason"] = fields["Reason"]

        for name, value in ordered_fields.items():
            inline = name in ["User", "Moderator", "ID", "Type"]
            embed.add_field(name=f"**{name}**", value=value, inline=inline)

        # Custom Time field as seen in the image
        now = datetime.datetime.now()
        date_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
        relative_str = f"Today at {now.strftime('%I:%M %p')}"

        embed.add_field(
            name="**Time**", value=f"```\n{date_str}\n```\n{relative_str}", inline=False
        )

        footer_text = f"Type: System | r-id: {r_id}"
        if ctx:
            footer_text = f"Requested by {ctx.author.name} | {footer_text}"
            embed.set_footer(text=footer_text, icon_url=ctx.author.display_avatar.url)
        else:
            embed.set_footer(text=footer_text)

        return embed

    @staticmethod
    def success(
        title: str, description: str, ctx: Optional[discord.ApplicationContext] = None, image_url: Optional[str] = None
    ) -> discord.Embed:
        return EmbedFactory._base_embed(
            f"✅ {title}", description, EmbedFactory.SUCCESS_COLOR, ctx, image_url=image_url
        )

    @staticmethod
    def error(
        title: str,
        description: str,
        ctx: Optional[discord.ApplicationContext] = None,
        error_id: Optional[str] = None,
        details: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> discord.Embed:
        desc = description
        if details:
            desc += f"\n\n**Error Details:**\n`{details}`"
        if error_id:
            desc += (
                f"\n\n**Error ID:** `{error_id}`\nPlease report this to the developer."
            )
        return EmbedFactory._base_embed(
            f"❌ {title}", desc, EmbedFactory.ERROR_COLOR, ctx, image_url=image_url
        )

    @staticmethod
    def warn(
        title: str, description: str, ctx: Optional[discord.ApplicationContext] = None, image_url: Optional[str] = None
    ) -> discord.Embed:
        return EmbedFactory._base_embed(
            f"⚠️ {title}", description, EmbedFactory.WARN_COLOR, ctx, image_url=image_url
        )

    @staticmethod
    def info(
        title: str, description: str, ctx: Optional[discord.ApplicationContext] = None, image_url: Optional[str] = None
    ) -> discord.Embed:
        return EmbedFactory._base_embed(
            f"ℹ️ {title}", description, EmbedFactory.INFO_COLOR, ctx, image_url=image_url
        )

    @staticmethod
    def toast(message: str, ctx: discord.ApplicationContext, success: bool = True) -> discord.Embed:
        """
        Creates a compact 'Toast' style notification for quick feedback.
        """
        color = EmbedFactory.SUCCESS_COLOR if success else EmbedFactory.ERROR_COLOR
        icon = "✅" if success else "❌"
        
        return EmbedFactory._base_embed(
            f"{icon} {message}", 
            "", 
            color, 
            ctx, 
            ephemeral=True
        )
