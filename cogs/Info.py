import sys

import discord
from discord.ext import commands

import config
from utils.ui.embed_factory import EmbedFactory
from utils.ui.fun_layout import FunLayoutView, create_fun_container


class HelpDropdown(discord.ui.Select):
    def __init__(self, bot: commands.Bot, cogs: list):
        options = []
        for cog_name in cogs:
            cog = bot.get_cog(cog_name)
            if cog:
                # Get a clean name and description
                name = cog_name
                description = cog.description or f"Commands related to {name}"
                options.append(
                    discord.SelectOption(label=name, description=description[:100])
                )

        super().__init__(
            placeholder="Select a category to see commands...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="help_dropdown",
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        cog_name = self.values[0]
        cog = self.bot.get_cog(cog_name)

        if not cog:
            return await interaction.response.send_message(
                "Cog not found.", ephemeral=True
            )

        is_owner = await self.bot.is_owner(interaction.user)

        def can_see(cmd):
            # Check for hidden attribute
            if getattr(cmd, "hidden", False):
                return False

            # Check for owner-only checks
            for check in getattr(cmd, "checks", []):
                # Pycord's is_owner check usually shows up as a predicate with 'is_owner' in its string representation
                if "is_owner" in str(check):
                    return is_owner

            # Check for default member permissions (Slash commands)
            if (
                hasattr(cmd, "default_member_permissions")
                and cmd.default_member_permissions
            ):
                if interaction.guild:
                    user_perms = interaction.channel.permissions_for(interaction.user)
                    # Check if user has ALL of the required permissions in the bitmask
                    if not (
                        user_perms.value & cmd.default_member_permissions
                        == cmd.default_member_permissions
                    ):
                        return False

            return True

        # Build the command list for this cog
        commands_text = ""

        # Handle all types of commands in the cog
        # Application Commands (Slash, User, Message)
        for command in cog.get_commands():
            if not can_see(command):
                continue

            if isinstance(command, discord.SlashCommandGroup):
                for sub in command.subcommands:
                    if can_see(sub):
                        commands_text += (
                            f"- `/{command.name} {sub.name}`: {sub.description}\n"
                        )
            elif isinstance(command, discord.SlashCommand):
                commands_text += f"- `/{command.name}`: {command.description}\n"

        # Handle Prefix Commands (discord.ext.commands.Command)
        prefix = self.bot.command_prefix
        if callable(prefix):
            # If prefix is a function, we'll just use a dot as a placeholder for the help menu
            prefix = "."

        # commands.Cog.get_commands() only returns application commands in modern Pycord if they are defined as such.
        # Prefix commands are in cog.get_commands() too, but we need to check the type.
        for command in cog.get_commands():
            if isinstance(command, commands.Command):
                if not can_see(command):
                    continue
                commands_text += f"- `{prefix}{command.qualified_name}`: {command.help or 'No description.'}\n"

        if not commands_text:
            commands_text = (
                "*You don't have permission to see any commands in this category.*"
            )

        container = create_fun_container(
            title=f"📖 {cog_name} Help",
            body=f"### Available Commands\n{commands_text}",
            view_id=f"help-{cog_name.lower()}",
        )

        # In Components V2, we add the ActionRow directly to the container
        dropdown = HelpDropdown(
            self.bot, [c for c in self.bot.cogs if c != "ErrorHandlerCog"]
        )
        row = discord.ui.ActionRow(dropdown)
        container.add_item(row)

        await interaction.response.edit_message(view=FunLayoutView(container))


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.description = "Get help with bot commands"

    @discord.slash_command(
        name="help",
        description="List all available commands and categories",
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
    async def help_command(self, ctx: discord.ApplicationContext):
        # Filter out internal/hidden cogs
        valid_cogs = [
            name for name, cog in self.bot.cogs.items() if name != "ErrorHandlerCog"
        ]

        container = create_fun_container(
            title="Bot Help Menu",
            body="Welcome to the help menu! Select a category from the dropdown below to see available commands.",
            view_id="help-main",
        )

        # In Components V2, we add the ActionRow directly to the container
        dropdown = HelpDropdown(self.bot, valid_cogs)
        row = discord.ui.ActionRow(dropdown)
        container.add_item(row)

        view = FunLayoutView(container)
        await ctx.respond(view=view)

    @discord.slash_command(
        name="about",
        description="Information about the bot and its development",
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
    async def about_command(self, ctx: discord.ApplicationContext):
        body = (
            f"**{self.bot.user.name}**\n"
            f"A modern, chaotic, and high-infrastructure Discord bot.\n\n"
            f"**Version:** `{config.VERSION}`\n"
            f"**Developer:** `{config.AUTHOR}`\n"
            f"**Library:** `Pycord {discord.__version__}`\n"
            f"**Python:** `{sys.version.split(' ')[0]}`\n\n"
            "This bot utilizes **Components V2** and a custom **Universal Infrastructure** for logging, error management, and UI standardization."
        )

        container = create_fun_container(
            title="✨ About Itsumi", body=body, view_id="about-page"
        )

        await ctx.respond(view=FunLayoutView(container))


def setup(bot):
    bot.add_cog(HelpCog(bot))
