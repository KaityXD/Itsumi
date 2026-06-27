import datetime
import json
import logging
import os
import traceback
import uuid
from typing import Optional

import discord

from utils.assets import assets

audit_logger = logging.getLogger("audit")


class UniversalErrorHandler:
    def __init__(self, logs_dir: Optional[str] = None):
        self.logs_dir = logs_dir or assets.get_path("logs", "errors")
        assets.ensure_dir("logs", "errors")
        assets.ensure_dir("logs", "guilds")
        assets.ensure_dir("logs", "global")

    def log_command(self, ctx: discord.ApplicationContext):
        """Logs a successful command execution to the audit log and permanent history."""
        import uuid

        from utils.audit import get_audit_logger
        from utils.registry import registry

        v_id = f"cmd-{str(uuid.uuid4())[:8]}"
        sess_id = registry.get_session(ctx.author.id)

        guild_id = ctx.guild.id if ctx.guild else None
        audit = get_audit_logger(guild_id)

        user_info = f"{ctx.author} ({ctx.author.id})"
        guild_info = f"{ctx.guild.name} ({ctx.guild.id})" if ctx.guild else "DM"
        command_info = f"/{ctx.command.name}"

        audit.success(
            f"{user_info} in {guild_info} executed {command_info} [v-id: {v_id}] [sess-id: {sess_id}]"
        )

        # Save to permanent history
        registry.register_interaction(
            v_id,
            {
                "type": "COMMAND_EXECUTION",
                "command": ctx.command.name,
                "user": {"name": str(ctx.author), "id": ctx.author.id},
                "guild": {
                    "name": ctx.guild.name if ctx.guild else "DM",
                    "id": ctx.guild.id if ctx.guild else None,
                },
                "channel_id": ctx.channel.id if ctx.channel else None,
                "status": "SUCCESS",
                "session_id": sess_id,
            },
        )

    def save_error(
        self, error: Exception, ctx: Optional[discord.ApplicationContext] = None
    ) -> str:
        error_id = str(uuid.uuid4())[:8]
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        # Extract location information
        tb = traceback.extract_tb(error.__traceback__)
        location = {"file": "Unknown", "line": 0, "function": "Unknown"}
        if tb:
            # Try to find a frame that isn't in discord library
            target_frame = tb[-1]
            for frame in reversed(tb):
                if "discord" not in frame.filename and "aiohttp" not in frame.filename:
                    target_frame = frame
                    break
            location = {
                "file": os.path.basename(target_frame.filename),
                "path": target_frame.filename,
                "line": target_frame.lineno,
                "function": target_frame.name,
                "text": target_frame.line,
            }

        from utils.logger import logger as fast_logger

        fast_logger.error(
            f"Captured error {error_id} at {location['file']}:L{location['line']} -> {type(error).__name__}"
        )

        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        tb_text = "".join(tb_lines)

        error_data = {
            "error_id": error_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "location": location,
            "traceback": tb_text,
        }

        if isinstance(error, discord.NotFound) and getattr(error, "code", None) in (10062, 10015):
            error_data["expired_interaction_hint"] = "Discord interaction expired (likely exceeded the 3-second response window) or webhook was not found."

        from utils.registry import registry

        registry.register_error(error_id, error_data)

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
        original_error = error
        if isinstance(error, discord.ApplicationCommandInvokeError):
            error = error.original

        # Check if the error is a timeout
        import asyncio
        is_timeout = isinstance(error, (asyncio.TimeoutError, TimeoutError))
        if not is_timeout:
            if isinstance(error, discord.NotFound) and getattr(error, "code", None) in (10062, 10015):
                is_timeout = True
            elif "timeout" in str(error).lower() or "timeout" in error.__class__.__name__.lower():
                is_timeout = True

        if is_timeout:
            from utils.ui.embed_factory import EmbedFactory
            embed = EmbedFactory.error(
                "Interaction Timed Out",
                "This interaction has timed out. Please try running the command again.",
                ctx=ctx
            )
            try:
                if ctx.interaction.response.is_done():
                    await ctx.followup.send(embed=embed, ephemeral=True)
                else:
                    await ctx.respond(embed=embed, ephemeral=True)
            except Exception:
                pass
            return

        error_id = self.save_error(original_error, ctx)

        # Reload error data to get location (or we could return it from save_error)
        tb = traceback.extract_tb(original_error.__traceback__)
        line_info = ""
        if tb:
            target_frame = tb[-1]
            for frame in reversed(tb):
                if "discord" not in frame.filename and "aiohttp" not in frame.filename:
                    target_frame = frame
                    break
            line_info = f"\n*Caused at {os.path.basename(target_frame.filename)}:L{target_frame.lineno} in {target_frame.name}*"

        error_message = str(error)
        if len(error_message) > 500:
            error_message = error_message[:497] + "..."

        error_message += line_info

        # Check for DNS/Connection errors and add context
        error_suffix = ""
        if "ClientConnectorDNSError" in str(original_error) or "DNSError" in str(original_error):
            error_suffix = "\n\n**⚠️ Note:** This appears to be a network/DNS issue."

        error_message += error_suffix

        from utils.ui.embed_factory import EmbedFactory
        embed = EmbedFactory.error(
            "An Error Occurred",
            "Something went wrong while executing this command.",
            ctx=ctx,
            error_id=error_id,
            details=error_message,
        )

        view = None
        # Add a "View Trace" button if the user is an owner
        from config import config
        owners = getattr(config, "OWNERS", [])
        if ctx.author.id in owners:
            from utils.ui.forensics import ForensicTraceExplorer
            from utils.ui.fun_layout import FunLayoutView
            
            explorer = ForensicTraceExplorer(ctx, error_id)
            await explorer.initialize()
            container = await explorer.build_page()
            view = FunLayoutView(container, original_view=explorer)

        try:
            if ctx.interaction.response.is_done():
                await ctx.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                await ctx.respond(embed=embed, view=view, ephemeral=True)
        except:
            pass

    async def handle_ui_error(self, interaction: discord.Interaction, error: Exception):
        """Processes and reports errors occurring within Views or Modals."""
        # Check if the error is a timeout
        import asyncio
        is_timeout = isinstance(error, (asyncio.TimeoutError, TimeoutError))
        if not is_timeout:
            if isinstance(error, discord.NotFound) and getattr(error, "code", None) in (10062, 10015):
                is_timeout = True
            elif "timeout" in str(error).lower() or "timeout" in error.__class__.__name__.lower():
                is_timeout = True

        if is_timeout:
            from utils.ui.embed_factory import EmbedFactory
            embed = EmbedFactory.error(
                "Interaction Timed Out",
                "This interaction has timed out. Please try running the command again.",
                ctx=None
            )
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception:
                pass
            return

        # Wrap interaction in a fake context for save_error compat
        class FakeContext:
            def __init__(self, interaction):
                self.interaction = interaction
                self.author = interaction.user
                self.guild = interaction.guild
                self.channel = interaction.channel
                self.command = None

        ctx = FakeContext(interaction)
        error_id = self.save_error(error, ctx)

        tb = traceback.extract_tb(error.__traceback__)
        line_info = ""
        if tb:
            target_frame = tb[-1]
            for frame in reversed(tb):
                if "discord" not in frame.filename and "aiohttp" not in frame.filename:
                    target_frame = frame
                    break
            line_info = f"\n*Caused at {os.path.basename(target_frame.filename)}:L{target_frame.lineno} in {target_frame.name}*"

        error_message = f"`{str(error)}`{line_info}"

        from utils.ui.embed_factory import EmbedFactory
        embed = EmbedFactory.error(
            "Interface Error",
            "An unexpected error occurred while interacting with this menu.",
            error_id=error_id,
            details=error_message
        )

        view = None
        from config import config
        owners = getattr(config, "OWNERS", [])
        if interaction.user.id in owners:
            from utils.ui.forensics import ForensicTraceExplorer
            from utils.ui.fun_layout import FunLayoutView
            
            explorer = ForensicTraceExplorer(interaction, error_id)
            await explorer.initialize()
            container = await explorer.build_page()
            view = FunLayoutView(container, original_view=explorer)

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except:
            pass
