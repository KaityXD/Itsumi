import discord
import datetime
import random
import uuid
import re
from typing import Optional

from utils.ui.fun_layout import FunLayoutView, create_fun_container
from utils.registry import registry

class RateAgainModal(discord.ui.Modal):
    def __init__(self, *args, **kwargs):
        super().__init__(title="Rate Something Else", *args, **kwargs)
        self.add_item(
            discord.ui.InputText(
                label="What else should I rate?",
                style=discord.InputTextStyle.short,
                placeholder="e.g. Pineapple on Pizza",
                required=True,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        from cogs.fun import build_rate_container
        new_thing = self.children[0].value
        container = await build_rate_container(new_thing)
        view = FunLayoutView(container)
        # Send new message instead of editing, per user request
        await interaction.response.send_message(view=view)


class AskAgainModal(discord.ui.Modal):
    def __init__(self, *args, **kwargs):
        super().__init__(title="Consult the Magic 8-Ball", *args, **kwargs)
        self.add_item(
            discord.ui.InputText(
                label="What is your new question?",
                style=discord.InputTextStyle.short,
                placeholder="e.g. Will I win the lottery?",
                required=True,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        from cogs.fun import build_8ball_container
        new_question = self.children[0].value
        container = await build_8ball_container(interaction.user, new_question)
        view = FunLayoutView(container)
        # Send new message instead of editing
        await interaction.response.send_message(view=view)


class AskAgainButton(discord.ui.Button):
    def __init__(
        self,
        is_ooc=False,
        rate_thing=None,
        is_backflip=False,
        is_roulette=False,
        is_waifu=False,
        waifu_tag=None,
        is_ship=False,
        ship_targets=None,
        action_type=None,
        target_id=None,
    ):
        self.is_ooc = is_ooc
        self.rate_thing = rate_thing
        self.is_backflip = is_backflip
        self.is_roulette = is_roulette
        self.is_waifu = is_waifu
        self.waifu_tag = waifu_tag
        self.is_ship = is_ship
        self.ship_targets = ship_targets
        self.action_type = action_type
        self.target_id = target_id

        if is_ooc:
            label = "Another One? 🎲"
        elif rate_thing:
            label = "Rate Again? ⚖️"
        elif is_backflip:
            label = "Flip Again! 🤸"
        elif is_roulette:
            label = "Pull Trigger 🔫"
        elif is_waifu:
            label = "Another Waifu? 🌸"
        elif is_ship:
            label = "Re-Ship! 🚢"
        elif action_type:
            label = f"{action_type.title()} Again! ✨"
        else:
            label = "Ask Again 🎱"

        # Using a static custom_id allows us to make this persistent across restarts!
        super().__init__(label=label, style=discord.ButtonStyle.blurple, custom_id="fun_ask_again_btn")

    async def callback(self, interaction: discord.Interaction):
        # To make this fully persistent and stateless, we check if we have instance variables.
        # If the bot restarted, the instance variables might be defaults, but we can read the message footer!
        parent_id = getattr(self.view, "view_id", None)
        
        # If parent_id is missing (bot restarted), parse it from the message embed footer
        if not parent_id and interaction.message.embeds and interaction.message.embeds[0].footer.text:
            match = re.search(r"v-id:\s*([a-zA-Z0-9-]+)", interaction.message.embeds[0].footer.text)
            if match:
                parent_id = match.group(1)

        # Fallback to identify using registry if instance vars are lost
        if not self.is_ooc and not self.rate_thing and not self.is_backflip and not self.is_roulette and not self.is_waifu and not self.is_ship and not self.action_type:
            if parent_id:
                identity = await registry.identify(parent_id)
                if identity and "data" in identity:
                    data = identity["data"]
                    title = data.get("title", "")
                    
                    if "Out of Context" in title: self.is_ooc = True
                    elif "Official Rating" in title: self.rate_thing = True
                    elif "Backflip" in title: self.is_backflip = True
                    elif "BANG" in title or "Click" in title: self.is_roulette = True
                    elif "Shipping" in title: self.is_ship = True
                    elif "8 Balls" in title: pass # Default
                    elif data.get("type") == "EMOTE":
                        self.action_type = data.get("action")
                        self.target_id = None # Requires fetching target from string, fallback to None
                    elif "Waifu" in title or "Neko" in title:
                        self.is_waifu = True
                        self.waifu_tag = "waifu"

        # Identify if we should edit or send new
        can_edit = False
        if interaction.message and interaction.message.author.id == interaction.client.user.id:
            # If it's a followup or we have permission, we could edit.
            # But let's check if the original user is the one clicking.
            if interaction.user.id == interaction.message.interaction.user.id if interaction.message.interaction else True:
                can_edit = True

        async def _deliver(view):
            if can_edit:
                await interaction.response.edit_message(view=view)
            else:
                await interaction.response.send_message(view=view)

        if self.is_ooc:
            from cogs.fun import build_ooc_container
            container = await build_ooc_container()
            view = FunLayoutView(container, parent_id=parent_id)
            await _deliver(view)
        elif self.rate_thing:
            await interaction.response.send_modal(RateAgainModal())
        elif self.is_backflip:
            cog = interaction.client.get_cog("Fun")
            container = await cog.build_backflip_container(interaction.user, guild_id=interaction.guild_id)
            view = FunLayoutView(container, parent_id=parent_id)
            await _deliver(view)
        elif self.is_roulette:
            cog = interaction.client.get_cog("Fun")
            container = await cog.build_roulette_container(interaction.user, guild_id=interaction.guild_id)
            view = FunLayoutView(container, parent_id=parent_id)
            await _deliver(view)
        elif self.is_ship:
            cog = interaction.client.get_cog("Fun")
            if self.ship_targets:
                u1_id, u2_id = self.ship_targets
                try:
                    user1 = await interaction.client.fetch_user(u1_id)
                    user2 = await interaction.client.fetch_user(u2_id)
                except:
                    return await interaction.response.send_message("One of the lovers escaped! 🏃", ephemeral=True)
            else:
                user1 = interaction.user
                user2 = interaction.user # Fallback if state lost

            container = await cog.build_ship_container(user1, user2)
            await _deliver(FunLayoutView(container, parent_id=parent_id))
        elif self.is_waifu:
            cog = interaction.client.get_cog("Fun")
            image_url = await cog._get_nb_image(self.waifu_tag or "waifu")
            container = create_fun_container(
                title=f"🌸 Your {(self.waifu_tag or 'waifu').replace('-', ' ').title()}",
                body=f"Here is another random {(self.waifu_tag or 'waifu').replace('-', ' ')}!",
                image_url=image_url,
                accessory=AskAgainButton(is_waifu=True, waifu_tag=self.waifu_tag or "waifu"),
            )
            await _deliver(FunLayoutView(container, parent_id=parent_id))
        elif self.action_type:
            cog = interaction.client.get_cog("Fun")
            target = interaction.guild.get_member(self.target_id) if interaction.guild and self.target_id else None
            
            image_url = await cog._get_nb_image(self.action_type)

            bodies = {
                "slap": f"{interaction.user.mention} just slapped {target.mention if target else 'someone'}! Ouch.",
                "hug": f"{interaction.user.mention} gives {target.mention if target else 'someone'} a big, warm hug!",
                "kiss": f"{interaction.user.mention} gives {target.mention if target else 'someone'} a sweet kiss!",
                "pat": f"{interaction.user.mention} gently pats {target.mention if target else 'someone'} on the head.",
                "bite": f"{interaction.user.mention} bit {target.mention if target else 'someone'}!",
                "cuddle": f"{interaction.user.mention} cuddles up with {target.mention if target else 'someone'}!",
                "poke": f"{interaction.user.mention} poked {target.mention if target else 'someone'}!",
                "tickle": f"{interaction.user.mention} tickled {target.mention if target else 'someone'}!",
                "wink": f"{interaction.user.mention} winks at {target.mention if target else 'someone'}!",
                "neko": "Here is another random neko for you!",
            }

            from utils.ui.embed_factory import EmbedFactory
            embed = EmbedFactory.custom(
                description=bodies.get(self.action_type, "Action done!"),
                color=discord.Color.random(),
                ctx=interaction,
                image_url=image_url
            )

            view = discord.ui.View(timeout=None)
            view.add_item(AskAgainButton(action_type=self.action_type, target_id=self.target_id))

            if can_edit:
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.response.send_modal(AskAgainModal())

class PersistentFunView(discord.ui.View):
    """Global persistent view to catch all Fun layout interactions after restart."""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(AskAgainButton())
