import datetime
import json
import os

import discord
from discord.ext import commands

from utils.ui.embed_factory import EmbedFactory


class DevCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    dev = discord.SlashCommandGroup(
        "dev",
        "Developer only commands",
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

    @dev.command(name="error_info", description="Get detailed info about an error ID")
    async def error_info(
        self, ctx: discord.ApplicationContext, error_id: str, date: str = None
    ):
        if not date:
            date = datetime.datetime.now().strftime("%Y-%m-%d")

        file_path = f"logs/errors/{date}/{error_id}.json"

        if not os.path.exists(file_path):
            return await ctx.respond(
                embed=EmbedFactory.error(
                    "Not Found",
                    f"Error ID `{error_id}` not found for date `{date}`.",
                    ctx=ctx,
                ),
                ephemeral=True,
            )

        with open(file_path, "r") as f:
            data = json.load(f)

        # Truncate traceback if it's too long for an embed
        tb = data.get("traceback", "No traceback available.")
        if len(tb) > 1000:
            tb = tb[-1000:] + "\n... (truncated)"

        embed = EmbedFactory.info(
            f"Error Report: {error_id}",
            f"**Type:** `{data['error_type']}`\n**Message:** `{data['error_message']}`",
            ctx=ctx,
        )

        context = data.get("context", {})
        embed.add_field(
            name="Context",
            value=f"**Cmd:** /{context.get('command')}\n**User:** {context.get('user_name')} ({context.get('user_id')})\n**Guild:** {context.get('guild_id')}",
            inline=False,
        )
        embed.add_field(name="Traceback", value=f"```py\n{tb}\n```", inline=False)
        embed.set_footer(text=f"Timestamp: {data['timestamp']}")

        await ctx.respond(embed=embed, ephemeral=True)

    @dev.command(name="audit_log", description="Get the audit log for a specific date")
    async def audit_log(self, ctx: discord.ApplicationContext, date: str = None):
        if not date:
            date = datetime.datetime.now().strftime("%Y-%m-%d")

        file_path = f"logs/audit/{date}.log"

        if not os.path.exists(file_path):
            return await ctx.respond(
                embed=EmbedFactory.error(
                    "Not Found", f"Audit log for `{date}` not found.", ctx=ctx
                ),
                ephemeral=True,
            )

        # Read last 15 lines of audit log
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            last_lines = lines[-15:]
            content = "".join(last_lines)

        embed = EmbedFactory.info(
            f"Audit Log: {date}",
            f"Showing last 15 entries:\n```\n{content}\n```",
            ctx=ctx,
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @dev.command(name="reload", description="Reload a specific cog")
    async def reload(self, ctx: discord.ApplicationContext, cog_name: str):
        try:
            self.bot.reload_extension(f"cogs.{cog_name}")
            await ctx.respond(
                embed=EmbedFactory.success(
                    "Cog Reloaded", f"Successfully reloaded `cogs.{cog_name}`", ctx=ctx
                ),
                ephemeral=True,
            )
        except Exception as e:
            await ctx.respond(
                embed=EmbedFactory.error("Reload Failed", str(e), ctx=ctx),
                ephemeral=True,
            )

    @dev.command(
        name="cleanup_logs", description="Delete logs older than retention period"
    )
    async def cleanup_logs(self, ctx: discord.ApplicationContext):
        import time

        from config import LOG_RETENTION_DAYS

        now = time.time()
        retention_seconds = LOG_RETENTION_DAYS * 24 * 60 * 60
        count = 0

        # We need to crawl both error and audit logs
        for base_dir in ["logs/errors", "logs/audit"]:
            if not os.path.exists(base_dir):
                continue

            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                # If it's a directory (errors are by date)
                if os.path.isdir(item_path):
                    # For date directories, we check the directory itself or its content
                    # Simple check: if the directory name is a date older than X
                    try:
                        folder_date = datetime.datetime.strptime(item, "%Y-%m-%d")
                        if (
                            datetime.datetime.now() - folder_date
                        ).days > LOG_RETENTION_DAYS:
                            import shutil

                            shutil.rmtree(item_path)
                            count += 1
                    except:
                        pass
                else:
                    # For audit log files
                    if os.path.getmtime(item_path) < (now - retention_seconds):
                        os.remove(item_path)
                        count += 1

        await ctx.respond(
            embed=EmbedFactory.success(
                "Cleanup Complete", f"Removed `{count}` old log items.", ctx=ctx
            ),
            ephemeral=True,
        )


def setup(bot):
    bot.add_cog(DevCog(bot))
