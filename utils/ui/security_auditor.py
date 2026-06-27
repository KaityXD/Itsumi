import discord
from typing import List, Dict, Any, Optional
from utils.database import db
from utils.permissions import PermissionLevel, PermissionManager

class SecurityAuditor:
    """
    Advanced forensic analyzer for guild security states.
    Identifies vulnerabilities, over-privileged entities, and exposed nodes.
    """

    def __init__(self, guild: discord.Guild):
        self.guild = guild

    async def run_full_audit(self) -> Dict[str, Any]:
        """Performs a comprehensive security scan of the guild."""
        return {
            "score": await self.calculate_security_score(),
            "shadow_admins": await self._find_shadow_admins(),
            "exposed_nodes": await self._find_exposed_nodes(),
            "mappings_count": len(await db.permissions.list_guild(self.guild.id)),
            "overrides_count": len(await db.permissions.list_overrides(self.guild.id)),
            "high_risk_roles": await self._find_high_risk_roles()
        }

    async def calculate_security_score(self) -> int:
        """Calculates a numerical 0-100 score representing server security."""
        score = 100
        
        # Deduct for many administrators
        admin_count = len([m for m in self.guild.members if m.guild_permissions.administrator])
        score -= min(admin_count * 2, 30)
        
        # Deduct for missing command overrides on sensitive nodes
        overrides = await db.permissions.list_overrides(self.guild.id)
        override_nodes = [r["node"] for r in overrides]
        
        critical_nodes = ["moderation.ban", "moderation.kick", "system.reload", "moderation.hardpurge"]
        for node in critical_nodes:
            if node not in override_nodes:
                score -= 10
                
        return max(0, score)

    async def _find_shadow_admins(self) -> List[discord.Member]:
        """Finds users who have high permissions but are NOT Level 3 in the bot."""
        shadows = []
        for member in self.guild.members:
            if member.bot: continue
            
            # User has Discord Admin but maybe not Bot Admin mapping
            if member.guild_permissions.administrator:
                lvl = await PermissionManager.get_user_level(member)
                if lvl < PermissionLevel.ADMINISTRATOR:
                    shadows.append(member)
        return shadows[:5]

    async def _find_exposed_nodes(self) -> List[str]:
        """Identifies critical commands that are using default (potentially loose) permissions."""
        overrides = await db.permissions.list_overrides(self.guild.id)
        override_nodes = [r["node"] for r in overrides]
        
        exposed = []
        critical_nodes = ["moderation.ban", "moderation.purge", "moderation.case.delete"]
        for node in critical_nodes:
            if node not in override_nodes:
                exposed.append(node)
        return exposed

    async def _find_high_risk_roles(self) -> List[discord.Role]:
        """Identifies roles with dangerous permissions (Manage Server, Manage Roles, etc)."""
        risky = []
        for role in self.guild.roles:
            if role.is_default(): continue
            perms = role.permissions
            if perms.administrator or perms.manage_guild or perms.manage_roles:
                risky.append(role)
        return risky[:5]

    async def resolve_effective_level(self, entity: discord.Member | discord.Role) -> int:
        """Calculates the absolute resolved permission level for any entity."""
        if isinstance(entity, discord.Member):
            return await PermissionManager.get_user_level(entity)
        else:
            return await db.permissions.get_level(entity.id, self.guild.id)
