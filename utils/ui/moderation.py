import discord
import random
from utils.database import db
from utils.ui.embed_factory import EmbedFactory
from utils.ui.fun_layout import FunLayoutView, create_fun_container

# --- User Facing Verification Flow ---

async def grant_verification(interaction: discord.Interaction):
    role_id = await db.settings.get("verify_role_id", guild_id=interaction.guild_id)
    if not role_id:
        return await interaction.response.send_message("❌ Verification system is unconfigured.", ephemeral=True)
    
    role = interaction.guild.get_role(int(role_id))
    if not role:
        return await interaction.response.send_message("❌ Verified role no longer exists.", ephemeral=True)

    if role in interaction.user.roles:
        return await interaction.response.send_message(embed=EmbedFactory.toast("You are already verified!", interaction, success=False), ephemeral=True)

    try:
        await interaction.user.add_roles(role, reason="Passed Verification")
        await interaction.response.send_message(embed=EmbedFactory.toast("Successfully verified! Access granted.", interaction), ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(embed=EmbedFactory.error("Error", "I do not have permission to assign the verified role.", ctx=interaction), ephemeral=True)

class RuleAgreementModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Rule Agreement")
        self.add_item(
            discord.ui.InputText(
                label="Type 'I agree' to proceed",
                placeholder="I agree",
                min_length=7,
                max_length=15,
                required=True
            )
        )

    async def callback(self, interaction: discord.Interaction):
        answer = self.children[0].value.lower().strip()
        if answer == "i agree":
            await grant_verification(interaction)
        else:
            await interaction.response.send_message(embed=EmbedFactory.error("Failed", "You did not type exactly 'I agree'.", ctx=interaction), ephemeral=True)

class MathCaptchaModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Math Captcha")
        self.num1 = random.randint(1, 10)
        self.num2 = random.randint(1, 10)
        self.answer = self.num1 + self.num2
        
        self.add_item(
            discord.ui.InputText(
                label=f"What is {self.num1} + {self.num2}?",
                placeholder="Enter the number...",
                min_length=1,
                max_length=5,
                required=True
            )
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            user_ans = int(self.children[0].value.strip())
            if user_ans == self.answer:
                await grant_verification(interaction)
            else:
                await interaction.response.send_message(embed=EmbedFactory.error("Failed", "Incorrect math answer. Try again.", ctx=interaction), ephemeral=True)
        except ValueError:
            await interaction.response.send_message(embed=EmbedFactory.error("Failed", "Please enter a valid number.", ctx=interaction), ephemeral=True)

class VerificationPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify Now", style=discord.ButtonStyle.success, emoji="✅", custom_id="verify_persistent_btn")
    async def verify_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        mode = await db.settings.get("verify_mode", guild_id=interaction.guild_id) or "button"

        if mode == "button":
            await grant_verification(interaction)
        elif mode == "rules":
            await interaction.response.send_modal(RuleAgreementModal())
        elif mode == "math":
            await interaction.response.send_modal(MathCaptchaModal())

# --- Setup Wizard ---

class WizardCustomizeModal(discord.ui.Modal):
    def __init__(self, wizard_view):
        super().__init__(title="Customize Verification Embed")
        self.wizard = wizard_view
        
        self.add_item(discord.ui.InputText(
            label="Embed Title", 
            value=self.wizard.custom_title, 
            required=True
        ))
        self.add_item(discord.ui.InputText(
            label="Embed Description", 
            style=discord.InputTextStyle.long, 
            value=self.wizard.custom_desc, 
            required=True
        ))
        self.add_item(discord.ui.InputText(
            label="Embed Color (Hex)", 
            value=self.wizard.custom_color, 
            required=True, 
            max_length=7
        ))

    async def callback(self, interaction: discord.Interaction):
        self.wizard.custom_title = self.children[0].value
        self.wizard.custom_desc = self.children[1].value
        self.wizard.custom_color = self.children[2].value
        
        await self.wizard.update_message(interaction)

class WizardRoleSelect(discord.ui.Select):
    def __init__(self, wizard):
        super().__init__(
            select_type=discord.ComponentType.role_select,
            placeholder="Select Verified Role...", 
            min_values=1, 
            max_values=1, 
            row=0
        )
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.wizard.owner_id:
            return await interaction.response.send_message("❌ This is not your setup wizard.", ephemeral=True)
        self.wizard.role_id = self.values[0].id
        await self.wizard.update_message(interaction)

class WizardModeSelect(discord.ui.Select):
    def __init__(self, wizard):
        options = [
            discord.SelectOption(label="Button", description="Simple click to verify", value="button", emoji="🔘"),
            discord.SelectOption(label="Rule Agreement", description="Must type 'I agree'", value="rules", emoji="📜"),
            discord.SelectOption(label="Math Captcha", description="Solve simple math", value="math", emoji="🧮")
        ]
        super().__init__(placeholder="Select Verification Mode...", min_values=1, max_values=1, options=options, row=0)
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.wizard.owner_id:
            return await interaction.response.send_message("❌ This is not your setup wizard.", ephemeral=True)
        self.wizard.mode = self.values[0]
        await self.wizard.update_message(interaction)

class WizardChannelSelect(discord.ui.Select):
    def __init__(self, wizard):
        super().__init__(
            select_type=discord.ComponentType.channel_select,
            channel_types=[discord.ChannelType.text],
            placeholder="Select Deployment Channel...", 
            min_values=1, 
            max_values=1, 
            row=0
        )
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.wizard.owner_id:
            return await interaction.response.send_message("❌ This is not your setup wizard.", ephemeral=True)
        self.wizard.deploy_channel_id = self.values[0].id
        await self.wizard.update_message(interaction)

class VerifyWizardView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=900) # 15 minutes timeout
        self.ctx = ctx
        self.owner_id = ctx.author.id
        self.step = 1
        
        self.role_id = None
        self.mode = "button"
        self.deploy_channel_id = None
        self.custom_title = "🛡️ Server Verification"
        self.custom_desc = "Welcome! Please click the button below to verify your account and gain access to the server."
        self.custom_color = "#57F287"

    async def initialize(self):
        """Asynchronously loads initial settings from the database."""
        guild_id = self.ctx.guild_id
        
        role_id = await db.settings.get("verify_role_id", guild_id=guild_id)
        self.role_id = int(role_id) if role_id else None
        
        self.mode = await db.settings.get("verify_mode", guild_id=guild_id) or "button"
        
        deploy_channel_id = await db.settings.get("verify_channel_id", guild_id=guild_id)
        self.deploy_channel_id = int(deploy_channel_id) if deploy_channel_id else None

        self.custom_title = await db.settings.get("verify_panel_title", guild_id=guild_id) or self.custom_title
        self.custom_desc = await db.settings.get("verify_panel_desc", guild_id=guild_id) or self.custom_desc
        self.custom_color = await db.settings.get("verify_panel_color", guild_id=guild_id) or self.custom_color

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ You cannot interact with this setup wizard.", ephemeral=True)
            return False
        return True

    async def build_current_step(self):
        self.clear_items()
        
        # Navigation Buttons
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌", row=2)
        cancel_btn.callback = self.on_cancel
        
        back_btn = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, emoji="⬅️", row=2)
        back_btn.callback = self.on_back
        if self.step == 1: back_btn.disabled = True

        next_btn = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, emoji="➡️", row=2)
        next_btn.callback = self.on_next
        
        title = ""
        body = ""

        if self.step == 1:
            title = "⚙️ Verification Setup [1/4]: Target Role"
            body = "Select the role that users will receive upon successfully verifying."
            
            if self.role_id:
                body += f"\n\n**Current Selection:** <@&{self.role_id}>"
            else:
                next_btn.disabled = True
                
            self.add_item(WizardRoleSelect(self))
            self.add_item(cancel_btn)
            self.add_item(next_btn)

        elif self.step == 2:
            title = "⚙️ Verification Setup [2/4]: Security Level"
            body = "How do you want users to verify?"
            
            mode_names = {"button": "🔘 Button Click", "rules": "📜 Rule Agreement", "math": "🧮 Math Captcha"}
            body += f"\n\n**Current Selection:** `{mode_names.get(self.mode, self.mode)}`"
            
            self.add_item(WizardModeSelect(self))
            self.add_item(back_btn)
            self.add_item(cancel_btn)
            self.add_item(next_btn)

        elif self.step == 3:
            title = "⚙️ Verification Setup [3/4]: Deployment Channel"
            body = "Select a channel where the persistent verification panel will be deployed."
            
            if self.deploy_channel_id:
                body += f"\n\n**Current Selection:** <#{self.deploy_channel_id}>"
            else:
                next_btn.disabled = True
                
            self.add_item(WizardChannelSelect(self))
            self.add_item(back_btn)
            self.add_item(cancel_btn)
            self.add_item(next_btn)

        elif self.step == 4:
            title = "⚙️ Verification Setup [4/4]: Aesthetics & Summary"
            mode_names = {"button": "🔘 Button Click", "rules": "📜 Rule Agreement", "math": "🧮 Math Captcha"}
            
            body = (
                f"Almost done! Review your settings below.\n\n"
                f"**Role:** <@&{self.role_id}>\n"
                f"**Channel:** <#{self.deploy_channel_id}>\n"
                f"**Mode:** `{mode_names.get(self.mode, self.mode)}`\n\n"
                f"**Message Preview:**\n"
                f"> **{self.custom_title}**\n> {self.custom_desc}\n> *Color: {self.custom_color}*"
            )

            edit_btn = discord.ui.Button(label="Edit Message", style=discord.ButtonStyle.primary, emoji="✏️", row=2)
            edit_btn.callback = self.on_edit_message
            
            deploy_btn = discord.ui.Button(label="Deploy Verification", style=discord.ButtonStyle.success, emoji="🚀", row=2)
            deploy_btn.callback = self.on_deploy

            self.add_item(back_btn)
            self.add_item(edit_btn)
            self.add_item(deploy_btn)

        return create_fun_container(title=title, body=body, interaction=self.ctx)

    async def update_message(self, interaction: discord.Interaction):
        container = await self.build_current_step()
        await interaction.response.edit_message(view=FunLayoutView(container, original_view=self))

    async def on_next(self, interaction: discord.Interaction):
        self.step += 1
        await self.update_message(interaction)

    async def on_back(self, interaction: discord.Interaction):
        self.step -= 1
        await self.update_message(interaction)
        
    async def on_cancel(self, interaction: discord.Interaction):
        for item in self.children: item.disabled = True
        container = create_fun_container(title="❌ Setup Cancelled", body="The verification setup wizard was cancelled.", color=discord.Color.red())
        await interaction.response.edit_message(view=FunLayoutView(container, original_view=self))
        self.stop()

    async def on_edit_message(self, interaction: discord.Interaction):
        await interaction.response.send_modal(WizardCustomizeModal(self))

    async def on_deploy(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        
        # Save all settings to DB
        await db.settings.set("verify_role_id", str(self.role_id), guild_id=guild_id)
        await db.settings.set("verify_mode", self.mode, guild_id=guild_id)
        await db.settings.set("verify_channel_id", str(self.deploy_channel_id), guild_id=guild_id)
        await db.settings.set("verify_panel_title", self.custom_title, guild_id=guild_id)
        await db.settings.set("verify_panel_desc", self.custom_desc, guild_id=guild_id)
        await db.settings.set("verify_panel_color", self.custom_color, guild_id=guild_id)

        channel = interaction.guild.get_channel(self.deploy_channel_id)
        if not channel:
            return await interaction.response.send_message("❌ Invalid channel configured. Did it get deleted?", ephemeral=True)

        try:
            color = discord.Color(int(self.custom_color.lstrip("#"), 16))
        except:
            color = discord.Color.brand_green()

        embed = EmbedFactory.custom(
            title=self.custom_title,
            description=self.custom_desc,
            color=color,
            ctx=interaction,
            footer="Verification System"
        )

        await channel.send(embed=embed, view=VerificationPanelView())
        
        for item in self.children: item.disabled = True
        container = create_fun_container(title="✅ Deployment Complete", body=f"Verification panel successfully deployed to {channel.mention}!", color=discord.Color.green())
        await interaction.response.edit_message(view=FunLayoutView(container, original_view=self))
        self.stop()
