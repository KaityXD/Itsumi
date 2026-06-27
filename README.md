# 🌸 Itsumi-pycord

<p align="center">
  <img src="https://raw.githubusercontent.com/Pycord-Development/pycord/master/assets/pycord_logo.png" width="120" alt="Pycord Logo">
  <br>
  <b>A modern, high-infrastructure Discord bot built for massive scale, deep forensics, and chaotic fun.</b>
  <br>
  <i>"High-signal engineering meets chaotic intent."</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Library-Pycord_2.6+-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Pycord">
  <img src="https://img.shields.io/badge/Database-aiosqlite-lightgrey?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Infrastructure-V2-brightgreen?style=for-the-badge" alt="Infrastructure V2">
</p>

---

## 🏗️ The Universal Infrastructure V2 (Automated)

Itsumi isn't just another Discord bot; it's a forensic-ready engine. Every interaction, every message, and every error is tracked through a sophisticated identification system that is **100% automated**.

### 🔍 Automated Forensic Tracking
*   **`v-id` (View ID)**: Tracks every UI component and command execution. Persistent across bot restarts.
*   **`r-id` (Response ID)**: Injected into the footer of every bot response. Allows instant lookup of the exact data snapshot used to generate that message.
*   **`e-id` (Error ID)**: Unique fingerprints for crashes, allowing developers to perform instant post-mortems via `/dev inspect`.
*   **`run-id` (Task ID)**: Monitors the health and execution of background maintenance loops.

### ⚡ High-Performance Backend
*   **Async Everything**: Powered by `aiosqlite` and `uvloop` for non-blocking, lightning-fast operations.
*   **Consolidated Storage**: A single, heavily indexed SQLite database manages guild settings, moderation cases, and forensic snapshots.
*   **Smart Caching**: Repository patterns in `utils/database.py` ensure high-speed access to frequently used data without redundant I/O.

---

## 🎨 Feature Showcase

### 🎭 Modern Components V2 (DesignerView)
Itsumi utilizes Pycord's latest `DesignerView` and `Container` systems to provide a sleek, professional UI that feels like a native part of Discord.

### 🛡️ Advanced Moderation & Security
*   **Deep Case History**: Every action (Warn, Kick, Ban, Timeout) is a numbered case with persistent metadata.
*   **Overlord Security SOC**: A central dashboard for managing permissions and server security operations.
*   **Verification System**: A multi-mode, interactive wizard for protecting your server from raids and bots.
*   **Forensic Auditing**: Real-time logging of message edits, deletions, and member events with `v-id` cross-referencing.

### 🎡 Chaotic Fun & Minigames
*   **Social Emotes**: Interactive actions (`/emote slap`, `/emote hug`) with random high-quality anime imagery.
*   **Backflip & Roulette**: Database-backed minigames with personal bests and global survival statistics.
*   **Anime Intelligence**: Integrated tools for tracing anime scenes from screenshots, fetching quotes, and random waifus.

---

## 🛠️ Developer's Guide

### Creating Forensic-Ready Features
Itsumi's global automation means you don't have to manually register IDs. Simply use standard Pycord methods, and the infrastructure does the rest.

```python
@discord.slash_command(name="ping")
async def ping(self, ctx):
    # Automation automatically injects 'r-id' into the footer
    await ctx.respond(f"Pong! `{self.bot.latency * 1000:.0f}ms`")
```

### Working with the Database
Use the `db` singleton for all persistent operations.

```python
from utils.database import db

# Get a setting
val = await db.settings.get("my_key", guild_id=ctx.guild.id)

# Set a setting
await db.settings.set("my_key", "my_value", guild_id=ctx.guild.id)
```

---

## 🚀 Deployment & Maintenance

Itsumi is designed for low-maintenance, high-uptime environments.

*   **Automated Maintenance**: Daily log rotation, retention enforcement, and database backups are handled by background tasks.
*   **Hot-Reloading**: Apply code changes to specific cogs or the global config without dropping shards using `/dev reload`.
*   **Deep Inspection**: Use `/dev inspect <id>` to debug any active or archived component instantly.

### Prerequisites
*   Python 3.10+
*   Pycord 2.6.0+
*   An active Discord Bot Token

---
<p align="center">
  <i>Created with chaotic intent and high-signal engineering by <b>Kazehara KaiTy</b>.</i>
</p>
