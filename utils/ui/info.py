import discord
from utils.ui.fun_layout import create_fun_container, FunLayoutView
from utils.ui.embed_factory import EmbedFactory

class PageJumpModal(discord.ui.Modal):
    def __init__(self, help_menu):
        super().__init__(title="Jump to Page")
        self.help_menu = help_menu
        self.add_item(
            discord.ui.InputText(
                label="Page Number",
                placeholder=f"Enter a number (1-{help_menu.max_pages})",
                min_length=1,
                max_length=len(str(help_menu.max_pages)),
            )
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            page = int(self.children[0].value)
            if 1 <= page <= self.help_menu.max_pages:
                self.help_menu.current_page = page - 1
                self.help_menu.update_button_states()
                container = await self.help_menu.build_page()
                from utils.ui.fun_layout import FunLayoutView

                await interaction.response.edit_message(
                    view=FunLayoutView(
                        container, timeout=180, original_view=self.help_menu
                    )
                )
            else:
                await interaction.response.send_message(
                    f"Invalid page number. Please enter between 1 and {self.help_menu.max_pages}.",
                    ephemeral=True,
                )
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number.", ephemeral=True
            )


class HelpDropdown(discord.ui.Select):
    def __init__(self, bot, cogs, user_or_id, help_menu):
        self.user_id = user_or_id if isinstance(user_or_id, int) else (user_or_id.id if user_or_id else None)
        self.help_menu = help_menu
        cog_emojis = {
            "Fun": "🎮",
            "Info": "ℹ️",
            "StatsCog": "📈",
            "Utility": "🛠️",
            "Moderation": "🛡️",
            "FunEmotes": "🎭",
            "FunAnime": "🌸",
            "FunGames": "🎲",
            "FunMisc": "🧩",
        }
        options = [
            discord.SelectOption(
                label="All Commands", description="Show everything I can do", emoji="🌐"
            )
        ]
        for name in sorted(cogs):
            cog = bot.get_cog(name)
            if cog:
                options.append(
                    discord.SelectOption(
                        label=name,
                        description=cog.description[:100] if hasattr(cog, "description") and cog.description else None,
                        emoji=cog_emojis.get(name),
                    )
                )

        super().__init__(
            placeholder="Jump to a category...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.user_id and interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "Not your menu!", ephemeral=True
            )

        selection = self.values[0]
        self.help_menu.cog_filter = None if selection == "All Commands" else selection
        self.help_menu.current_page = 0
        self.help_menu.update_filtered_commands()
        self.help_menu.update_button_states()

        container = await self.help_menu.build_page()
        from utils.ui.fun_layout import FunLayoutView

        await interaction.response.edit_message(
            view=FunLayoutView(container, timeout=180, original_view=self.help_menu)
        )


class HelpMenu(discord.ui.View):
    def __init__(self, ctx=None, bot=None, commands_per_page=6, user_id=None):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.bot = bot
        self.commands_per_page = commands_per_page
        self.current_page = 0
        self.cog_filter = None
        self.user_id = user_id or (ctx.author.id if ctx and ctx.author else None)

        self.valid_cog_names = []
        self.all_command_data = []

        if bot:
            # Filter cogs to avoid internal ones
            self.valid_cog_names = [
                name for name, cog in bot.cogs.items() if name != "ErrorHandlerCog"
            ]

            # Pre-cache all command data
            for cog_name in self.valid_cog_names:
                cog = bot.get_cog(cog_name)
                if not cog:
                    continue
                for cmd in cog.get_commands():
                    if isinstance(cmd, discord.SlashCommandGroup):
                        self.all_command_data.append((cmd, "group", cog_name))
                        for sub in cmd.subcommands:
                            self.all_command_data.append((sub, "sub", cog_name))
                    elif isinstance(cmd, discord.SlashCommand):
                        self.all_command_data.append((cmd, "slash", cog_name))
                    elif isinstance(cmd, discord.ext.commands.Command):
                        if isinstance(cmd, discord.ext.commands.Group):
                            self.all_command_data.append((cmd, "prefix_group", cog_name))
                            for sub in cmd.commands:
                                self.all_command_data.append((sub, "prefix_sub", cog_name))
                        else:
                            self.all_command_data.append((cmd, "prefix", cog_name))

        self.update_filtered_commands()

        # Row 1: Dropdown
        if bot and self.user_id:
            self.dropdown = HelpDropdown(bot, self.valid_cog_names, self.user_id, self)
            self.add_item(self.dropdown)

        # Row 2: Navigation
        self.update_button_states()

    def __get_init_args__(self):
        return {
            "commands_per_page": self.commands_per_page,
            "user_id": self.user_id,
        }

    def update_filtered_commands(self):
        if self.cog_filter:
            self.filtered_commands = [
                c for c in self.all_command_data if c[2] == self.cog_filter
            ]
        else:
            self.filtered_commands = self.all_command_data

        self.max_pages = max(
            1, (len(self.filtered_commands) - 1) // self.commands_per_page + 1
        )

    def update_button_states(self):
        self.prev_button.disabled = self.current_page == 0
        self.page_indicator.label = f"{self.current_page + 1} / {self.max_pages}"
        self.next_button.disabled = self.current_page >= self.max_pages - 1

    async def on_error(self, error, item, interaction):
        from utils.error_handler import UniversalErrorHandler
        await UniversalErrorHandler().handle_ui_error(interaction, error)

    def format_command_line(self, cmd, type):
        if type == "group" or type == "prefix_group":
            return (
                f"📁 **`/{cmd.name}`** (Group)"
                if type == "group"
                else f"📁 **`{self.bot.command_prefix}{cmd.name}`** (Group)"
            )
        elif type == "sub":
            return f"└─ `/{cmd.parent.name} {cmd.name}`"
        elif type == "prefix_sub":
            return f"└─ `{self.bot.command_prefix}{cmd.parent.name} {cmd.name}`"
        elif type == "slash":
            return f"🚀 **`/{cmd.name}`**"
        else:
            prefix = self.bot.command_prefix
            if callable(prefix):
                prefix = "!"
            return f"📄 **`{prefix}{cmd.name}`**"

    async def build_page(self):
        start = self.current_page * self.commands_per_page
        end = start + self.commands_per_page
        current_commands = self.filtered_commands[start:end]

        title = (
            f"🛠️ Itsumi Index: {self.cog_filter}"
            if self.cog_filter
            else "🛠️ Itsumi Command Index"
        )
        body = f"Showing {len(self.filtered_commands)} commands\n\n"

        if not current_commands:
            body += "*No commands found in this category.*"
        else:
            for cmd, type, _ in current_commands:
                line = self.format_command_line(cmd, type)
                desc = (
                    cmd.description if hasattr(cmd, "description") else cmd.help
                ) or "No description."
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                body += f"{line}\n-# {desc}\n"

        # Buttons and Dropdown are added "inside" the container by FunLayoutView
        container = create_fun_container(
            title=title,
            body=body,
            view_id=f"help-p{self.current_page + 1}",
        )
        return container

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.user_id and interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                EmbedFactory.toast("Not your menu!", interaction, success=False), ephemeral=True
            )
        self.current_page -= 1
        self.update_button_states()
        container = await self.build_page()
        from utils.ui.fun_layout import FunLayoutView

        await interaction.response.edit_message(
            view=FunLayoutView(container, timeout=180, original_view=self)
        )

    @discord.ui.button(label="1 / 1", style=discord.ButtonStyle.secondary)
    async def page_indicator(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.user_id and interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                EmbedFactory.toast("Not your menu!", interaction, success=False), ephemeral=True
            )
        await interaction.response.send_modal(PageJumpModal(self))

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.user_id and interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                EmbedFactory.toast("Not your menu!", interaction, success=False), ephemeral=True
            )
        self.current_page += 1
        self.update_button_states()
        container = await self.build_page()
        from utils.ui.fun_layout import FunLayoutView

        await interaction.response.edit_message(
            view=FunLayoutView(container, timeout=180, original_view=self)
        )
