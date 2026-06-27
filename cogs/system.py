import asyncio
import datetime
import importlib
import json
import math
import os
import re
import shutil
import time
import uuid

import discord
from discord import option
from discord.ext import commands, tasks

from utils.assets import assets
from utils.database import db
from utils.error_handler import UniversalErrorHandler
from utils.logger import logger
from utils.metrics import tracker
from utils.permissions import PermissionLevel, has_level, perms
from utils.registry import registry
from utils.ui.embed_factory import EmbedFactory
from utils.ui.fun_layout import FunLayoutView, create_fun_container


class Developer(commands.Cog):
    """
    Dedicated tools for bot developers.
    Provides deep inspection, log management, and system maintenance.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_task.start()
        self.backup_task.start()

        registry.register_task("cleanup_task", self.cleanup_task)
        registry.register_task("backup_task", self.backup_task)

    def cog_unload(self):
        self.cleanup_task.cancel()
        self.backup_task.cancel()

    @tasks.loop(hours=24)
    async def backup_task(self):
        """Creates a timestamped backup of the consolidated database."""
        if not os.path.exists(db.db_path):
            # Database might not be initialized yet
            return

        backup_dir = os.path.join(assets.get_path("database"), "backups")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"itsumi_backup_{timestamp}.db")

        try:
            # Safely copy the SQLite file (works even while open in WAL mode)
            shutil.copy2(db.db_path, backup_path)

            # Keep only the last 7 backups
            backups = sorted([f for f in os.listdir(backup_dir) if f.endswith(".db")])
            if len(backups) > 7:
                for old_backup in backups[:-7]:
                    os.remove(os.path.join(backup_dir, old_backup))

            logger.success(f"Database backup created: {backup_path}")
        except Exception as e:
            logger.error(f"Database backup failed: {e}")

    @tasks.loop(hours=24)
    async def cleanup_task(self):
        """Maintenance task to purge logs older than the retention period."""
        run_id = registry.log_task_run("cleanup_task", "STARTING")
        logger.info(f"Executing scheduled log maintenance... [run-id: {run_id}]")

        from config import config
        LOG_RETENTION_DAYS = config.LOG_RETENTION_DAYS

        now = time.time()
        retention_seconds = LOG_RETENTION_DAYS * 24 * 60 * 60
        removed_count = 0

        # Crawl all log categories
        log_categories = [["logs", "errors"], ["logs", "guilds"], ["logs", "global"]]

        for category in log_categories:
            base_dir = assets.get_path(*category)
            if not os.path.exists(base_dir):
                continue

            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                try:
                    if os.path.isdir(item_path):
                        # Attempt to parse date-named folders
                        try:
                            folder_date = datetime.datetime.strptime(item, "%Y-%m-%d")
                            if (
                                datetime.datetime.now() - folder_date
                            ).days > LOG_RETENTION_DAYS:
                                shutil.rmtree(item_path)
                                removed_count += 1
                        except ValueError:
                            pass
                    elif os.path.getmtime(item_path) < (now - retention_seconds):
                        os.remove(item_path)
                        removed_count += 1
                except Exception as e:
                    logger.warning(f"Failed to cleanup item at {item_path}: {e}")

        logger.success(f"Maintenance complete. Purged {removed_count} stale log items.")
        registry.log_task_run("cleanup_task", "COMPLETED", {"purged": removed_count})

    @cleanup_task.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

    # --- Slash Command Group ---

    dev = discord.SlashCommandGroup(
        "dev",
        "Exclusive tools for the bot developers",
        checks=[commands.is_owner().predicate],
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
        contexts={
            discord.InteractionContextType.guild,
            discord.InteractionContextType.bot_dm,
            discord.InteractionContextType.private_channel,
        },
    )

    # --- Autocompletes ---

    async def id_autocomplete(self, ctx: discord.AutocompleteContext):
        """Fetches recent View or Error IDs for autocomplete selection."""
        recent_ids = registry.get_recent_ids()

        if not ctx.value:
            return recent_ids[:25]

        # Filter by user input and limit results
        return [rid for rid in recent_ids if ctx.value.lower() in rid.lower()][:25]

    # --- Developer Commands ---

    @dev.command(
        name="inspect",
        description="Identify and inspect any bot component by its ID (v-id or e-id)",
    )
    async def inspect(
        self,
        ctx: discord.ApplicationContext,
        any_id: discord.Option(
            str, "The ID to inspect (v-id or e-id)", autocomplete=id_autocomplete
        ),
    ):
        """Peeks into the internal registry to find details about a specific component."""
        # Strip prefixes if they were manually typed
        target_id = any_id.split(":")[-1].strip()
        info = await registry.identify(target_id)

        if info["type"] == "VIEW":
            view = info.get("obj")
            data = info.get("data", {})

            status_icon = "🟢" if info["status"] == "ACTIVE" else "📂"
            title = f"🔍 Component Inspection: {info['status']}"

            fields = {
                "Type": f"`{data.get('class', 'discord.ui.View')}`",
                "ID": f"`{target_id}`",
                "Status": f"{status_icon} **{info['status']}**",
            }

            if view:
                fields["Components"] = f"{len(view.children)} items in structure"
            elif "items" in data:
                fields["Components"] = f"{len(data['items'])} items (snapshot)"

            if "logged_at" in data:
                fields["Timestamp"] = f"`{data['logged_at']}`"

            embed = EmbedFactory.system(title, fields, ctx=ctx)
            await ctx.respond(embed=embed, ephemeral=True)

        elif info["type"] == "ERROR":
            data = info["data"]
            fields = {
                "Type": f"`{data['error_type']}`",
                "ID": f"`{target_id}`",
                "Status": "📂 **ARCHIVED**"
                if info["status"] == "ARCHIVED"
                else "🔴 **LIVE**",
                "Exception": f"```{data['error_message']}```",
            }
            embed = EmbedFactory.system(
                "🔍 Error Trace Registry", fields, ctx=ctx, color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)

        elif info["type"] == "COMMAND" or (
            info["type"] == "INTERACTION" and target_id.startswith("cmd-")
        ):
            data = info.get("data", {})
            fields = {
                "Type": "🚀 **COMMAND EXECUTION**",
                "ID": f"`{target_id}`",
                "Command": f"`/{data.get('command', 'unknown')}`",
                "User": f"{data.get('user_name', 'Unknown')} (`{data.get('user_id', '???')}`)",
                "Guild": f"`{data.get('guild_id', 'DM')}`",
                "Timestamp": f"`{data.get('logged_at', '???')}`",
            }
            embed = EmbedFactory.system(
                "🔍 History Inspection", fields, ctx=ctx, color=discord.Color.purple()
            )
            await ctx.respond(embed=embed, ephemeral=True)

        elif info["type"] == "RESPONSE" or target_id.startswith("r-"):
            data = info.get("data", {})
            fields = {
                "Type": f"📤 **BOT RESPONSE ({data.get('response_type', 'TEXT')})**",
                "ID": f"`{target_id}`",
                "Ephemeral": "✅ **YES**" if data.get("ephemeral") else "❌ **NO**",
                "User": f"{data.get('user', {}).get('name', '???')} (`{data.get('user', {}).get('id', '???')}`)",
                "Guild": f"`{data.get('guild', {}).get('name', 'DM')}`",
                "Timestamp": f"`{data.get('logged_at', '???')}`",
            }

            content = data.get("content", "No content available.")
            if isinstance(content, dict):
                content_str = "\n".join([f"**{k}:** {v}" for k, v in content.items()])
            else:
                content_str = str(content)

            if len(content_str) > 500:
                content_str = content_str[:497] + "..."

            fields["Content Preview"] = content_str

            embed = EmbedFactory.system(
                "🔍 Response Inspection", fields, ctx=ctx, color=discord.Color.teal()
            )
            await ctx.respond(embed=embed, ephemeral=True)

        elif info["type"] != "UNKNOWN":
            data = info.get("data", {})
            fields = {
                "Type": f"📦 **{info['type']}**",
                "ID": f"`{target_id}`",
                "Status": f"📂 **{info['status']}**",
            }
            # Add all data keys as fields (up to limit)
            for k, v in data.items():
                if k not in ["type", "v_id", "logged_at"] and len(fields) < 20:
                    fields[k.title()] = f"`{v}`"

            embed = EmbedFactory.system("🔍 Generic Inspection", fields, ctx=ctx)
            await ctx.respond(embed=embed, ephemeral=True)

        else:
            embed = EmbedFactory.error(
                "Inspector Result",
                f"ID `{any_id}` could not be identified in memory or archives (last 3 days).",
                ctx=ctx,
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @dev.command(
        name="error_info",
        description="Retrieve detailed forensics for a specific error ID",
    )
    async def error_info(
        self,
        ctx: discord.ApplicationContext,
        error_id: discord.Option(str, "The error ID to look up"),
        date: discord.Option(str, "The date folder (YYYY-MM-DD)", default=None),
    ):
        """Loads error JSON files from disk to provide a post-mortem of a crash."""
        if not date:
            date = datetime.datetime.now().strftime("%Y-%m-%d")

        file_path = assets.get_path("logs", "errors", date, f"{error_id}.json")

        if not os.path.exists(file_path):
            embed = EmbedFactory.error(
                "Forensics Unavailable",
                f"No error log found for `{error_id}` on `{date}`.",
                ctx=ctx,
            )
            return await ctx.respond(embed=embed, ephemeral=True)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Truncate traceback to avoid embed limits
        tb = data.get("traceback", "No traceback available.")
        if len(tb) > 1000:
            tb = "..." + tb[-997:]

        embed = EmbedFactory.info(
            f"Error Forensics: {error_id}",
            f"**Type:** `{data['error_type']}`\n**Message:** `{data['error_message']}`",
            ctx=ctx,
        )

        context = data.get("context", {})
        embed.add_field(
            name="Context",
            value=(
                f"**Command:** `/{context.get('command')}`\n"
                f"**User:** {context.get('user_name')} (`{context.get('user_id')}`)\n"
                f"**Guild:** `{context.get('guild_id')}`"
            ),
            inline=False,
        )
        embed.add_field(name="Traceback", value=f"```py\n{tb}\n```", inline=False)
        embed.set_footer(text=f"Occurred: {data['timestamp']}")

        await ctx.respond(embed=embed, ephemeral=True)

    @dev.command(
        name="audit_log", description="View the most recent entries in an audit log"
    )
    async def audit_log(
        self,
        ctx: discord.ApplicationContext,
        guild_id: discord.Option(
            str, "Guild ID (leave empty for global log)", default=None
        ),
    ):
        """Tails the audit log files to check recent bot activities."""
        if guild_id:
            file_path = assets.get_path("logs", "guilds", guild_id, "audit.log")
            title = f"📜 Audit Log: Guild {guild_id}"
        else:
            file_path = assets.get_path("logs", "global", "audit.log")
            title = "📜 Global Audit Log"

        if not os.path.exists(file_path):
            embed = EmbedFactory.error(
                "Audit Missing", f"Log file at `{file_path}` does not exist.", ctx=ctx
            )
            return await ctx.respond(embed=embed, ephemeral=True)

        # Read last 15 lines efficiently
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            last_lines = lines[-15:]
            content = "".join(last_lines)

        embed = EmbedFactory.info(
            title,
            f"Last 15 log entries:\n```\n{content}\n```",
            ctx=ctx,
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @dev.command(name="reload", description="Hot-reload a bot extension")
    async def reload(
        self,
        ctx: discord.ApplicationContext,
        extension: discord.Option(str, "Name of the extension (e.g., fun, system)"),
    ):
        """Reloads a cog without restarting the entire bot process."""
        # Try different path variations for convenience
        paths = [
            f"cogs.{extension}",
        ]

        success = False
        last_error = "Extension not found."

        for path in paths:
            try:
                self.bot.reload_extension(path)
                success = True
                last_path = path
                break
            except commands.ExtensionNotLoaded:
                continue
            except Exception as e:
                last_error = str(e)
                break

        if success:
            embed = EmbedFactory.success(
                "Extension Reloaded",
                f"Successfully hot-swapped `{last_path}`.",
                ctx=ctx,
            )
        else:
            embed = EmbedFactory.error("Reload Failed", last_error, ctx=ctx)

        await ctx.respond(embed=embed, ephemeral=True)

    @dev.command(name="reload_config", description="Hot-reload the bot configuration")
    async def reload_config(self, ctx: discord.ApplicationContext):
        """Reloads the config.py module and updates common class variables."""
        try:
            import config as config_module
            importlib.reload(config_module)
            from config import config

            # Manually update classes that evaluated config at import time
            from utils.ui.embed_factory import EmbedFactory

            EmbedFactory.SUCCESS_COLOR = discord.Color(config.SUCCESS_COLOR)
            EmbedFactory.ERROR_COLOR = discord.Color(config.ERROR_COLOR)
            EmbedFactory.WARN_COLOR = discord.Color(config.WARN_COLOR)
            EmbedFactory.INFO_COLOR = discord.Color(config.DEFAULT_COLOR)

            embed = EmbedFactory.success(
                "Config Reloaded",
                "Successfully reloaded `config.py` and updated system constants.",
                ctx=ctx,
            )
        except Exception as e:
            embed = EmbedFactory.error("Config Reload Failed", str(e), ctx=ctx)

        await ctx.respond(embed=embed, ephemeral=True)

    @dev.command(
        name="cleanup_logs", description="Manual trigger maintenance to purge old logs"
    )
    async def cleanup_logs(self, ctx: discord.ApplicationContext):
        """Forces a cleanup task run to respect retention policies."""
        from config import config
        LOG_RETENTION_DAYS = config.LOG_RETENTION_DAYS

        now = time.time()
        retention_seconds = LOG_RETENTION_DAYS * 24 * 60 * 60
        count = 0

        # Crawl standard log directories
        log_categories = [["logs", "errors"], ["logs", "guilds"], ["logs", "global"]]

        for category in log_categories:
            base_dir = assets.get_path(*category)
            if not os.path.exists(base_dir):
                continue

            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                try:
                    if os.path.isdir(item_path):
                        # Attempt to parse date-named folders
                        try:
                            folder_date = datetime.datetime.strptime(item, "%Y-%m-%d")
                            if (
                                datetime.datetime.now() - folder_date
                            ).days > LOG_RETENTION_DAYS:
                                shutil.rmtree(item_path)
                                count += 1
                        except ValueError:
                            pass
                    elif os.path.getmtime(item_path) < (now - retention_seconds):
                        os.remove(item_path)
                        count += 1
                except Exception as e:
                    # Log failure but continue with other items
                    continue

        embed = EmbedFactory.success(
            "Maintenance Complete",
            f"Purged `{count}` stale log items based on {LOG_RETENTION_DAYS}-day retention.",
            ctx=ctx,
        )
        await ctx.respond(embed=embed, ephemeral=True)


# --- SYSTEM COG: ERROR EVENTS ---


class ErrorEvents(commands.Cog):
    """
    Global error dispatcher for the bot.
    Intercepts command executions and exceptions to route them through the UniversalErrorHandler.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.handler = UniversalErrorHandler()

    @commands.Cog.listener()
    async def on_application_command(self, ctx: discord.ApplicationContext):
        """Logs every slash command execution and enforces dynamic permissions."""
        self.handler.log_command(ctx)

        # Enforce dynamic permissions globally
        await perms.check_permissions(ctx)

    @commands.Cog.listener()
    async def on_application_command_error(
        self, ctx: discord.ApplicationContext, error: discord.DiscordException
    ):
        """Catches and processes all slash command errors."""
        await self.handler.handle_error(ctx, error)

    @commands.Cog.listener()
    async def on_interaction_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        """Catches and processes all component/modal interaction errors."""
        await self.handler.handle_ui_error(interaction, error)


# --- SYSTEM COG: FORENSIC LOGGING ---


class ForensicLogging(commands.Cog):
    """
    Itsumi's Forensic Logging Engine.
    Provides deep introspection into server events with persistent storage.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.description = "Deep forensics for message and member events."

    # --- Configuration ---

    log = discord.SlashCommandGroup("log", "Configure forensic logging")

    @log.command(name="channel", description="Set the destination for forensic logs")
    @has_level(PermissionLevel.ADMINISTRATOR)
    @option("channel", description="The channel to receive logs")
    async def log_channel(
        self, ctx: discord.ApplicationContext, channel: discord.TextChannel
    ):
        """Configures the primary channel for high-signal forensic logs."""
        await db.settings.set(
            "forensic_log_channel", str(channel.id), guild_id=ctx.guild.id
        )
        await ctx.respond(
            EmbedFactory.success(
                "Log Channel Updated",
                f"Forensic logs will now be sent to {channel.mention}.",
                ctx=ctx,
            )
        )

    @log.command(name="toggle", description="Enable or disable specific log events")
    @has_level(PermissionLevel.ADMINISTRATOR)
    @option(
        "event",
        description="The event to toggle",
        choices=["Messages", "Members", "Roles"],
    )
    @option("status", description="Enable or disable", choices=["Enable", "Disable"])
    async def log_toggle(
        self, ctx: discord.ApplicationContext, event: str, status: str
    ):
        """Toggles tracking for specific categories of server events."""
        key = f"log_enabled_{event.lower()}"
        value = "1" if status == "Enable" else "0"
        await db.settings.set(key, value, guild_id=ctx.guild.id)

        await ctx.respond(
            EmbedFactory.success(
                "Logging Updated",
                f"Forensic tracking for **{event}** has been **{status.lower()}d**.",
                ctx=ctx,
            )
        )

    # --- Listeners ---

    async def _get_log_channel(self, guild: discord.Guild):
        channel_id = await db.settings.get("forensic_log_channel", guild_id=guild.id)
        if not channel_id:
            return None
        return guild.get_channel(int(channel_id))

    async def _is_enabled(self, guild: discord.Guild, event_type: str):
        val = await db.settings.get(f"log_enabled_{event_type}", guild_id=guild.id)
        return val == "1"

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not await self._is_enabled(message.guild, "messages"):
            return

        channel = await self._get_log_channel(message.guild)
        if not channel:
            return

        # Record to DB
        await db.execute(
            "INSERT INTO message_logs (guild_id, channel_id, message_id, author_id, content, event_type) VALUES (?, ?, ?, ?, ?, ?)",
            (
                message.guild.id,
                message.channel.id,
                message.id,
                message.author.id,
                message.content,
                "DELETE",
            ),
        )

        # Build Forensic Embed
        v_id = f"flog-{str(uuid.uuid4())[:8]}"
        embed = EmbedFactory.system(
            title="🗑️ Message Deleted",
            fields={
                "User": f"{message.author.mention} (`{message.author.id}`)",
                "Channel": f"{message.channel.mention} (`{message.channel.id}`)",
                "Content": message.content
                or "*No text content (likely an embed or attachment)*",
                "Forensic ID": f"`{v_id}`",
            },
            color=discord.Color.red(),
        )

        registry.register_interaction(
            v_id, {"type": "FORENSIC_LOG", "event": "DELETE", "message_id": message.id}
        )

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        if not await self._is_enabled(before.guild, "messages"):
            return

        channel = await self._get_log_channel(before.guild)
        if not channel:
            return

        # Record to DB
        await db.execute(
            "INSERT INTO message_logs (guild_id, channel_id, message_id, author_id, content, event_type) VALUES (?, ?, ?, ?, ?, ?)",
            (
                before.guild.id,
                before.channel.id,
                before.id,
                before.author.id,
                before.content,
                "EDIT",
            ),
        )

        # Build Forensic Embed
        v_id = f"flog-{str(uuid.uuid4())[:8]}"
        embed = EmbedFactory.system(
            title="📝 Message Edited",
            fields={
                "User": f"{before.author.mention} (`{before.author.id}`)",
                "Channel": f"{before.channel.mention} (`{before.channel.id}`)",
                "Before": before.content or "*Empty*",
                "After": after.content or "*Empty*",
                "Forensic ID": f"`{v_id}`",
            },
            color=discord.Color.orange(),
        )

        registry.register_interaction(
            v_id, {"type": "FORENSIC_LOG", "event": "EDIT", "message_id": before.id}
        )

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not await self._is_enabled(member.guild, "members"):
            return

        channel = await self._get_log_channel(member.guild)
        if not channel:
            return

        v_id = f"flog-{str(uuid.uuid4())[:8]}"
        embed = EmbedFactory.system(
            title="📥 Member Joined",
            fields={
                "User": f"{member.mention} (`{member.id}`)",
                "Account Created": f"<t:{int(member.created_at.timestamp())}:R>",
                "Forensic ID": f"`{v_id}`",
            },
            color=discord.Color.green(),
        )

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not await self._is_enabled(member.guild, "members"):
            return

        channel = await self._get_log_channel(member.guild)
        if not channel:
            return

        v_id = f"flog-{str(uuid.uuid4())[:8]}"
        roles = [r.mention for r in member.roles if r.name != "@everyone"]

        embed = EmbedFactory.system(
            title="📤 Member Left",
            fields={
                "User": f"{member} (`{member.id}`)",
                "Joined At": f"<t:{int(member.joined_at.timestamp())}:R>"
                if member.joined_at
                else "*Unknown*",
                "Roles": ", ".join(roles) if roles else "None",
                "Forensic ID": f"`{v_id}`",
            },
            color=discord.Color.dark_gray(),
        )

        await channel.send(embed=embed)


# --- SYSTEM COG: SYSTEM STATS ---


class SystemStats(commands.Cog):
    """
    Performance monitoring and vital signs for Itsumi.
    Tracks latency, uptime, resource usage, and command traffic.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_metrics.start()
        self.sync_counts.start()

    def cog_unload(self):
        """Clean up tasks when the cog is unloaded."""
        self.update_metrics.cancel()
        self.sync_counts.cancel()

    # --- Background Loops ---

    @tasks.loop(seconds=10)
    async def update_metrics(self):
        """Periodically records bot latency to the tracker."""
        if self.bot.latency is not None:
            latency_ms = self.bot.latency * 1000
            if not math.isnan(latency_ms):
                tracker.record_latency(latency_ms)

    @tasks.loop(minutes=5)
    async def sync_counts(self):
        """Syncs guild and user counts to the metrics tracker."""
        run_id = registry.log_task_run("sync_counts", "STARTING")

        tracker.guild_count = len(self.bot.guilds)
        tracker.user_count = sum(g.member_count or 0 for g in self.bot.guilds)

        registry.log_task_run(
            "sync_counts",
            "COMPLETED",
            {"guilds": tracker.guild_count, "users": tracker.user_count},
        )

    @sync_counts.before_loop
    async def before_sync(self):
        """Wait for the bot to be fully connected before syncing counts."""
        await self.bot.wait_until_ready()

    # --- Commands ---

    @discord.slash_command(
        name="stats", description="Check Itsumi's vital signs and performance metrics"
    )
    @tracker.profile(name="System Stats")
    async def stats(self, ctx: discord.ApplicationContext):
        """Displays a real-time dashboard of bot performance and network scope."""
        uptime = tracker.uptime
        if math.isnan(uptime):
            uptime = 0.0

        uptime_seconds = int(uptime)
        h, r = divmod(uptime_seconds, 3600)
        m, s = divmod(r, 60)
        uptime_str = f"{h}h {m}m {s}s"

        spark = tracker.get_latency_sparkline()

        # Sharding Information
        shard_count = self.bot.shard_count or 1
        current_shard = ctx.guild.shard_id if ctx.guild else 0
        shard_latency = self.bot.latencies

        shard_info = f"**Shards:** `{shard_count}` total\n"
        if shard_count > 1:
            avg_shard_lat = sum(l for _, l in shard_latency) / len(shard_latency) * 1000
            shard_info += f"- **Current Shard:** `{current_shard}`\n"
            shard_info += f"- **Avg Shard Latency:** `{avg_shard_lat:.2f}ms`"

        # Slowest Commands Analysis
        slowest_list = sorted(
            tracker.command_timings, key=lambda x: x[1], reverse=True
        )[:5]
        slow_info = ""
        if slowest_list:
            slow_info = "### 🐌 Slowest Recent Commands\n"
            for name, dur in slowest_list:
                slow_info += f"- `{name}`: `{dur:.1f}ms`\n"

        body = (
            f"### 🚀 System Performance\n"
            f"- **Global Latency:** `{tracker.avg_latency:.2f}ms`\n"
            f"- **History:** `{spark}`\n"
            f"- **Uptime:** `{uptime_str}`\n"
            f"- **Memory:** `{tracker.memory_usage:.1f} MB`\n"
            f"- **CPU:** `{tracker.cpu_usage:.1f}%`\n\n"
            f"### 💎 Sharding\n{shard_info}\n\n"
            f"### 📥 Command Traffic\n"
            f"- **Executed:** `{tracker.command_counts}` commands\n\n"
            f"{slow_info}\n"
            f"### 🌐 Network Scope\n"
            f"- **Guilds:** `{tracker.guild_count}`\n"
            f"- **Users:** `{tracker.user_count:,}`"
        )

        container = create_fun_container(
            title="Itsumi Stats", body=body, view_id="stats-dash"
        )

        await ctx.respond(view=FunLayoutView(container))

    # --- Listeners ---

    @commands.Cog.listener()
    async def on_application_command(self, ctx):
        """Increments the command counter whenever a slash command is used."""
        tracker.increment_commands()


# --- SYSTEM COG: FORENSIC UI COMMANDS ---


class ForensicUI(commands.Cog):
    """
    Advanced introspection tools for Forensic Logs.
    Allows administrators to look up historical message edits and deletions.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.description = "Deep dive into server forensics and message history."

    # --- Message Context Commands ---

    @discord.message_command(name="Get Forensic IDs")
    @has_level(PermissionLevel.MODERATOR)
    async def get_msg_ids(
        self, ctx: discord.ApplicationContext, message: discord.Message
    ):
        """Extracts r-id and v-id from a message's content or embed footer."""
        r_id, v_id = None, None

        if message.content:
            match = re.search(r"r-id:\s*([a-zA-Z0-9-]+)", message.content)
            if match:
                r_id = match.group(1)
            match = re.search(r"v-id:\s*([a-zA-Z0-9-]+)", message.content)
            if match:
                v_id = match.group(1)

        for embed in message.embeds:
            if embed.footer and embed.footer.text:
                match = re.search(r"r-id:\s*([a-zA-Z0-9-]+)", embed.footer.text)
                if match:
                    r_id = match.group(1)
                match = re.search(r"v-id:\s*([a-zA-Z0-9-]+)", embed.footer.text)
                if match:
                    v_id = match.group(1)

        body = f"### 🆔 IDs for Message `{message.id}`\n"
        body += f"- **v-id (View ID):** `{v_id or 'None'}`\n"
        body += f"- **r-id (Response ID):** `{r_id or 'None'}`\n"

        container = create_fun_container(title="Extracted IDs", body=body)
        await ctx.respond(view=FunLayoutView(container), ephemeral=True)

    @discord.message_command(name="Edit Bot Message")
    @has_level(PermissionLevel.ADMINISTRATOR)
    async def edit_bot_message_ctx(
        self, ctx: discord.ApplicationContext, message: discord.Message
    ):
        """Opens an options menu to edit a bot message's content or embeds."""
        if message.author.id != self.bot.user.id:
            return await ctx.respond(
                embed=EmbedFactory.error(
                    "Invalid Target", "I can only edit my own messages.", ctx=ctx
                ),
                ephemeral=True,
            )

        from utils.ui.system import EditMessageOptionsView

        view = EditMessageOptionsView(message)
        container = create_fun_container(
            title="Edit Bot Message",
            body=f"Choose how you want to edit message `{message.id}`.",
        )
        await ctx.respond(
            view=FunLayoutView(container, original_view=view), ephemeral=True
        )

    @discord.message_command(name="Forensic Trace")
    @has_level(PermissionLevel.MODERATOR)
    async def forensic_trace_ctx(
        self, ctx: discord.ApplicationContext, message: discord.Message
    ):
        """Extracts IDs and launches the Forensic Trace Explorer."""
        r_id, v_id = None, None

        if message.content:
            match = re.search(r"r-id:\s*([a-zA-Z0-9-]+)", message.content)
            if match: r_id = match.group(1)
            match = re.search(r"v-id:\s*([a-zA-Z0-9-]+)", message.content)
            if match: v_id = match.group(1)

        for embed in message.embeds:
            if embed.footer and embed.footer.text:
                match = re.search(r"r-id:\s*([a-zA-Z0-9-]+)", embed.footer.text)
                if match: r_id = match.group(1)
                match = re.search(r"v-id:\s*([a-zA-Z0-9-]+)", embed.footer.text)
                if match: v_id = match.group(1)

        start_id = r_id or v_id
        if not start_id:
            return await ctx.respond(
                embed=EmbedFactory.error("No IDs Found", "This message does not contain any forensic IDs.", ctx=ctx),
                ephemeral=True
            )

        from utils.ui.forensics import ForensicTraceExplorer
        explorer = ForensicTraceExplorer(ctx, start_id)
        await explorer.initialize()
        container = await explorer.build_page()
        await ctx.respond(view=FunLayoutView(container, original_view=explorer), ephemeral=True)

    # --- Slash Commands ---

    forensic = discord.SlashCommandGroup("forensic", "Introspection and lookup tools")

    @forensic.command(name="trace", description="Trace the full chain of custody for any forensic ID")
    @has_level(PermissionLevel.MODERATOR)
    @option("id", description="The ID to trace (r-id, v-id, or e-id)", autocomplete=Developer.id_autocomplete)
    async def trace_slash(self, ctx: discord.ApplicationContext, id: str):
        """Launches the interactive Forensic Trace Explorer."""
        from utils.ui.forensics import ForensicTraceExplorer
        explorer = ForensicTraceExplorer(ctx, id.split(":")[-1].strip())
        await explorer.initialize()
        container = await explorer.build_page()
        await ctx.respond(view=FunLayoutView(container, original_view=explorer), ephemeral=True)

    @forensic.command(
        name="extract_ids", description="Extract forensic IDs using a message ID"
    )
    @has_level(PermissionLevel.MODERATOR)
    @option("message_id", description="The ID of the message in the current channel")
    async def extract_ids_slash(self, ctx: discord.ApplicationContext, message_id: str):
        try:
            msg = await ctx.channel.fetch_message(int(message_id))
            await self.get_msg_ids(ctx, msg)
        except:
            await ctx.respond(
                embed=EmbedFactory.error(
                    "Not Found", "Could not find that message in this channel.", ctx=ctx
                ),
                ephemeral=True,
            )

    @forensic.command(name="edit_message", description="Raw edit a bot message by ID")
    @has_level(PermissionLevel.ADMINISTRATOR)
    @option(
        "message_id", description="The ID of the bot's message in the current channel"
    )
    async def edit_message_slash(
        self, ctx: discord.ApplicationContext, message_id: str
    ):
        try:
            msg = await ctx.channel.fetch_message(int(message_id))
            await self.edit_bot_message_ctx(ctx, msg)
        except:
            await ctx.respond(
                embed=EmbedFactory.error(
                    "Not Found", "Could not find that message in this channel.", ctx=ctx
                ),
                ephemeral=True,
            )

    @forensic.command(name="lookup", description="Look up a forensic log entry by ID")
    @has_level(PermissionLevel.MODERATOR)
    @option("id", description="The Forensic ID (flog-...) or registry ID")
    async def forensic_lookup(self, ctx: discord.ApplicationContext, id: str):
        """Retrieves raw forensic data from the database or registry."""
        # Check Registry for metadata
        identity = await registry.identify(id)

        # Check Database if it's a message log
        # Try to find message history if we have a message ID from registry or if it's a raw msg ID
        msg_id = None
        if identity["type"] == "FORENSIC_LOG":
            msg_id = identity["data"].get("message_id")
        elif id.isdigit():
            msg_id = int(id)

        if msg_id:
            history = await db.fetchall(
                "SELECT * FROM message_logs WHERE message_id = ? ORDER BY timestamp DESC",
                (msg_id,),
            )

            if history:
                body = f"### 🕵️ Forensic History for `{msg_id}`\n"
                for entry in history:
                    body += (
                        f"- **{entry['event_type']}** | <t:{int(discord.utils.parse_time(entry['timestamp']).timestamp())}:R>\n"
                        f"  > {entry['content'][:100]}{'...' if len(entry['content']) > 100 else ''}\n"
                    )

                container = create_fun_container(
                    title=f"Forensic Lookup: {id}", body=body, view_id=f"f-lookup-{id}"
                )
                return await ctx.respond(view=FunLayoutView(container))

        # Fallback to general identity
        body = f"### 🔍 ID Identity\n- **Type:** `{identity['type']}`\n- **Status:** `{identity['status']}`\n"
        if "data" in identity:
            body += f"```json\n{json.dumps(identity['data'], indent=2)[:500]}\n```"

        container = create_fun_container(title=f"Forensic Lookup: {id}", body=body)
        await ctx.respond(view=FunLayoutView(container))

    @forensic.command(
        name="user", description="View forensic history for a specific user"
    )
    @has_level(PermissionLevel.MODERATOR)
    @option("user", description="The user to audit")
    async def forensic_user(
        self, ctx: discord.ApplicationContext, user: discord.Member
    ):
        """Aggregates all logged events for a specific user."""
        # Get message logs
        msg_logs = await db.fetchall(
            "SELECT event_type, timestamp FROM message_logs WHERE author_id = ? ORDER BY timestamp DESC LIMIT 5",
            (user.id,),
        )

        body = f"### 👤 Audit for {user.mention}\n"
        body += f"- **ID:** `{user.id}`\n"
        body += f"- **Joined:** <t:{int(user.joined_at.timestamp())}:R>\n\n"

        body += "#### 🕒 Recent Message Events\n"
        if msg_logs:
            for log in msg_logs:
                body += f"- **{log['event_type']}** | <t:{int(discord.utils.parse_time(log['timestamp']).timestamp())}:R>\n"
        else:
            body += "*No message events logged.*\n"

        container = create_fun_container(
            title=f"User Forensics: {user.name}", body=body
        )
        await ctx.respond(view=FunLayoutView(container))


def setup(bot):
    bot.add_cog(Developer(bot))
    bot.add_cog(ErrorEvents(bot))
    bot.add_cog(ForensicLogging(bot))
    bot.add_cog(SystemStats(bot))
    bot.add_cog(ForensicUI(bot))
