import json
import discord
from discord import option
from discord.ext import commands

from utils.database import db
from utils.ui.embed_factory import EmbedFactory
from utils.ui.fun_layout import FunLayoutView, create_fun_container
from utils.permissions import PermissionLevel, has_level
from utils.ui.utility import TagControlPanel, TagCreateModal


class Avatar(commands.Cog):
    """
    User utility for viewing and downloading profile pictures.
    Supports both slash commands and user context menu interactions.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.description = "View user avatars with ease."

    def build_avatar_container(
        self, user: discord.User | discord.Member
    ) -> discord.ui.Container:
        """Constructs the UI container for displaying an avatar and its download links."""
        title = f"✨ {user.display_name}'s Avatar"
        body = f"View and download the avatar for **{user}**."

        # Generate markdown links for multiple image formats
        formats = ["png", "jpg", "webp"]
        links = []
        for fmt in formats:
            url = user.display_avatar.with_format(fmt).url
            links.append(f"[**{fmt.upper()}**]({url})")

        body += f"\n\n**Downloads:** {' | '.join(links)}"

        container = create_fun_container(
            title=title,
            body=body,
            image_url=user.display_avatar.url,
            view_id=f"avatar-{user.id}",
        )
        return container

    # --- Slash Commands ---

    @discord.slash_command(
        name="avatar",
        description="Display a user's avatar.",
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
    @discord.option("user", description="The user to view (defaults to you)", default=None)
    async def avatar_slash(
        self, ctx: discord.ApplicationContext, user: discord.User = None
    ):
        """Standard slash command to fetch and show a user's avatar."""
        user = user or ctx.author
        container = self.build_avatar_container(user)
        await ctx.respond(view=FunLayoutView(container))

    # --- Context Menu Commands ---

    @discord.user_command(
        name="View Avatar",
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
    async def avatar_user(self, ctx: discord.ApplicationContext, user: discord.User):
        """Context menu shortcut to quickly view a user's avatar."""
        container = self.build_avatar_container(user)
        await ctx.respond(view=FunLayoutView(container))


class Tags(commands.Cog):
    """
    Advanced server-specific Tag system.
    Allows creating, managing, and invoking custom text snippets.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.description = "Custom server tags for quick information retrieval."

    # --- Autocomplete ---

    async def tag_autocomplete(self, ctx: discord.AutocompleteContext):
        """Fetches tag names matching the user's input using fuzzy logic."""
        from rapidfuzz import process, fuzz
        
        tag_names = await db.tags.list_names(ctx.interaction.guild_id)
        if not ctx.value:
            return sorted(tag_names)[:25]
        
        # Get top 25 fuzzy matches
        matches = process.extract(
            ctx.value, 
            tag_names, 
            scorer=fuzz.WRatio, 
            limit=25
        )
        return [match[0] for match in matches if match[1] > 40]

    # --- Rendering Engine ---

    def render_tag(self, tag_data: dict):
        """Transforms database tag records into Discord-ready responses."""
        if not tag_data["is_embed"]:
            return {"content": tag_data["content"], "embed": None}

        try:
            data = json.loads(tag_data["content"])
            description = data.get("description", "")
            title = data.get("title")
            color_hex = data.get("color")

            color = discord.Color.blue()
            if color_hex:
                try:
                    color = discord.Color(int(color_hex.lstrip("#"), 16))
                except: pass

            embed = EmbedFactory.custom(
                title=title,
                description=description,
                color=color,
                image_url=tag_data["thumbnail_url"]
            )

            return {"content": None, "embed": embed}
        except Exception as e:
            return {"content": f"⚠️ **Tag Render Error:** {e}\n\nRaw Content: {tag_data['content']}", "embed": None}

    # --- Tag Command Group ---

    tag = discord.SlashCommandGroup("tag", "Custom server tag commands")

    @tag.command(name="get", description="Invoke a custom server tag")
    @option("name", description="The name of the tag to display", autocomplete=tag_autocomplete)
    async def tag_get(self, ctx: discord.ApplicationContext, name: str):
        """Retrieves and sends the content of a saved tag."""
        tag = await db.tags.get(name, guild_id=ctx.guild_id)
        if not tag:
            return await ctx.respond(embed=EmbedFactory.error("Not Found", f"Tag `{name}` not found.", ctx=ctx), ephemeral=True)

        from utils.registry import registry
        r_id = registry.register_response("TAG", {"name": name}, interaction=ctx)

        rendered = self.render_tag(tag)
        footer_text = f"r-id: {r_id}"

        if rendered["embed"]:
            rendered["embed"].set_footer(text=footer_text)
            await ctx.respond(embed=rendered["embed"])
        else:
            content = rendered["content"]
            content += f"\n\n-# {footer_text}"
            await ctx.respond(content)

    @tag.command(name="list", description="Open the Tag Control Panel")
    async def tag_panel(self, ctx: discord.ApplicationContext):
        """Opens the interactive management interface for server tags."""
        panel = TagControlPanel(ctx, self.bot)
        container = await panel.build_page()
        await ctx.respond(view=FunLayoutView(container, original_view=panel))

    @tag.command(name="create", description="Create a new tag via modal")
    async def tag_create(self, ctx: discord.ApplicationContext):
        """Launches the tag creation modal."""
        await ctx.send_modal(TagCreateModal())

    @tag.command(name="edit", description="Edit an existing tag")
    @option("name", description="The tag to edit", autocomplete=tag_autocomplete)
    async def tag_edit(self, ctx: discord.ApplicationContext, name: str):
        """Fetches tag data and opens the editor modal."""
        tag = await db.tags.get(name, guild_id=ctx.guild_id)
        if not tag:
            return await ctx.respond(f"❌ Tag `{name}` not found.", ephemeral=True)
        
        # Check permissions: Creator or Administrator
        if tag["creator_id"] != ctx.author.id and not ctx.author.guild_permissions.administrator:
            return await ctx.respond(embed=EmbedFactory.error("Permission Denied", "You do not have permission to edit this tag.", ctx=ctx), ephemeral=True)

        await ctx.send_modal(TagCreateModal(tag_name=name, current_content=tag["content"]))

    @tag.command(name="delete", description="Permanently delete a tag")
    @option("name", description="The tag to remove", autocomplete=tag_autocomplete)
    async def tag_delete(self, ctx: discord.ApplicationContext, name: str):
        """Deletes a tag from the server database."""
        tag = await db.tags.get(name, guild_id=ctx.guild_id)
        if not tag:
            return await ctx.respond(embed=EmbedFactory.error("Not Found", f"Tag `{name}` not found.", ctx=ctx), ephemeral=True)

        if tag["creator_id"] != ctx.author.id and not ctx.author.guild_permissions.administrator:
            return await ctx.respond(embed=EmbedFactory.error("Permission Denied", "You do not have permission to delete this tag.", ctx=ctx), ephemeral=True)

        await db.tags.delete(name, guild_id=ctx.guild_id)
        await ctx.respond(embed=EmbedFactory.toast(f"Tag `{name}` has been deleted.", ctx, success=True), ephemeral=True)

    # --- Configuration ---

    @tag.command(name="prefix", description="Set the prefix for tag triggers (e.g., ! or ?)")
    @has_level(PermissionLevel.ADMINISTRATOR)
    @option("prefix", description="The new prefix for tags. Use 'none' to disable prefix triggers.")
    async def tag_prefix(self, ctx: discord.ApplicationContext, prefix: str):
        """Sets the prefix used to trigger tags via text messages."""
        if prefix.lower() == "none":
            await db.settings.set("tag_prefix", "", guild_id=ctx.guild_id)
            return await ctx.respond(EmbedFactory.success("Prefix Disabled", "Tags can now only be invoked via slash commands.", ctx=ctx))
        
        if len(prefix) > 3:
            return await ctx.respond(embed=EmbedFactory.error("Invalid Prefix", "Prefix must be 3 characters or less.", ctx=ctx), ephemeral=True)

        await db.settings.set("tag_prefix", prefix, guild_id=ctx.guild_id)
        await ctx.respond(EmbedFactory.success("Prefix Updated", f"Tags can now be triggered using `{prefix}tagname`.", ctx=ctx))

    # --- Listeners ---

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listens for tag triggers in messages."""
        if message.author.bot or not message.guild:
            return

        # Fetch the guild's tag prefix, default to '?'
        prefix = await db.settings.get("tag_prefix", guild_id=message.guild.id)
        if prefix is None:
            prefix = "?"
            
        if not prefix: # Explicitly disabled
            return

        if message.content.startswith(prefix):
            tag_name = message.content[len(prefix):].split(" ", 1)[0].lower()
            if not tag_name:
                return

            tag = await db.tags.get(tag_name, guild_id=message.guild.id)
            if tag:
                from utils.registry import registry
                
                # --- Smart Reply Logic ---
                target_message = message
                if message.reference and isinstance(message.reference.resolved, discord.Message):
                    target_message = message.reference.resolved

                r_id = registry.register_response("TAG_PREFIX", {"name": tag_name}, message=message)
                
                rendered = self.render_tag(tag)
                footer_text = f"r-id: {r_id}"
                
                send_kwargs = {}
                if rendered["embed"]:
                    rendered["embed"].set_footer(text=footer_text)
                    send_kwargs["embed"] = rendered["embed"]
                else:
                    content = rendered["content"]
                    content += f"\n\n-# {footer_text}"
                    send_kwargs["content"] = content

                try:
                    await target_message.reply(mention_author=False, **send_kwargs)
                    
                    # Clean up the trigger message if we replied to someone else
                    if target_message != message:
                        try: await message.delete()
                        except: pass
                except discord.HTTPException:
                    await message.channel.send(**send_kwargs)


def setup(bot):
    bot.add_cog(Avatar(bot))
    bot.add_cog(Tags(bot))
