import discord
import json
from utils.database import db
from utils.ui.fun_layout import FunLayoutView, create_fun_container
from utils.ui.embed_factory import EmbedFactory

class TagCreateModal(discord.ui.Modal):
    def __init__(self, tag_name=None, current_content=None, is_embed=False, thumbnail_url=None):
        super().__init__(title="Configure Tag Content")
        self.tag_name = tag_name
        self.is_embed = is_embed
        self.thumbnail_url = thumbnail_url

        self.add_item(
            discord.ui.InputText(
                label="Tag Name",
                placeholder="e.g. rules",
                value=tag_name,
                min_length=1,
                max_length=50,
                required=True
            )
        )

        if is_embed:
            self.add_item(
                discord.ui.InputText(
                    label="Embed Title",
                    placeholder="The bold title of the embed",
                    value=current_content.get("title") if isinstance(current_content, dict) else None,
                    required=False,
                )
            )
            self.add_item(
                discord.ui.InputText(
                    label="Embed Description",
                    style=discord.InputTextStyle.long,
                    placeholder="The main body text of the embed",
                    value=current_content.get("description") if isinstance(current_content, dict) else current_content,
                    required=True,
                )
            )
            self.add_item(
                discord.ui.InputText(
                    label="Image/Thumbnail URL",
                    placeholder="https://example.com/image.png",
                    value=thumbnail_url,
                    required=False,
                )
            )
            self.add_item(
                discord.ui.InputText(
                    label="Embed Color (Hex)",
                    placeholder="#3498DB",
                    value=current_content.get("color") if isinstance(current_content, dict) else None,
                    required=False,
                )
            )
        else:
            self.add_item(
                discord.ui.InputText(
                    label="Text Content",
                    style=discord.InputTextStyle.long,
                    placeholder="What should this tag say?",
                    value=current_content if isinstance(current_content, str) else current_content.get("description") if current_content else None,
                    min_length=1,
                    max_length=2000,
                    required=True,
                )
            )

    async def callback(self, interaction: discord.Interaction):
        # Use original tag name if editing to prevent accidental name changes
        name = self.tag_name.lower() if self.tag_name else self.children[0].value.lower()
        
        if self.is_embed:
            title = self.children[1].value
            description = self.children[2].value
            thumb = self.children[3].value
            color = self.children[4].value
            
            content_data = {
                "title": title,
                "description": description,
                "color": color
            }
            final_content = json.dumps(content_data)
            thumbnail = thumb
        else:
            final_content = self.children[1].value
            thumbnail = None

        try:
            if self.tag_name: # Editing
                await db.tags.edit(name, final_content, guild_id=interaction.guild_id, is_embed=self.is_embed, thumbnail_url=thumbnail)
                await interaction.response.send_message(embed=EmbedFactory.toast(f"Tag `{name}` updated!", interaction), ephemeral=True)
            else: # Creating
                await db.tags.create(name, final_content, interaction.user.id, str(interaction.user), guild_id=interaction.guild_id, is_embed=self.is_embed, thumbnail_url=thumbnail)
                await interaction.response.send_message(embed=EmbedFactory.toast(f"Tag `{name}` created!", interaction), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(embed=EmbedFactory.error("Save Failed", str(e), ctx=interaction), ephemeral=True)


class TagTypeView(discord.ui.View):
    def __init__(self, ctx, tag_name=None, current_content=None, is_embed=False, thumbnail_url=None):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.tag_name = tag_name
        self.current_content = current_content
        self.is_embed = is_embed
        self.thumbnail_url = thumbnail_url

    @discord.ui.button(label="Text Tag", style=discord.ButtonStyle.primary, emoji="💬")
    async def text_tag(self, button, interaction):
        content = self.current_content
        if isinstance(content, str) and content.startswith("{"):
            try: content = json.loads(content)
            except: pass
            
        await interaction.response.send_modal(TagCreateModal(
            tag_name=self.tag_name, 
            current_content=content, 
            is_embed=False
        ))

    @discord.ui.button(label="Embed Tag", style=discord.ButtonStyle.primary, emoji="🖼️")
    async def embed_tag(self, button, interaction):
        content = self.current_content
        if isinstance(content, str) and content.startswith("{"):
            try: content = json.loads(content)
            except: pass
        elif isinstance(content, str):
            content = {"description": content}

        await interaction.response.send_modal(TagCreateModal(
            tag_name=self.tag_name, 
            current_content=content, 
            is_embed=True,
            thumbnail_url=self.thumbnail_url
        ))


class TagSelect(discord.ui.Select):
    def __init__(self, tags, selected_name=None, tag_control_panel=None):
        options = [
            discord.SelectOption(
                label=tag["name"], 
                description=f"By {tag['creator_name']} • {tag['uses']} uses",
                default=(tag["name"] == selected_name)
            )
            for tag in tags
        ]
        super().__init__(
            placeholder="Select a tag to manage...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )
        self.tag_control_panel = tag_control_panel

    async def callback(self, interaction: discord.Interaction):
        view = self.tag_control_panel or self.view
        if isinstance(view, FunLayoutView) and view.original_view:
            view = view.original_view

        view.selected_tag = self.values[0]
        view.update_button_states()
        container = await view.build_page()
        await interaction.response.edit_message(view=FunLayoutView(container, original_view=view))


class TagControlPanel(discord.ui.View):
    def __init__(self, ctx, bot):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.bot = bot
        self.current_page = 0
        self.tags_per_page = 5
        self.selected_tag = None
        self.all_tags = []

    def update_button_states(self):
        has_selection = self.selected_tag is not None
        self.edit_btn.disabled = not has_selection
        self.delete_btn.disabled = not has_selection
        
        self.prev_btn.disabled = self.current_page == 0
        max_pages = max(1, (len(self.all_tags) - 1) // self.tags_per_page + 1)
        self.next_btn.disabled = self.current_page >= max_pages - 1

    async def build_page(self):
        self.all_tags = await db.tags.list_all(guild_id=self.ctx.guild_id)
        max_pages = max(1, (len(self.all_tags) - 1) // self.tags_per_page + 1)
        
        start = self.current_page * self.tags_per_page
        end = start + self.tags_per_page
        current_tags = self.all_tags[start:end]

        title = "🏷️ Tag Control Panel"
        body = f"Total Tags: `{len(self.all_tags)}` | Page `{self.current_page + 1}/{max_pages}`\n"
        if self.selected_tag:
            body += f"Selected: **`{self.selected_tag}`**\n"
        body += "\n"
        
        if not current_tags:
            body += "*No tags found in this server.*"
        else:
            for tag in current_tags:
                marker = "▶️" if tag["name"] == self.selected_tag else "🔹"
                tag_type = "🖼️ Embed" if tag["is_embed"] else "💬 Text"
                body += f"{marker} **`{tag['name']}`** ({tag_type})\n-# Created by {tag['creator_name']} • {tag['uses']} uses\n"

        self.clear_items()
        if current_tags:
            self.add_item(TagSelect(current_tags, self.selected_tag, tag_control_panel=self))
        
        self.add_item(self.create_btn)
        self.add_item(self.edit_btn)
        self.add_item(self.delete_btn)
        self.add_item(self.prev_btn)
        self.add_item(self.next_btn)
        
        self.update_button_states()

        container = create_fun_container(
            title=title,
            body=body,
            view_id=f"tag-cp-p{self.current_page}",
            interaction=self.ctx
        )
        return container

    @discord.ui.button(label="Create", style=discord.ButtonStyle.success, emoji="➕")
    async def create_btn(self, button, interaction):
        view = TagTypeView(self.ctx)
        container = create_fun_container(
            title="Choose Tag Type",
            body="Would you like to create a simple **Text Tag** or a rich **Embed Tag**?",
            interaction=interaction
        )
        await interaction.response.send_message(view=FunLayoutView(container, original_view=view), ephemeral=True)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, emoji="📝")
    async def edit_btn(self, button, interaction):
        tag = await db.tags.get(self.selected_tag, guild_id=interaction.guild_id)
        if not tag:
            return await interaction.response.send_message("❌ Tag not found.", ephemeral=True)
            
        if tag["creator_id"] != interaction.user.id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ No permission to edit this tag.", ephemeral=True)
            
        view = TagTypeView(
            self.ctx, 
            tag_name=tag["name"], 
            current_content=tag["content"],
            is_embed=bool(tag["is_embed"]),
            thumbnail_url=tag["thumbnail_url"]
        )
        container = create_fun_container(
            title=f"Edit Tag: {tag['name']}",
            body="Choose the mode you want to use for editing this tag.",
            interaction=interaction
        )
        await interaction.response.send_message(view=FunLayoutView(container, original_view=view), ephemeral=True)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_btn(self, button, interaction):
        tag = await db.tags.get(self.selected_tag, guild_id=interaction.guild_id)
        if not tag:
            return await interaction.response.send_message("❌ Tag not found.", ephemeral=True)
            
        if tag["creator_id"] != interaction.user.id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ No permission to delete this tag.", ephemeral=True)
            
        await db.tags.delete(self.selected_tag, guild_id=interaction.guild_id)
        deleted_name = tag["name"]
        self.selected_tag = None
        container = await self.build_page()
        
        container.items[2].content = f"✅ Tag `{deleted_name}` deleted.\n\n" + container.items[2].content
        await interaction.response.edit_message(view=FunLayoutView(container, original_view=self))

    async def on_error(self, error, item, interaction):
        from utils.error_handler import UniversalErrorHandler
        await UniversalErrorHandler().handle_ui_error(interaction, error)

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, button, interaction):
        self.current_page -= 1
        self.selected_tag = None
        container = await self.build_page()
        await interaction.response.edit_message(view=FunLayoutView(container, original_view=self))

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_btn(self, button, interaction):
        self.current_page += 1
        self.selected_tag = None
        container = await self.build_page()
        await interaction.response.edit_message(view=FunLayoutView(container, original_view=self))
