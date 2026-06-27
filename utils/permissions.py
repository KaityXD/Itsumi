import discord
from discord.ext import commands
from typing import Optional, Union, List, Dict

from .database import db

class SecPerm:
    """Granular Bitfield Permissions for the Overlord Engine."""
    NONE            = 0
    
    # --- Basic Access ---
    USE_COMMANDS    = 1 << 0
    VIEW_STATS      = 1 << 1
    
    # --- Moderation Suite ---
    MOD_WARN        = 1 << 2
    MOD_KICK        = 1 << 3
    MOD_TIMEOUT     = 1 << 4
    MOD_BAN         = 1 << 5
    MOD_CASE_EDIT   = 1 << 6
    MOD_CASE_DELETE = 1 << 7
    MOD_PURGE       = 1 << 8
    
    # --- Management Suite ---
    MANAGE_TAGS     = 1 << 9
    MANAGE_PERMS    = 1 << 10
    MANAGE_SETTINGS = 1 << 11
    
    # --- System & Forensics ---
    VIEW_FORENSICS  = 1 << 12
    SYSTEM_RELOAD   = 1 << 13
    SYSTEM_ERRORS   = 1 << 14
    
    # --- Administrative ---
    ADMINISTRATOR   = 1 << 15  # Implicitly grants all lower perms
    BYPASS_FILTERS  = 1 << 16
    ROOT_ACCESS     = 1 << 17  # Bot Owner only

    LABELS = {
        USE_COMMANDS: "Use Commands",
        VIEW_STATS: "View Stats",
        MOD_WARN: "Issue Warnings",
        MOD_KICK: "Kick Members",
        MOD_TIMEOUT: "Timeout Members",
        MOD_BAN: "Ban Members",
        MOD_CASE_EDIT: "Edit Cases",
        MOD_CASE_DELETE: "Delete Cases",
        MOD_PURGE: "Purge Messages",
        MANAGE_TAGS: "Manage Tags",
        MANAGE_PERMS: "Manage Permissions",
        MANAGE_SETTINGS: "Manage Settings",
        VIEW_FORENSICS: "View Forensics",
        SYSTEM_RELOAD: "Reload Extensions",
        SYSTEM_ERRORS: "View Error Logs",
        ADMINISTRATOR: "Full Administrator",
        ROOT_ACCESS: "System Root"
    }

class PermissionLevel:
    """Legacy tier mapping for backward compatibility during migration."""
    EVERYONE = 0
    HELPER = 1
    MODERATOR = 2
    ADMINISTRATOR = 3
    BOT_OWNER = 4

    LABELS = {
        0: "Everyone 👤",
        1: "Helper 🎗️",
        2: "Moderator 🛡️",
        3: "Administrator 👑",
        4: "Bot Owner 🛠️"
    }

class PermissionManager:
    """
    Overlord Security Engine (v5).
    Resolves permissions based on Security Groups, role hierarchies, and bitfields.
    """

    @staticmethod
    async def get_user_permissions(user: Union[discord.Member, discord.User]) -> int:
        """Determines the absolute permission bitfield for a user."""
        # 1. Root Bypass
        from config import config
        owners = getattr(config, "OWNERS", [])
        if user.id in owners:
            return SecPerm.ROOT_ACCESS | SecPerm.ADMINISTRATOR | 0xFFFFF

        if isinstance(user, discord.User) or not user.guild:
            return SecPerm.USE_COMMANDS | SecPerm.VIEW_STATS

        guild_id = user.guild.id
        resolved_perms = SecPerm.NONE

        # 2. Check Security Groups (New v5 System)
        # This will be implemented fully once the DB tables are migrated.
        # For now, we map legacy levels to bitfields.
        
        legacy_level = await PermissionManager.get_user_level(user)
        
        if legacy_level >= 1: # Helper
            resolved_perms |= SecPerm.USE_COMMANDS | SecPerm.VIEW_STATS | SecPerm.MOD_WARN
        if legacy_level >= 2: # Moderator
            resolved_perms |= SecPerm.MOD_KICK | SecPerm.MOD_TIMEOUT | SecPerm.MOD_BAN | SecPerm.MOD_PURGE | SecPerm.MOD_CASE_EDIT
        if legacy_level >= 3: # Admin
            resolved_perms |= SecPerm.ADMINISTRATOR | SecPerm.MANAGE_TAGS | SecPerm.MANAGE_PERMS | SecPerm.MANAGE_SETTINGS | SecPerm.VIEW_FORENSICS | SecPerm.SYSTEM_ERRORS

        return resolved_perms

    @staticmethod
    async def get_user_level(user: Union[discord.Member, discord.User]) -> int:
        """Legacy resolver for backward compatibility."""
        from config import config
        owners = getattr(config, "OWNERS", [])
        if user.id in owners:
            return PermissionLevel.BOT_OWNER

        if isinstance(user, discord.User) or not user.guild:
            return PermissionLevel.EVERYONE

        guild_id = user.guild.id
        user_level = await db.permissions.get_level(user.id, guild_id)
        
        role_levels = []
        for role in user.roles:
            role_levels.append(await db.permissions.get_level(role.id, guild_id))
        
        if user.guild_permissions.administrator:
            role_levels.append(PermissionLevel.ADMINISTRATOR)

        return max(user_level, *role_levels, PermissionLevel.EVERYONE)

    @staticmethod
    async def has_perm(user: discord.Member, permission: int) -> bool:
        """Checks if a user has a specific bitfield permission."""
        user_perms = await PermissionManager.get_user_permissions(user)
        
        if user_perms & SecPerm.ROOT_ACCESS: return True
        if user_perms & SecPerm.ADMINISTRATOR: return True
        
        return (user_perms & permission) == permission

    @staticmethod
    async def check_permissions(ctx: discord.ApplicationContext, required_level: int = None) -> bool:
        """Global check logic used by decorators."""
        # For now, we still use legacy levels for the global check to prevent breaking cogs
        # but we will migrate commands to use specific bitfields soon.
        
        user_level = await PermissionManager.get_user_level(ctx.author)
        
        # If a specific level is provided (legacy decorator use)
        if required_level is not None:
            if user_level >= required_level:
                return True
            raise commands.CheckFailure(
                f"Insufficient Permissions!\n"
                f"Required: **{PermissionLevel.LABELS.get(required_level)}**\n"
                f"Your Level: **{PermissionLevel.LABELS.get(user_level)}**"
            )

        # Default command node resolution
        node = f"{ctx.cog.qualified_name.lower() if ctx.cog else 'global'}.{ctx.command.name}"
        req = await db.permissions.get_override(node, ctx.guild_id or 0)
        
        if req is None:
            # Hardcoded fallbacks
            defaults = {
                "system.developer": PermissionLevel.BOT_OWNER,
                "system.stats": PermissionLevel.EVERYONE,
                "moderation": PermissionLevel.MODERATOR,
            }
            category = node.split(".")[0]
            req = defaults.get(node, defaults.get(category, PermissionLevel.EVERYONE))

        if user_level >= req:
            return True

        raise commands.CheckFailure(f"This command requires **Tier {req}** access.")

def has_level(level: int):
    async def predicate(ctx: discord.ApplicationContext):
        return await PermissionManager.check_permissions(ctx, required_level=level)
    return commands.check(predicate)

# Global singleton
perms = PermissionManager()
