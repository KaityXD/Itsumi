import datetime
import uuid
from typing import Optional, Union

import discord


def create_fun_container(
    title: str,
    body: str,
    accessory: Optional[discord.ui.ViewItem] = None,
    color: Optional[Union[discord.Color, int]] = None,
    spoiler: bool = False,
    image_url: Optional[str] = None,
    view_id: Optional[str] = None,
    interaction: Optional[Union[discord.Interaction, discord.ApplicationContext]] = None,
    ephemeral: bool = False,
) -> discord.ui.Container:
    """
    Utility to quickly create a modern Components V2 container for fun commands.
    """
    from utils.registry import registry

    r_id = registry.register_response(
        "LAYOUT", 
        {"title": title, "body": body}, 
        interaction=interaction,
        ephemeral=ephemeral
    )

    if not view_id:
        view_id = str(uuid.uuid4())[:8]

    container = discord.ui.Container(color=color, spoiler=spoiler)

    # Add Header
    container.add_item(discord.ui.TextDisplay(content=f"## {title}"))

    # Add Separator
    container.add_item(discord.ui.Separator())

    # Add Content Section
    if accessory:
        section = discord.ui.Section()
        section.add_item(discord.ui.TextDisplay(content=body))
        section.accessory = accessory
        container.add_item(section)
    else:
        # If no accessory, just add the text directly to avoid the gray placeholder button
        container.add_item(discord.ui.TextDisplay(content=body))

    # Add Image if provided
    if image_url:
        container.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(image_url)))

    # Add Footer with View ID and Response ID
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    container.add_item(discord.ui.Separator(divider=False))
    container.add_item(
        discord.ui.TextDisplay(
            content=f"-# Type: Layout | {now} | v-id: {view_id} | r-id: {r_id}"
        )
    )

    # Register this container snapshot
    registry.register_interaction(
        view_id,
        {
            "type": "CONTAINER",
            "title": title,
            "body": body,
            "image_url": image_url,
            "spoiler": spoiler,
            "r_id": r_id,
        },
    )

    container._view_id = view_id
    container._r_id = r_id
    return container


class FunLayoutView(discord.ui.DesignerView):
    """
    A DesignerView that wraps a container and dynamically incorporates items from an original view.
    """
    def __init__(
        self,
        container: Optional[discord.ui.Container] = None,
        timeout: Optional[float] = 180.0,
        custom_id: Optional[str] = None,
        view_id: Optional[str] = None,
        original_view: Optional[discord.ui.View] = None,
        parent_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(timeout=timeout)
        self.parent_id = parent_id
        self.original_view = original_view
        self.view_id = view_id or (getattr(container, "_view_id", None) if container else None) or f"v-{str(uuid.uuid4())[:8]}"
        
        # Restoration support
        if not container and "container_data" in kwargs:
            data = kwargs["container_data"]
            container = create_fun_container(
                title=data.get("title", "Restored View"),
                body=data.get("body", "This view was restored after a bot restart."),
                view_id=self.view_id
            )

        if container:
            self.add_item(container)
            self.r_id = getattr(container, "_r_id", None)
            
            title = "Restored"
            if len(container.items) > 0 and hasattr(container.items[0], "content"):
                title = container.items[0].content.lstrip("# ")
                
            body = ""
            if len(container.items) > 2:
                item = container.items[2]
                if hasattr(item, "content"):
                    body = item.content
                elif hasattr(item, "items") and len(item.items) > 0 and hasattr(item.items[0], "content"):
                    body = item.items[0].content
                    
            self._container_data = {
                "title": title,
                "body": body
            }

        if original_view:
        # (rest of items sync logic ...)

            # Sync the original view's on_error only if it's not the default View.on_error
            original_on_error = getattr(original_view, "on_error", None)
            if original_on_error:
                func = getattr(original_on_error, "__func__", None)
                if func and func is not discord.ui.View.on_error:
                    self.on_error = original_on_error

            # DesignerView (Components V2) REQUIRES ActionRows for Buttons/Selects.
            # We sort items into Actions (Top) and Navigation (Bottom)
            from discord.ui import ActionRow
            
            nav_emojis = ["◀️", "🏠", "▶️", "🔄"]
            selects = []
            action_buttons = []
            nav_buttons = []
            others = []

            for item in original_view.children:
                if hasattr(item, "row"):
                    item.row = None
                
                if item.type in (
                    discord.ComponentType.string_select,
                    discord.ComponentType.user_select,
                    discord.ComponentType.role_select,
                    discord.ComponentType.mentionable_select,
                    discord.ComponentType.channel_select
                ):
                    selects.append(item)
                elif item.type == discord.ComponentType.button:
                    # Categorize buttons
                    if (hasattr(item, "emoji") and item.emoji and item.emoji.name in nav_emojis):
                        item.style = discord.ButtonStyle.secondary
                        nav_buttons.append(item)
                    else:
                        action_buttons.append(item)
                else:
                    others.append(item)

            # 1. Add Selects (Each in its own row)
            for select in selects:
                container.add_item(ActionRow(select))

            # 2. Add Action Buttons (Grouped)
            if action_buttons:
                for i in range(0, len(action_buttons), 5):
                    container.add_item(ActionRow(*action_buttons[i:i+5]))

            # 3. Add Navigation Buttons (Grouped at the bottom)
            if nav_buttons:
                for i in range(0, len(nav_buttons), 5):
                    container.add_item(ActionRow(*nav_buttons[i:i+5]))

            # 4. Add other items normally to the VIEW
            for item in others:
                self.add_item(item)

        # Pull IDs from container if not provided
        self.view_id = view_id or getattr(container, "_view_id", None)
        self.r_id = getattr(container, "_r_id", None)

        if self.view_id:
            from utils.registry import registry

            # Try to get a user ID from the view if possible
            user_id = None
            if hasattr(self, "ctx") and hasattr(self.ctx, "author"):
                user_id = self.ctx.author.id
            elif hasattr(self, "user"):
                user_id = self.user.id

            # Snapshot info with parent trace
            view_info = {
                "type": "VIEW",
                "class": self.__class__.__name__,
                "timeout": self.timeout,
                "parent_v_id": self.parent_id,
                "items": [str(i) for i in self.children],
            }
            registry.register_interaction(self.view_id, view_info, user_id=user_id)
            registry.register_view(self.view_id, self)

    def __get_init_args__(self):
        """Returns the data needed to reconstruct this view after a restart."""
        return {
            "timeout": self.timeout,
            "view_id": self.view_id,
            "parent_id": self.parent_id,
            "container_data": getattr(self, "_container_data", {})
        }

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction):
        """Global error handler for all FunLayoutView components."""
        from utils.error_handler import UniversalErrorHandler
        handler = UniversalErrorHandler()
        await handler.handle_ui_error(interaction, error)
