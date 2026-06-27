import discord
import json
import asyncio
from typing import Union, List, Optional, Any, Dict
from utils.database import db
from utils.permissions import PermissionLevel, PermissionManager, SecPerm
from utils.ui.fun_layout import FunLayoutView, create_fun_container
from utils.ui.embed_factory import EmbedFactory
from utils.ui.security_auditor import SecurityAuditor

class OverlordSecurityCenter(discord.ui.View):
    """
    Overlord Security Engine v5: High-Density RBAC Infrastructure.
    Professional dashboard for managing security teams, bitfield permissions, and node overrides.
    """
    def __init__(self, ctx: discord.ApplicationContext):
        super().__init__(timeout=600)
        self.ctx = ctx
        self.guild_id = ctx.guild.id
        self.state = "MAIN"  # MAIN, TEAMS, TEAM_DETAIL, EDIT_PERMS, ADD_MEMBER, NODES
        self.selected_team = None # The group ID (Row)
        self.auditor = SecurityAuditor(ctx.guild)
        self._interaction_lock = asyncio.Lock()

    async def _safe_respond(self, interaction: discord.Interaction, container: Any):
        """High-reliability response handler."""
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
        
        match self.state:
            case "MAIN": return await self._build_soc_main()
            case "TEAMS": return await self._build_teams_list()
            case "TEAM_DETAIL": return await self._build_team_detail()
            case "EDIT_PERMS": return await self._build_perm_matrix()
            case "ADD_MEMBER": return await self._build_member_deployment()
            case "NODES": return await self._build_node_registry()
            case _: return await self._build_soc_main()

    # --- SOC State Builders ---

    async def _build_soc_main(self):
        groups = await db.permissions.list_groups(self.guild_id)
        overrides = await db.permissions.list_overrides(self.guild_id)
        
        title = "🛰️ OVERLORD SECURITY CENTER [v5]"
        body = (
            "### 📊 CORE INFRASTRUCTURE\n"
            f"- **Security Teams:** `{len(groups)}` active\n"
            f"- **Node Overrides:** `{len(overrides)}` active\n"
            f"- **Encryption:** `AES-256-GCM` 🔐\n"
            f"- **Protocol:** `RBAC / ENFORCED` ⚔️\n\n"
            "### 🛠️ OPERATIONAL ZONES\n"
            "Manage infrastructure access tiers and command node routing."
        )
        
        self._add_nav_buttons()
        return create_fun_container(title, body, view_id="overlord-main", interaction=self.ctx, color=0x2C3E50)

    async def _build_teams_list(self):
        groups = await db.permissions.list_groups(self.guild_id)
        title = "🛡️ SECURITY TEAMS (RBAC)"
        
        body = "List of active security teams within this jurisdiction:\n\n"
        
        if not groups:
            body += "*No custom security teams registered.*"
        else:
            options = []
            for g in groups:
                marker = "▶️" if self.selected_team and g["id"] == self.selected_team["id"] else "🔹"
                body += f"{marker} **`{g['name']}`** (Perms: `0x{g['permissions_bitfield']:0X}`)\n"
                options.append(discord.SelectOption(label=g["name"], description=f"ID: {g['id']} | Matrix Access", value=str(g["id"])))
            
            if options:
                self.add_item(TeamSelect(options, overlord_view=self))

        self.add_item(CreateTeamButton(overlord_view=self))
        self._add_nav_buttons()
        return create_fun_container(title, body, view_id="overlord-teams", interaction=self.ctx, color=0x27AE60)

    async def _build_team_detail(self):
        team = self.selected_team
        title = f"📁 TEAM CONFIG: {team['name']}"
        
        # Resolve permissions
        active_perms = []
        for bit, label in SecPerm.LABELS.items():
            if team["permissions_bitfield"] & bit:
                active_perms.append(f"`{label}`")
        
        body = (
            f"### ⚙️ TEAM ATTRIBUTES\n"
            f"- **Internal ID:** `{team['id']}`\n"
            f"- **Bitfield:** `0x{team['permissions_bitfield']:0X}`\n"
            f"- **Created:** `{team['created_at']}`\n\n"
            f"### 🔐 ACTIVE PERMISSIONS\n"
            f"{', '.join(active_perms) if active_perms else '*None defined*'}\n"
        )
        
        self.add_item(StateButton(label="Edit Matrix", state="EDIT_PERMS", emoji="🔐", style=discord.ButtonStyle.primary, overlord_view=self))
        self.add_item(StateButton(label="Deploy Members", state="ADD_MEMBER", emoji="➕", style=discord.ButtonStyle.success, overlord_view=self))
        self.add_item(DeleteTeamButton(overlord_view=self))
        self._add_nav_buttons()
        return create_fun_container(title, body, view_id="overlord-detail", interaction=self.ctx, color=0x2980B9)

    async def _build_perm_matrix(self):
        team = self.selected_team
        title = f"🔐 PERMISSION MATRIX: {team['name']}"
        body = "Select a permission to toggle its status in this team's bitfield."
        
        options = []
        for bit, label in SecPerm.LABELS.items():
            is_active = bool(team["permissions_bitfield"] & bit)
            marker = "🟢" if is_active else "🔴"
            options.append(discord.SelectOption(label=label, description=f"{'Revoke' if is_active else 'Grant'} this access", value=str(bit), emoji=marker))
            
        if options:
            self.add_item(PermToggleSelect(options[:25], overlord_view=self))
            
        self.add_item(StateButton(label="Back to Team", state="TEAM_DETAIL", emoji="⬅️", style=discord.ButtonStyle.secondary, overlord_view=self))
        self._add_nav_buttons()
        return create_fun_container(title, body, view_id="overlord-matrix", interaction=self.ctx, color=0x8E44AD)

    async def _build_member_deployment(self):
        title = "➕ MEMBER DEPLOYMENT"
        body = f"Target a role or member to incorporate them into **{self.selected_team['name']}**."
        
        self.add_item(MemberDeploySelect(discord.ComponentType.role_select, "Deploy Role...", overlord_view=self))
        self.add_item(MemberDeploySelect(discord.ComponentType.user_select, "Deploy User...", overlord_view=self))
        
        self.add_item(StateButton(label="Back to Team", state="TEAM_DETAIL", emoji="⬅️", style=discord.ButtonStyle.secondary, overlord_view=self))
        self._add_nav_buttons()
        return create_fun_container(title, body, view_id="overlord-deploy", interaction=self.ctx, color=0xF39C12)

    async def _build_node_registry(self):
        overrides = await db.permissions.list_overrides(self.guild_id)
        title = "⌨️ NODE REGISTRY"
        
        body = "Custom routing protocols for system command nodes:\n\n"
        if not overrides:
            body += "*No node overrides active.*"
        else:
            options = []
            for r in overrides:
                body += f"🔹 **`{r['node']}`** → Tier {r['required_level']}\n"
                options.append(discord.SelectOption(label=r["node"], description=f"Revoke Protocol", value=r["node"], emoji="🗑️"))
            
            if options:
                self.add_item(NodeRevokeSelect(options[:25], overlord_view=self))

        self.add_item(NodeInjectButton(overlord_view=self))
        self._add_nav_buttons()
        return create_fun_container(title, body, view_id="overlord-nodes", interaction=self.ctx, color=0x34495E)

    def _add_nav_buttons(self):
        """Standard Overlord Navigation."""
        self.add_item(StateButton(label="SOC Home", state="MAIN", emoji="🛰️", style=discord.ButtonStyle.primary if self.state == "MAIN" else discord.ButtonStyle.secondary, overlord_view=self))
        self.add_item(StateButton(label="Teams", state="TEAMS", emoji="🛡️", style=discord.ButtonStyle.primary if self.state in ["TEAMS", "TEAM_DETAIL", "EDIT_PERMS", "ADD_MEMBER"] else discord.ButtonStyle.secondary, overlord_view=self))
        self.add_item(StateButton(label="Nodes", state="NODES", emoji="⌨️", style=discord.ButtonStyle.primary if self.state == "NODES" else discord.ButtonStyle.secondary, overlord_view=self))

# --- Overlord Components ---

class StateButton(discord.ui.Button):
    def __init__(self, label, state, emoji, style, overlord_view):
        super().__init__(label=label, emoji=emoji, style=style)
        self.target_state = state
        self.overlord_view = overlord_view
    async def callback(self, interaction: discord.Interaction):
        self.overlord_view.state = self.target_state
        container = await self.overlord_view.build_page()
        await self.overlord_view._safe_respond(interaction, container)

class TeamSelect(discord.ui.Select):
    def __init__(self, options, overlord_view):
        super().__init__(placeholder="Select a Team to manage...", options=options)
        self.overlord_view = overlord_view
    async def callback(self, interaction: discord.Interaction):
        group_id = int(self.values[0])
        self.overlord_view.selected_team = await db.permissions.get_group(group_id)
        self.overlord_view.state = "TEAM_DETAIL"
        container = await self.overlord_view.build_page()
        await self.overlord_view._safe_respond(interaction, container)

class CreateTeamButton(discord.ui.Button):
    def __init__(self, overlord_view):
        super().__init__(label="Create Team", emoji="➕", style=discord.ButtonStyle.success)
        self.overlord_view = overlord_view
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateTeamModal(self.overlord_view))

class CreateTeamModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="REGISTER SECURITY TEAM")
        self.parent_view = parent_view
        self.add_item(discord.ui.InputText(label="Team Name", placeholder="e.g. ALPHA_FORCE"))
    async def callback(self, interaction: discord.Interaction):
        name = self.children[0].value.upper()
        await db.permissions.create_group(interaction.guild_id, name)
        self.parent_view.state = "TEAMS"
        container = await self.parent_view.build_page()
        await self.parent_view._safe_respond(interaction, container)
        await interaction.followup.send(embed=EmbedFactory.toast(f"Team {name} Activated", self.parent_view.ctx), ephemeral=True)

class PermToggleSelect(discord.ui.Select):
    def __init__(self, options, overlord_view):
        super().__init__(placeholder="Toggle Permission...", options=options)
        self.overlord_view = overlord_view
    async def callback(self, interaction: discord.Interaction):
        bit = int(self.values[0])
        team = self.overlord_view.selected_team
        
        # Toggle bit
        new_bitfield = team["permissions_bitfield"] ^ bit
        await db.permissions.update_group_perms(team["id"], new_bitfield)
        
        # Refresh selected team data
        self.overlord_view.selected_team = await db.permissions.get_group(team["id"])
        container = await self.overlord_view.build_page()
        await self.overlord_view._safe_respond(interaction, container)

class MemberDeploySelect(discord.ui.Select):
    def __init__(self, select_type, placeholder, overlord_view):
        super().__init__(select_type=select_type, placeholder=placeholder, min_values=1, max_values=1)
        self.overlord_view = overlord_view
    async def callback(self, interaction: discord.Interaction):
        entity = self.values[0]
        entity_type = "ROLE" if isinstance(entity, discord.Role) else "USER"
        
        await db.permissions.add_group_member(self.overlord_view.selected_team["id"], self.overlord_view.guild_id, entity.id, entity_type)
        self.overlord_view.state = "TEAM_DETAIL"
        container = await self.overlord_view.build_page()
        await self.overlord_view._safe_respond(interaction, container)
        await interaction.followup.send(embed=EmbedFactory.toast(f"Member Deployed to {self.overlord_view.selected_team['name']}", self.overlord_view.ctx), ephemeral=True)

class DeleteTeamButton(discord.ui.Button):
    def __init__(self, overlord_view):
        super().__init__(label="Decommission Team", emoji="🗑️", style=discord.ButtonStyle.danger)
        self.overlord_view = overlord_view
    async def callback(self, interaction: discord.Interaction):
        await db.permissions.delete_group(self.overlord_view.selected_team["id"], self.overlord_view.guild_id)
        self.overlord_view.selected_team = None
        self.overlord_view.state = "TEAMS"
        container = await self.overlord_view.build_page()
        await self.overlord_view._safe_respond(interaction, container)
        await interaction.followup.send(embed=EmbedFactory.toast("Team Decommissioned", self.overlord_view.ctx), ephemeral=True)

class NodeRevokeSelect(discord.ui.Select):
    def __init__(self, options, overlord_view):
        super().__init__(placeholder="Revoke Node Protocol...", options=options)
        self.overlord_view = overlord_view
    async def callback(self, interaction: discord.Interaction):
        await db.permissions.delete_override(self.values[0], self.overlord_view.guild_id)
        container = await self.overlord_view.build_page()
        await self.overlord_view._safe_respond(interaction, container)

class NodeInjectButton(discord.ui.Button):
    def __init__(self, overlord_view):
        super().__init__(label="Inject Override", emoji="💉", style=discord.ButtonStyle.secondary)
        self.overlord_view = overlord_view
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(InjectNodeModal(self.overlord_view))

class InjectNodeModal(discord.ui.Modal):
    def __init__(self, parent_view):
        super().__init__(title="INJECT NODE OVERRIDE")
        self.parent_view = parent_view
        self.add_item(discord.ui.InputText(label="Command Node", placeholder="e.g. moderation.ban"))
        self.add_item(discord.ui.InputText(label="Required Tier", placeholder="0-3"))
    async def callback(self, interaction: discord.Interaction):
        node = self.children[0].value
        try: level = int(self.children[1].value)
        except: return await interaction.response.send_message("Invalid Tier.", ephemeral=True)
        await db.permissions.set_override(node, level, interaction.guild_id)
        container = await self.parent_view.build_page()
        await self.parent_view._safe_respond(interaction, container)
