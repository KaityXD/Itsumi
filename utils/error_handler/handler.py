import datetime
import json
import logging
import os
import traceback
import uuid
from typing import Optional

import discord

audit_logger = logging.getLogger("audit")


class UniversalErrorHandler:
    def __init__(self, logs_dir: str = "logs/errors"):
        self.logs_dir = logs_dir
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)

        # Setup audit logging directory
        if not os.path.exists("logs/audit"):
            os.makedirs("logs/audit")

    def log_command(self, ctx: discord.ApplicationContext):
        """Logs a successful command execution to the audit log."""
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        file_path = f"logs/audit/{date_str}.log"

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        user_info = f"{ctx.author} ({ctx.author.id})"
        guild_info = f"{ctx.guild.name} ({ctx.guild.id})" if ctx.guild else "DM"
        command_info = f"/{ctx.command.name}"

        log_entry = (
            f"[{timestamp}] [CMD] {user_info} in {guild_info} executed {command_info}\n"
        )

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
        audit_logger.info(f"Command executed: {command_info} by {user_info}")

    def save_error(
        self, error: Exception, ctx: Optional[discord.ApplicationContext] = None
    ) -> str:
        error_id = str(uuid.uuid4())[:8]
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        error_data = {
            "error_id": error_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
        }

        if ctx:
            error_data["context"] = {
                "command": ctx.command.name if ctx.command else "Unknown",
                "user_id": ctx.author.id,
                "user_name": str(ctx.author),
                "guild_id": ctx.guild.id if ctx.guild else None,
                "channel_id": ctx.channel.id if ctx.channel else None,
                "interaction_id": ctx.interaction.id,
                "view_id": ctx.interaction.data.get("custom_id")
                if ctx.interaction.data
                else None,
            }

        day_dir = os.path.join(self.logs_dir, date_str)
        if not os.path.exists(day_dir):
            os.makedirs(day_dir)

        file_path = os.path.join(day_dir, f"{error_id}.json")
        with open(file_path, "w") as f:
            json.dump(error_data, f, indent=4)

        return error_id

    async def handle_error(self, ctx: discord.ApplicationContext, error: Exception):
        # Prevent double handling if it's already an ApplicationCommandInvokeError
        if isinstance(error, discord.ApplicationCommandInvokeError):
            error = error.original

        error_id = self.save_error(error, ctx)

        from utils.ui.embed_factory import EmbedFactory

        embed = EmbedFactory.error(
            "An Error Occurred",
            "Something went wrong while executing this command.",
            ctx=ctx,
            error_id=error_id,
        )

        try:
            if ctx.interaction.response.is_done():
                await ctx.followup.send(embed=embed, ephemeral=True)
            else:
                await ctx.respond(embed=embed, ephemeral=True)
        except:
            pass
