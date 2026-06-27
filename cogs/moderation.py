import asyncio
import uuid
from datetime import timedelta
from typing import Optional

import discord
from discord import option
from discord.ext import commands
from pytimeparse.timeparse import timeparse

from utils.database import db
from utils.permissions import PermissionLevel, has_level
from utils.ui.embed_factory import EmbedFactory
from utils.ui.fun_layout import FunLayoutView, create_fun_container
from utils.audit import get_audit_logger
from utils.ui.moderation import VerificationPanelView, VerifyWizardView


class ModerationBase:
    async def log_action(
        self,
        ctx: discord.ApplicationContext,
        action: str,
        target: discord.Member | discord.User,
        reason: str,
        case_id: int,
        v_id: str,
        duration: Optional[str] = None,
    ):
        """Logs a moderation action to the configured mod-log channel and audit logs."""
        # 1. Internal Audit Logging (Surveillance)
        audit = get_audit_logger(ctx.guild.id)
        audit.info(f"MOD_ACTION | Type: {action} | Case: #{case_id} | Target: {target} ({target.id}) | Mod: {ctx.author} ({ctx.author.id}) | Reason: {reason} | v-id: {v_id}")

        # 2. Public (Moderator-facing) Discord Logging
        log_channel_id = await db.settings.get("mod_log_channel", guild_id=ctx.guild.id)
        if not log_channel_id:
            return

        log_channel = ctx.guild.get_channel(int(log_channel_id))
        if not log_channel:
            return

        color_map = {
            "Warn": discord.Color.yellow(),
            "Kick": discord.Color.orange(),
            "Timeout": discord.Color.blue(),
            "Ban": discord.Color.red(),
            "Unban": discord.Color.green(),
            "Purge": discord.Color.purple(),
            "Nuke": discord.Color.dark_grey(),
            "Case Edited": discord.Color.teal(),
            "Case Deleted": discord.Color.dark_red(),
        }

        fields = {
            "User": f"{target.mention} (`{target.id}`)",
            "Moderator": f"{ctx.author.mention} (`{ctx.author.id}`)",
            "Reason": reason,
        }
        if duration:
            fields["Duration"] = duration

        embed = EmbedFactory.system(
            title=f"{action} — Case #{case_id}",
            fields=fields,
            ctx=ctx,
            color=color_map.get(action, discord.Color.light_grey()),
        )

        try:
            return await log_channel.send(embed=embed)
        except:
            return None

    async def send_dm_notification(
        self,
        target: discord.Member | discord.User,
        action: str,
        guild_name: str,
        reason: str,
        case_id: int,
        duration: Optional[str] = None,
    ):
        """Sends a DM to the target user about the moderation action."""
        try:
            body = (
                f"You have been **{action.lower()}ed** in **{guild_name}**.\n\n"
                f"**Reason:** {reason}\n"
                f"**Case ID:** `#{case_id}`"
            )
            if duration:
                body += f"\n**Duration:** {duration}"

            container = create_fun_container(
                title=f"🛡️ Punishment: {action}",
                body=body,
                color=discord.Color.red(),
                view_id=f"dm-{case_id}",
            )
            await target.send(view=FunLayoutView(container))
        except:
            pass


class Moderation(commands.Cog, ModerationBase):
    """
    Server moderation tools including kicks, bans, warnings, timeouts, and cases.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.description = "Keep your server safe with advanced moderation tools."

    # --- Configuration ---

    @discord.slash_command(name="permissions", description="Launch the Overlord Security Operations Center")
    @has_level(PermissionLevel.ADMINISTRATOR)
    async def perms_panel(self, ctx: discord.ApplicationContext):
        from utils.ui.system import OverlordSecurityCenter
        soc = OverlordSecurityCenter(ctx)
        container = await soc.build_page()
        await ctx.respond(view=FunLayoutView(container, original_view=soc))

    # --- Punishment Commands ---

    @commands.slash_command(name="warn", description="Issue a formal warning to a member")
    @has_level(PermissionLevel.MODERATOR)
    @option("member", description="The member to warn")
    @option("reason", description="Reason for the warning")
    async def warn(self, ctx: discord.ApplicationContext, member: discord.Member, *, reason: str):
        if member.id == ctx.author.id:
            return await ctx.respond(embed=EmbedFactory.error("Self-Action", "You cannot warn yourself.", ctx=ctx), ephemeral=True)
        
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.respond(
                embed=EmbedFactory.error("Permission Denied", "You cannot warn someone with a higher or equal role.", ctx=ctx), ephemeral=True
            )

        v_id = f"mod-{str(uuid.uuid4())[:8]}"
        case_id = await db.moderation.create_case(
            "Warn",
            member.id,
            str(member),
            ctx.author.id,
            str(ctx.author),
            reason,
            v_id,
            guild_id=ctx.guild.id,
        )

        await self.send_dm_notification(member, "Warn", ctx.guild.name, reason, case_id)
        log_msg = await self.log_action(ctx, "Warn", member, reason, case_id, v_id)
        if log_msg:
            r_id = log_msg.embeds[0].footer.text.split("r-id: ")[-1]
            await db.moderation.update_log_meta(case_id, r_id, log_msg.id, guild_id=ctx.guild.id)

        embed = EmbedFactory.system(
            title=f"Warning — Case #{case_id}",
            fields={
                "User": f"{member.mention} (`{member.id}`)",
                "Moderator": f"{ctx.author.mention} (`{ctx.author.id}`)",
                "Reason": reason,
            },
            ctx=ctx,
            color=discord.Color.yellow(),
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(name="kick", description="Remove a member from the server")
    @has_level(PermissionLevel.MODERATOR)
    @option("member", description="The member to kick")
    @option("reason", description="Reason for the kick")
    async def kick(self, ctx: discord.ApplicationContext, member: discord.Member, *, reason: str):
        """Kicks a member and notifies them via DM."""
        if member.id == ctx.author.id:
            return await ctx.respond(embed=EmbedFactory.error("Self-Action", "You cannot kick yourself.", ctx=ctx), ephemeral=True)
            
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.respond(
                embed=EmbedFactory.error("Permission Denied", "You cannot kick someone with a higher or equal role.", ctx=ctx), ephemeral=True
            )

        v_id = f"mod-{str(uuid.uuid4())[:8]}"
        case_id = await db.moderation.create_case(
            "Kick",
            member.id,
            str(member),
            ctx.author.id,
            str(ctx.author),
            reason,
            v_id,
            guild_id=ctx.guild.id,
        )

        await self.send_dm_notification(member, "Kick", ctx.guild.name, reason, case_id)
        await member.kick(reason=f"[Case #{case_id}] {reason}")
        log_msg = await self.log_action(ctx, "Kick", member, reason, case_id, v_id)
        if log_msg:
            r_id = log_msg.embeds[0].footer.text.split("r-id: ")[-1]
            await db.moderation.update_log_meta(case_id, r_id, log_msg.id, guild_id=ctx.guild.id)

        embed = EmbedFactory.system(
            title=f"Kick — Case #{case_id}",
            fields={
                "User": f"{member.mention} (`{member.id}`)",
                "Moderator": f"{ctx.author.mention} (`{ctx.author.id}`)",
                "Reason": reason,
            },
            ctx=ctx,
            color=discord.Color.orange(),
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(name="ban", description="Permanently or temporarily ban a user")
    @has_level(PermissionLevel.MODERATOR)
    @option("user", description="The user to ban (ID or Mention)")
    @option("reason", description="Reason for the ban")
    @option("duration", description="Duration (e.g., 1d, 1h). Leave empty for permanent.")
    async def ban(
        self,
        ctx: discord.ApplicationContext,
        user: discord.User,
        *,
        reason: str,
        duration: str = None,
    ):
        """Bans a user and optionally schedules an automatic unban."""
        if user.id == ctx.author.id:
            return await ctx.respond(embed=EmbedFactory.error("Self-Action", "You cannot ban yourself.", ctx=ctx), ephemeral=True)

        member = ctx.guild.get_member(user.id)
        if member:
            if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
                return await ctx.respond(
                    embed=EmbedFactory.error("Permission Denied", "You cannot ban someone with a higher or equal role.", ctx=ctx),
                    ephemeral=True,
                )

        parsed_duration = timeparse(duration) if duration else None
        v_id = f"mod-{str(uuid.uuid4())[:8]}"
        case_id = await db.moderation.create_case(
            "Ban",
            user.id,
            str(user),
            ctx.author.id,
            str(ctx.author),
            reason,
            v_id,
            duration=duration or "Permanent",
            guild_id=ctx.guild.id,
        )

        await self.send_dm_notification(user, "Ban", ctx.guild.name, reason, case_id, duration)
        await ctx.guild.ban(user, reason=f"[Case #{case_id}] {reason}")
        log_msg = await self.log_action(ctx, "Ban", user, reason, case_id, v_id, duration)
        if log_msg:
            r_id = log_msg.embeds[0].footer.text.split("r-id: ")[-1]
            await db.moderation.update_log_meta(case_id, r_id, log_msg.id, guild_id=ctx.guild.id)

        await ctx.respond(embed=EmbedFactory.toast(f"User {user} banned. (Case #{case_id})", ctx), ephemeral=True)

        if parsed_duration:
            await asyncio.sleep(parsed_duration)
            try:
                await ctx.guild.unban(user, reason=f"Temporary ban expired (Case #{case_id})")
                await self.log_action(
                    ctx, "Unban", user, "Temporary ban expired", case_id, "auto-unban"
                )
            except:
                pass

    @commands.slash_command(name="timeout", description="Restrict a member's ability to communicate")
    @has_level(PermissionLevel.MODERATOR)
    @option("member", description="The member to timeout")
    @option("duration", description="Duration (e.g., 10m, 1h, 1d)")
    @option("reason", description="Reason for the timeout")
    async def timeout(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member,
        duration: str,
        *,
        reason: str,
    ):
        """Places a member in timeout for a specified duration."""
        if member.id == ctx.author.id:
            return await ctx.respond(embed=EmbedFactory.error("Self-Action", "You cannot timeout yourself.", ctx=ctx), ephemeral=True)
            
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.respond(
                embed=EmbedFactory.error("Permission Denied", "You cannot timeout someone with a higher or equal role.", ctx=ctx),
                ephemeral=True,
            )

        seconds = timeparse(duration)
        if not seconds:
            return await ctx.respond(embed=EmbedFactory.error("Invalid Duration", "The duration format provided is invalid.", ctx=ctx), ephemeral=True)

        v_id = f"mod-{str(uuid.uuid4())[:8]}"
        case_id = await db.moderation.create_case(
            "Timeout",
            member.id,
            str(member),
            ctx.author.id,
            str(ctx.author),
            reason,
            v_id,
            duration=duration,
            guild_id=ctx.guild.id,
        )

        until = discord.utils.utcnow() + timedelta(seconds=seconds)
        await member.timeout(until, reason=f"[Case #{case_id}] {reason}")
        await self.send_dm_notification(member, "Timeout", ctx.guild.name, reason, case_id, duration)
        log_msg = await self.log_action(ctx, "Timeout", member, reason, case_id, v_id, duration)
        if log_msg:
            r_id = log_msg.embeds[0].footer.text.split("r-id: ")[-1]
            await db.moderation.update_log_meta(case_id, r_id, log_msg.id, guild_id=ctx.guild.id)

        embed = EmbedFactory.system(
            title=f"Timeout — Case #{case_id}",
            fields={
                "User": f"{member.mention} (`{member.id}`)",
                "Moderator": f"{ctx.author.mention} (`{ctx.author.id}`)",
                "Reason": reason,
                "Duration": duration,
            },
            ctx=ctx,
            color=discord.Color.blue(),
        )
        await ctx.respond(embed=embed)

    # --- Utility & Config Commands ---

    @commands.slash_command(name="modlog", description="Configure the moderation log channel")
    @has_level(PermissionLevel.ADMINISTRATOR)
    @option("channel", description="The channel to receive moderation logs")
    async def set_modlog(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        """Sets the channel where moderation action summaries are sent."""
        await db.settings.set("mod_log_channel", str(channel.id), guild_id=ctx.guild.id)
        embed = EmbedFactory.success(
            "Mod-Log Configured",
            f"Successfully set the moderation log channel to {channel.mention}.",
            ctx=ctx,
        )
        await ctx.respond(embed=embed)

    case = discord.SlashCommandGroup("case", "Manage moderation cases")

    @case.command(name="lookup", description="Retrieve details for a moderation case")
    @has_level(PermissionLevel.MODERATOR)
    @option("case_id", description="The numerical ID of the case")
    async def case_lookup(self, ctx: discord.ApplicationContext, case_id: int):
        """Fetches historical punishment data from the database."""
        row = await db.moderation.get_case(case_id, guild_id=ctx.guild.id)

        if not row:
            return await ctx.respond(embed=EmbedFactory.error("Not Found", f"Case `#{case_id}` not found.", ctx=ctx), ephemeral=True)

        fields = {
            "Type": row["type"],
            "User": f"<@{row['user_id']}> (`{row['user_id']}`)",
            "Moderator": f"<@{row['moderator_id']}> (`{row['moderator_id']}`)",
            "Reason": row["reason"],
            "v-id": f"`{row['v_id']}`",
        }
        if row["duration"]:
            fields["Duration"] = row["duration"]

        embed = EmbedFactory.system(
            title=f"📋 Case Lookup: #{case_id}",
            fields=fields,
            ctx=ctx,
            color=discord.Color.blue(),
        )
        await ctx.respond(embed=embed)

    @case.command(name="edit", description="Update the reason for a moderation case")
    @has_level(PermissionLevel.MODERATOR)
    @option("case_id", description="The numerical ID of the case")
    @option("reason", description="The new reason for the case")
    async def case_edit(self, ctx: discord.ApplicationContext, case_id: int, reason: str):
        """Updates the reason of an existing moderation case."""
        row = await db.moderation.get_case(case_id, guild_id=ctx.guild.id)

        if not row:
            return await ctx.respond(embed=EmbedFactory.error("Not Found", f"Case `#{case_id}` not found.", ctx=ctx), ephemeral=True)

        old_reason = row["reason"]
        await db.moderation.update_reason(case_id, reason, guild_id=ctx.guild.id)

        # Log the edit
        user = self.bot.get_user(row["user_id"]) or await self.bot.fetch_user(row["user_id"])
        await self.log_action(
            ctx, 
            "Case Edited", 
            user, 
            f"**Old Reason:** {old_reason}\n**New Reason:** {reason}", 
            case_id, 
            row["v_id"]
        )

        embed = EmbedFactory.success(
            "Case Updated",
            f"Case `#{case_id}` reason has been updated.\n\n"
            f"**New Reason:** {reason}",
            ctx=ctx
        )
        await ctx.respond(embed=embed)

    @case.command(name="delete", description="Permanently remove a moderation case")
    @has_level(PermissionLevel.MODERATOR)
    @option("case_id", description="The numerical ID of the case")
    async def case_delete(self, ctx: discord.ApplicationContext, case_id: int):
        """Removes a case record from the database and deletes the modlog message."""
        row = await db.moderation.get_case(case_id, guild_id=ctx.guild.id)

        if not row:
            return await ctx.respond(embed=EmbedFactory.error("Not Found", f"Case `#{case_id}` not found.", ctx=ctx), ephemeral=True)

        # 1. Attempt to delete the modlog message
        log_channel_id = await db.settings.get("mod_log_channel", guild_id=ctx.guild.id)
        if log_channel_id:
            log_channel = ctx.guild.get_channel(int(log_channel_id))
            if log_channel:
                deleted_msg = False
                # Try direct deletion if we have the ID
                if row["log_message_id"]:
                    try:
                        msg = await log_channel.fetch_message(row["log_message_id"])
                        await msg.delete()
                        deleted_msg = True
                    except:
                        pass
                
                # Fallback: Search by r_id if not deleted yet (as requested)
                if not deleted_msg and row["r_id"]:
                    try:
                        async for message in log_channel.history(limit=100):
                            if message.embeds and message.embeds[0].footer:
                                if row["r_id"] in message.embeds[0].footer.text:
                                    await message.delete()
                                    deleted_msg = True
                                    break
                    except:
                        pass

        await db.execute("DELETE FROM cases WHERE id = ? AND guild_id = ?", (case_id, ctx.guild.id))

        # Log the deletion in audit logs
        user = self.bot.get_user(row["user_id"]) or await self.bot.fetch_user(row["user_id"])
        await self.log_action(
            ctx, 
            "Case Deleted", 
            user, 
            f"Case #{case_id} deleted by {ctx.author}. (Original Reason: {row['reason']})", 
            case_id, 
            row["v_id"]
        )

        embed = EmbedFactory.success(
            "Case Deleted",
            f"Case `#{case_id}` has been permanently removed from the records.\n"
            f"The associated modlog message has also been cleaned up.",
            ctx=ctx
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(name="purge", description="Delete multiple messages with advanced filters")
    @has_level(PermissionLevel.MODERATOR)
    @option("amount", description="Number of messages to scan (max 100)", min_value=1, max_value=100)
    @option("user", description="Only purge messages from this user", required=False)
    @option("contains", description="Only purge messages containing this text", required=False)
    @option("regex", description="Only purge messages matching this regex pattern", required=False)
    @option("has_attachment", description="Only purge messages with attachments", choices=["Yes", "No"], required=False)
    @option("has_link", description="Only purge messages containing links", choices=["Yes", "No"], required=False)
    @option("is_bot", description="Only purge messages from bots", choices=["Yes", "No"], required=False)
    @option("starts_with", description="Only purge messages starting with this text", required=False)
    @option("ends_with", description="Only purge messages ending with this text", required=False)
    async def purge(
        self,
        ctx: discord.ApplicationContext,
        amount: int,
        user: discord.Member = None,
        contains: str = None,
        regex: str = None,
        has_attachment: str = None,
        has_link: str = None,
        is_bot: str = None,
        starts_with: str = None,
        ends_with: str = None,
    ):
        """Mass-deletes messages based on complex criteria."""
        await ctx.defer(ephemeral=True)

        import re
        link_regex = r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"

        def check(m: discord.Message):
            if user and m.author.id != user.id:
                return False
            if contains and contains.lower() not in m.content.lower():
                return False
            if regex:
                try:
                    if not re.search(regex, m.content):
                        return False
                except:
                    return False # Invalid regex
            if has_attachment:
                has_any = len(m.attachments) > 0
                if (has_attachment == "Yes" and not has_any) or (has_attachment == "No" and has_any):
                    return False
            if has_link:
                has_any = re.search(link_regex, m.content) is not None
                if (has_link == "Yes" and not has_any) or (has_link == "No" and has_any):
                    return False
            if is_bot:
                if (is_bot == "Yes" and not m.author.bot) or (is_bot == "No" and m.author.bot):
                    return False
            if starts_with and not m.content.lower().startswith(starts_with.lower()):
                return False
            if ends_with and not m.content.lower().endswith(ends_with.lower()):
                return False
            return True

        try:
            deleted = await ctx.channel.purge(limit=amount, check=check)
            count = len(deleted)
            
            # Create a case for the purge action
            v_id = f"mod-{str(uuid.uuid4())[:8]}"
            reason = f"Purged {count} messages with filters."
            case_id = await db.moderation.create_case(
                "Purge",
                ctx.channel.id,
                f"#{ctx.channel.name}",
                ctx.author.id,
                str(ctx.author),
                reason,
                v_id,
                guild_id=ctx.guild.id,
            )

            # Use a dummy user for log_action compatibility (since target is a channel)
            class DummyTarget:
                def __init__(self, channel):
                    self.mention = channel.mention
                    self.id = channel.id
                def __str__(self):
                    return f"#{channel.name}"

            log_msg = await self.log_action(ctx, "Purge", DummyTarget(ctx.channel), reason, case_id, v_id)
            if log_msg:
                r_id = log_msg.embeds[0].footer.text.split("r-id: ")[-1]
                await db.moderation.update_log_meta(case_id, r_id, log_msg.id, guild_id=ctx.guild.id)

            embed = EmbedFactory.success(
                "Purge Complete",
                f"Successfully deleted **{count}** messages from this channel.\n\n"
                f"**Filters Applied:**\n"
                f"- User: {user.mention if user else 'Any'}\n"
                f"- Contains: `{contains or 'None'}`\n"
                f"- Has Link: `{has_link or 'Any'}`",
                ctx=ctx
            )
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(embed=EmbedFactory.error("Purge Failed", str(e), ctx=ctx), ephemeral=True)

    @commands.slash_command(name="hardpurge", description="Completely reset this channel (clones and deletes original)")
    @has_level(PermissionLevel.ADMINISTRATOR)
    async def hard_purge(self, ctx: discord.ApplicationContext):
        """Advanced 'nuke' command that recreates the channel from scratch."""
        await ctx.defer(ephemeral=True)

        try:
            channel = ctx.channel
            position = channel.position
            
            # 1. Clone the channel
            new_channel = await channel.clone(reason=f"Hardpurge by {ctx.author}")
            
            # 2. Re-position it
            await new_channel.edit(position=position)
            
            # 3. Create a case for the log
            v_id = f"mod-{str(uuid.uuid4())[:8]}"
            reason = "Channel nuked (hardpurge)."
            case_id = await db.moderation.create_case(
                "Nuke",
                channel.id,
                f"#{channel.name}",
                ctx.author.id,
                str(ctx.author),
                reason,
                v_id,
                guild_id=ctx.guild.id,
            )

            # Log the action
            class DummyTarget:
                def __init__(self, channel):
                    self.mention = f"#{channel.name}"
                    self.id = channel.id
                def __str__(self):
                    return f"#{channel.name}"

            log_msg = await self.log_action(ctx, "Nuke", DummyTarget(channel), reason, case_id, v_id)
            if log_msg:
                r_id = log_msg.embeds[0].footer.text.split("r-id: ")[-1]
                await db.moderation.update_log_meta(case_id, r_id, log_msg.id, guild_id=ctx.guild.id)

            # 4. Delete the old channel
            await channel.delete(reason=f"Hardpurge by {ctx.author}")

            # 5. Send confirmation in the NEW channel
            embed = EmbedFactory.success(
                "Channel Reset",
                f"This channel has been completely reset by {ctx.author.mention}.\n"
                f"All previous messages have been permanently removed.",
                ctx=ctx
            )
            await new_channel.send(embed=embed)

        except Exception as e:
            await ctx.respond(embed=EmbedFactory.error("Hardpurge Failed", str(e), ctx=ctx), ephemeral=True)


class Verification(commands.Cog):
    """
    Advanced server protection and verification tools.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.description = "Configurable, multi-mode verification system."

    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent view once the bot is ready
        self.bot.add_view(VerificationPanelView())

    verify = discord.SlashCommandGroup("verify", "Advanced server protection and verification tools")

    @verify.command(
        name="panel", 
        description="Open the advanced Verification System dashboard"
    )
    @has_level(PermissionLevel.ADMINISTRATOR)
    async def verify_panel(self, ctx: discord.ApplicationContext):
        """Launches the interactive GUI wizard for configuring verification."""
        wizard = VerifyWizardView(ctx)
        await wizard.initialize()
        container = await wizard.build_current_step()
        await ctx.respond(view=FunLayoutView(container, original_view=wizard))


def setup(bot):
    bot.add_cog(Moderation(bot))
    bot.add_cog(Verification(bot))
