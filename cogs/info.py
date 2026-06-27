import sys
import discord
from discord.ext import commands
from config import config
from utils.ui.fun_layout import FunLayoutView, create_fun_container
from utils.ui.info import HelpMenu

class Help(commands.Cog):
    """
    The central navigation hub for the bot.
    Provides a dynamic help menu and detailed information about commands and the bot itself.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.description = "Get help with bot commands and information."

    def get_detailed_help(self, command: discord.ApplicationCommand | commands.Command):
        """Constructs a detailed UI container for a specific command."""
        name = command.qualified_name
        desc = (
            command.description if hasattr(command, "description") else command.help
        ) or "No description provided."

        body = f"## Help: {name}\n"
        body += f"{desc}\n\n"

        # --- Usage Generation ---
        if isinstance(command, commands.Command):
            prefix = self.bot.command_prefix
            if callable(prefix):
                prefix = "!"
            usage = f"{prefix}{name} {command.signature}"
        else:
            # Format slash command usage with options
            usage = f"/{name}"
            if hasattr(command, "options"):
                for opt in command.options:
                    usage += f" <{opt.name}>" if opt.required else f" [{opt.name}]"

        body += f"### Usage\n`{usage}`\n\n"

        # --- Permissions Analysis ---
        perms = []
        if (
            hasattr(command, "default_member_permissions")
            and command.default_member_permissions
        ):
            # Convert the bitmask to a human-readable list of capabilities
            p = discord.Permissions(command.default_member_permissions)
            perms = [cap.replace("_", " ").title() for cap, val in p if val]

        if perms:
            body += f"### Required Permissions\n{', '.join(perms)}\n"

        return create_fun_container(
            title=f"Command: {name}", 
            body=body, 
            view_id=f"help-detail-{name}"
        )

    # --- Slash Commands ---

    @discord.slash_command(
        name="help",
        description="List all available commands or get specific help",
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
    async def help_command(
        self,
        ctx: discord.ApplicationContext,
        query: discord.Option(str, "Search for a specific command", default=None),
    ):
        """Dispatches either the main help menu or a detailed command view."""
        if query:
            # Attempt to find the command in both slash and prefix registries
            command = self.bot.get_application_command(query) or self.bot.get_command(query)
            if not command:
                return await ctx.respond(
                    f"❌ Command `{query}` not found.", ephemeral=True
                )

            container = self.get_detailed_help(command)
            return await ctx.respond(view=FunLayoutView(container))

        # Initialize and build the interactive help menu
        menu = HelpMenu(ctx, self.bot)
        container = await menu.build_page()

        await ctx.respond(
            view=FunLayoutView(container, timeout=180, original_view=menu)
        )

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
        """Displays the bot's metadata, versioning, and technical stack."""
        body = (
            f"**{self.bot.user.name}**\n"
            f"A modern, chaotic, and high-infrastructure Discord bot.\n\n"
            f"**Version:** `{config.VERSION}`\n"
            f"**Developer:** `{config.AUTHOR}`\n"
            f"**Library:** `Pycord {discord.__version__}`\n"
            f"**Python:** `{sys.version.split(' ')[0]}`\n\n"
            "This bot utilizes **Components V2** and a custom **Universal Infrastructure**."
        )

        container = create_fun_container(
            title="✨ About Itsumi", body=body, view_id="about-page"
        )

        await ctx.respond(view=FunLayoutView(container))


def setup(bot):
    bot.add_cog(Help(bot))
