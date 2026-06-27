import asyncio
import datetime
import uuid
import functools
import discord
from typing import Any, Dict, Optional, Union, List

from utils.registry import registry
from utils.logger import logger

import importlib

def inject_automation(bot: discord.Bot):
    """
    Hooks into Pycord's core components to automatically generate and track:
    - v-id: For every UI View
    - r-id: For every response sent by the bot
    - e-id: For every error captured
    """
    logger.info("Initializing Global Forensic Automation...")

    _automate_views()
    _automate_responses()
    _automate_errors(bot)
    
    # Register the restoration engine to run when the bot is ready
    @bot.event
    async def on_ready():
        await restore_all_views(bot)

async def restore_all_views(bot: discord.Bot):
    """
    The Restoration Engine: Hydrates active views from the database 
    and re-registers them with the bot's persistent view registry.
    """
    logger.info("UI Restoration Engine: Scanning for active views...")
    active_snapshots = await registry.get_active_views()
    
    restored_count = 0
    for snap in active_snapshots:
        v_id = snap["v_id"]
        class_path = snap["class_path"]
        init_args = snap.get("init_args", {})
        
        try:
            # 1. Dynamically import the class
            module_name, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            view_class = getattr(module, class_name)
            
            # 2. Re-hydrate context/objects if possible
            # Note: We can only truly restore persistent views (timeout=None)
            # or those that don't rely on transient object references.
            
            # 3. Instantiate the view
            # We filter init_args to only those the class constructor accepts
            try:
                import inspect
                sig = inspect.signature(view_class)
                has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
                if not has_var_keyword:
                    filtered_args = {k: v for k, v in init_args.items() if k in sig.parameters}
                else:
                    filtered_args = init_args
                
                # Automatically inject bot if the constructor requests it and it's not already provided
                if "bot" in sig.parameters and "bot" not in filtered_args:
                    filtered_args["bot"] = bot
            except Exception:
                filtered_args = init_args

            view = view_class(**filtered_args)
            view.view_id = v_id # Ensure v_id is preserved
            
            # 4. Re-register with the bot
            bot.add_view(view)
            restored_count += 1
            logger.trace(f"  └─ Restored View: {v_id} ({class_name})")
            
        except Exception as e:
            logger.warning(f"  └─ Failed to restore view {v_id}: {e}")

    if restored_count > 0:
        logger.success(f"UI Restoration Engine: Successfully restored {restored_count} active views.")
    else:
        logger.info("UI Restoration Engine: No active views required restoration.")

def _automate_views():
    """Monkey-patches discord.ui.View to auto-generate v-id and persistent component IDs."""
    original_init = discord.ui.View.__init__

    @functools.wraps(original_init)
    def patched_init(self, *args, **kwargs):
        v_id = kwargs.pop("view_id", None)
        original_init(self, *args, **kwargs)
        
        if not hasattr(self, "view_id") or not self.view_id:
            self.view_id = v_id or f"v-{str(uuid.uuid4())[:8]}"
            
        # --- Persistent Component Automation ---
        # We ensure every button/select has a custom_id that includes the v_id
        # this allows Pycord to route interactions back to this view instance.
        for index, item in enumerate(self.children):
            if hasattr(item, "custom_id") and item.custom_id is None:
                # Generate a deterministic custom_id based on v_id and position
                item.custom_id = f"{self.view_id}:{item.__class__.__name__}:{index}"

        # Register the view with the registry safely and asynchronously if loop is running
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.call_soon(lambda: registry.register_view(self.view_id, self))
            else:
                registry.register_view(self.view_id, self)
        except (RuntimeError, AttributeError):
            try:
                registry.register_view(self.view_id, self)
            except Exception:
                pass

    discord.ui.View.__init__ = patched_init
    logger.trace("Successfully patched discord.ui.View for v-id and component automation.")

def _automate_responses():
    """
    Monkey-patches response methods to auto-generate r-id 
    and inject it into embeds/content.
    """
    
    def _inject_r_id_to_params(r_id: str, kwargs: Dict[str, Any]):
        content = kwargs.get("content")
        embed = kwargs.get("embed")
        embeds = kwargs.get("embeds")
        
        footer_text = f"r-id: {r_id}"
        
        if embeds:
            for e in embeds:
                if isinstance(e, discord.Embed):
                    _append_to_footer(e, footer_text)
        elif embed and isinstance(embed, discord.Embed):
            _append_to_footer(embed, footer_text)
        elif content is not None:
            # Only append to content if it's a string and no embeds are present
            if isinstance(content, str) and not (embed or embeds):
                if footer_text not in content:
                    kwargs["content"] = f"{content}\n\n-# {footer_text}"
        elif not (embed or embeds):
            # If nothing is provided, we can't really inject it visually 
            # unless we add content
            kwargs["content"] = f"-# {footer_text}"

    def _append_to_footer(embed: discord.Embed, text: str):
        current_footer = embed.footer.text or ""
        if text not in current_footer:
            new_footer = f"{current_footer} | {text}" if current_footer else text
            embed.set_footer(text=new_footer, icon_url=embed.footer.icon_url)

    # 1. Patch ApplicationContext.respond
    original_ctx_respond = discord.ApplicationContext.respond
    
    @functools.wraps(original_ctx_respond)
    async def patched_ctx_respond(self, *args, **kwargs):
        # Avoid double registration if it's already registered by EmbedFactory
        # We check if an r-id is already in the footer of an embed
        existing_r_id = None
        embed = kwargs.get("embed")
        embeds = kwargs.get("embeds")
        if embed and embed.footer.text and "r-id:" in embed.footer.text:
            existing_r_id = embed.footer.text.split("r-id:")[1].strip().split(" ")[0]
        elif embeds:
            for e in embeds:
                if e.footer.text and "r-id:" in e.footer.text:
                    existing_r_id = e.footer.text.split("r-id:")[1].strip().split(" ")[0]
                    break
        
        r_id = existing_r_id or registry.register_response(
            response_type="AUTO_CMD",
            content=kwargs.get("content") or "Embed/View Response",
            interaction=self,
            ephemeral=kwargs.get("ephemeral", False)
        )
        
        if not existing_r_id:
            _inject_r_id_to_params(r_id, kwargs)
            
        return await original_ctx_respond(self, *args, **kwargs)

    discord.ApplicationContext.respond = patched_ctx_respond

    # 2. Patch InteractionResponse.send_message
    original_ir_send = discord.InteractionResponse.send_message
    
    @functools.wraps(original_ir_send)
    async def patched_ir_send(self, *args, **kwargs):
        r_id = registry.register_response(
            response_type="AUTO_INTERACT",
            content=kwargs.get("content") or "Interaction Response",
            interaction=self._parent, # InteractionResponse has _parent which is Interaction
            ephemeral=kwargs.get("ephemeral", False)
        )
        _inject_r_id_to_params(r_id, kwargs)
        return await original_ir_send(self, *args, **kwargs)

    discord.InteractionResponse.send_message = patched_ir_send

    # 3. Patch Webhook.send (Used for followups)
    original_webhook_send = discord.Webhook.send
    
    @functools.wraps(original_webhook_send)
    async def patched_webhook_send(self, *args, **kwargs):
        # We don't always have an interaction here, but we can try to find one
        r_id = registry.register_response(
            response_type="AUTO_FOLLOWUP",
            content=kwargs.get("content") or "Followup Response",
            ephemeral=kwargs.get("ephemeral", False)
        )
        _inject_r_id_to_params(r_id, kwargs)
        return await original_webhook_send(self, *args, **kwargs)

    discord.Webhook.send = patched_webhook_send

    # 4. Patch Messageable.send (For Text Channels, DMs, etc.)
    original_send = discord.abc.Messageable.send

    @functools.wraps(original_send)
    async def patched_send(self, *args, **kwargs):
        r_id = registry.register_response(
            response_type="AUTO_MSG",
            content=kwargs.get("content") or "Message Response",
        )
        _inject_r_id_to_params(r_id, kwargs)
        return await original_send(self, *args, **kwargs)

    discord.abc.Messageable.send = patched_send

    logger.trace("Successfully patched response methods for r-id automation.")

def _automate_errors(bot: discord.Bot):
    """Hooks into global error events to capture e-id."""
    from utils.error_handler import UniversalErrorHandler
    handler = UniversalErrorHandler()

    @bot.event
    async def on_application_command_error(ctx: discord.ApplicationContext, error: Exception):
        await handler.handle_error(ctx, error)

    # We also need to log commands for v-id (command execution)
    @bot.event
    async def on_application_command_completion(ctx: discord.ApplicationContext):
        handler.log_command(ctx)

    logger.trace("Successfully hooked global error and completion events for e-id/v-id automation.")
