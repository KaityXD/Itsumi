import datetime
import uuid
from typing import List, Optional, Union

import discord


def create_fun_container(
    title: str,
    body: str,
    accessory: Optional[discord.ui.ViewItem] = None,
    color: Optional[Union[discord.Color, int]] = None,
    spoiler: bool = False,
    image_url: Optional[str] = None,
    view_id: Optional[str] = None,
) -> discord.ui.Container:
    """
    Utility to quickly create a modern Components V2 container for fun commands.
    """
    if not view_id:
        view_id = str(uuid.uuid4())[:8]

    container = discord.ui.Container(color=color, spoiler=spoiler)

    # Add Header
    container.add_item(discord.ui.TextDisplay(content=f"## {title}"))

    # Add Separator
    container.add_item(discord.ui.Separator())

    # Add Content Section
    section = discord.ui.Section()
    section.add_item(discord.ui.TextDisplay(content=body))

    # Sections MUST have an accessory (Button or Thumbnail)
    if accessory:
        section.accessory = accessory
    else:
        # If no accessory is provided, we use a small transparent/invisible button as a placeholder
        section.accessory = discord.ui.Button(
            label="\u200b", style=discord.ButtonStyle.secondary, disabled=True
        )

    container.add_item(section)

    # Add Image if provided
    if image_url:
        container.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(image_url)))

    # Add Footer with View ID
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    container.add_item(discord.ui.Separator(divider=False))
    container.add_item(discord.ui.TextDisplay(content=f"-# {now} | v-id: {view_id}"))

    return container


class FunLayoutView(discord.ui.DesignerView):
    """
    A simple DesignerView that wraps a single container.
    """

    def __init__(
        self,
        container: discord.ui.Container,
        timeout: Optional[float] = 180.0,
        custom_id: Optional[str] = None,
    ):
        super().__init__(timeout=timeout)
        self.add_item(container)
        if custom_id:
            # Persistent views usually need a custom_id for the items to trigger
            # correctly after restart.
            for item in self.children:
                if hasattr(item, "custom_id") and item.custom_id is None:
                    # Note: Most V2 components use 'id' instead of 'custom_id'
                    pass
