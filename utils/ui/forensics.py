import discord
import json
import asyncio
from typing import Union, List, Optional, Any, Dict
from datetime import datetime

from utils.registry import registry
from utils.ui.fun_layout import FunLayoutView, create_fun_container
from utils.ui.embed_factory import EmbedFactory

class ForensicTraceExplorer(discord.ui.View):
    """
    Forensic Trace Engine: Reconstructs the chain of custody for any forensic ID.
    Visualizes the journey from command execution to final response.
    """
    def __init__(self, ctx: Union[discord.ApplicationContext, discord.Interaction], start_id: str):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.start_id = start_id
        self.chain = []
        self.current_index = 0
        self._interaction_lock = asyncio.Lock()

    async def initialize(self):
        """Pre-fetches the trace chain."""
        self.chain = await registry.trace(self.start_id)
        self.current_index = len(self.chain) - 1 if self.chain else 0

    async def _safe_respond(self, interaction: discord.Interaction, container: Any):
        async with self._interaction_lock:
            view = FunLayoutView(container, original_view=self)
            try:
                if interaction.response.is_done():
                    await interaction.edit_original_response(view=view)
                else:
                    await interaction.response.edit_message(view=view)
            except Exception:
                await interaction.followup.send(view=view, ephemeral=True)

    async def build_page(self) -> Any:
        self.clear_items()
        
        if not self.chain:
            return create_fun_container(
                "🔍 Forensic Trace: Null", 
                f"No chain of custody found for ID `{self.start_id}`.",
                color=0xE74C3C
            )

        snapshot = self.chain[self.current_index]
        trace_id = snapshot.get("_trace_id")
        trace_type = snapshot.get("_trace_type")
        status = snapshot.get("_trace_status")
        
        # 1. Build Chain visualization
        chain_viz = ""
        for i, item in enumerate(self.chain):
            marker = "⏺️" if i == self.current_index else "⚪"
            chain_viz += f"{marker} "
        
        # 2. Build details based on type
        body = f"### 📂 Chain of Custody\n{chain_viz}\n\n"
        body += f"**Step {self.current_index + 1} of {len(self.chain)}**\n"
        body += f"- **ID:** `{trace_id}`\n"
        body += f"- **Type:** `{trace_type}`\n"
        body += f"- **Status:** `{'🟢 LIVE' if status == 'ACTIVE' else '📂 ARCHIVED'}`\n\n"
        
        body += "### 📋 Snapshot Data\n"
        
        if trace_type == "RESPONSE":
            body += f"- **Response Type:** `{snapshot.get('response_type')}`\n"
            body += f"- **User:** {snapshot.get('user', {}).get('name')} (`{snapshot.get('user', {}).get('id')}`)\n"
            body += f"- **Guild:** `{snapshot.get('guild', {}).get('name')}`\n"
            content = snapshot.get('content', 'No content.')
            if isinstance(content, dict):
                content = json.dumps(content, indent=2)
            body += f"```\n{str(content)[:300]}\n```"
            
        elif trace_type == "VIEW":
            body += f"- **Class:** `{snapshot.get('class')}`\n"
            body += f"- **Timeout:** `{snapshot.get('timeout')}s`\n"
            body += f"- **Items:** `{len(snapshot.get('items', []))} components`\n"
            if "parent_v_id" in snapshot:
                body += f"- **Parent v-id:** `{snapshot['parent_v_id']}`\n"
                
        elif trace_type == "ERROR":
            body += f"**Exception:** `{snapshot.get('error_type')}`\n"
            body += f"**Message:** `{snapshot.get('message')}`\n"
            loc = snapshot.get('location', {})
            body += f"**Location:** `{loc.get('file')}:{loc.get('line')}` in `{loc.get('function')}`\n"
            
        elif trace_type == "INTERACTION" and trace_id.startswith("cmd-"):
            body += f"**Command:** `/{snapshot.get('command')}`\n"
            body += f"**Status:** `{snapshot.get('status')}`\n"
            body += f"**User:** {snapshot.get('user', {}).get('name')}\n"
            
        else:
            # Generic view
            for k, v in snapshot.items():
                if not k.startswith("_") and k not in ["type", "v_id", "logged_at", "parent_id"]:
                    body += f"- **{k.title()}:** `{v}`\n"

        body += f"\n-# Logged at {snapshot.get('logged_at', 'Unknown')}"

        # 3. Add Navigation
        if len(self.chain) > 1:
            self.add_item(TraceNavButton("Previous", self.current_index - 1, self))
            self.add_item(TraceNavButton("Next", self.current_index + 1, self))

        return create_fun_container(
            f"🔍 Trace Explorer: {trace_id}", 
            body, 
            view_id=f"trace-explorer-{trace_id}",
            color=0x3498DB if status == "ACTIVE" else 0x95A5A6
        )

class TraceNavButton(discord.ui.Button):
    def __init__(self, direction: str, target_index: int, explorer: ForensicTraceExplorer):
        label = "⬅️ Parent" if direction == "Previous" else "Child ➡️"
        disabled = target_index < 0 or target_index >= len(explorer.chain)
        super().__init__(label=label, style=discord.ButtonStyle.secondary, disabled=disabled)
        self.target_index = target_index
        self.explorer = explorer

    async def callback(self, interaction: discord.Interaction):
        self.explorer.current_index = self.target_index
        container = await self.explorer.build_page()
        await self.explorer._safe_respond(interaction, container)
