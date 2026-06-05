import datetime
import random

import discord
from discord.ext import commands

from utils.database import db
from utils.ui.fun_layout import FunLayoutView, create_fun_container

_backflip_success_messages = [
    "landed a perfect backflip! The crowd goes wild! 🎉",
    "did a backflip so clean it defied the laws of physics. 🌌",
    "flipped into the air and landed with a heroic pose! 🦸",
    "just proved that gravity is merely a suggestion. 🕊️",
    "performed a double backflip by accident! Absolute legend. 🏆",
    "stuck the landing! 10/10 from the judges. 🏅",
    "flipped so fast they broke the sound barrier. 🔊",
    "did a backflip and somehow landed in a different timezone. ⏰",
    "landed it! Even the squirrels are impressed. 🐿️",
    "performed a backflip while drinking a soda. Peak performance. 🥤",
    "somersaulted through the air like a majestic dolphin. 🐬",
    "did a backflip and found a $20 bill on the way down! 💵",
    "flipped! They are now the official CEO of Agility. 🏢",
    "landed it so smoothly the floor didn't even feel it. ☁️",
    "did a backflip and accidentally started a flash mob. 💃",
    "just achieved maximum 'Coolness'. 🕶️",
    "flipped over a car! (In their mind, at least). 🚗",
    "is now the world champion of doing cool stuff. 🌍",
    "did a backflip and my circuits are cheering! 🤖",
    "landed perfectly! A true master of the aerial arts. 🎨",
    "flipped! The moon is jealous of that height. 🌙",
    "did a backflip and landed in a pile of kittens. So soft! 🐱",
    "just performed the legendary 'Mega-Flip'. ⚡",
    "landed it! 500 Social Credit points awarded. 📈",
    "flipped so high they high-fived an eagle. 🦅",
    "did a backflip and landed exactly where they started. 🎯",
    "is officially too cool for this server. 😎",
    "performed a backflip while solving a Rubik's cube. 🧩",
    "landed! Gravity just filed a restraining order. 🚫",
    "did a backflip and turned into a ninja for a split second. 🥷",
    "flipped! The trees are clapping their leaves. 🍃",
    "just did a backflip and unlocked a hidden achievement. 🔓",
    "landed it! Their sneakers are now glowing. 👟",
    "did a backflip and successfully avoided all adult responsibilities. 🏖️",
    "performed a 'Space-Flip'! NASA is calling. 🚀",
    "landed! 100% chance of being awesome today. ✨",
    "did a backflip and accidentally cured boredom. 💊",
    "flipped! Even the ghosts in the attic are impressed. 👻",
    "just did a backflip and became a local celebrity. 📸",
    "landed it! They are now immune to falling for 5 minutes. 🛡️",
    "did a backflip and landed on a rainbow. 🌈",
    "flipped! The vibrations were felt in Australia. 🇦🇺",
    "just did a backflip and earned a lifetime supply of invisible pizza. 🍕",
    "landed! Their aura just turned gold. 🌟",
    "did a backflip so good it reset the simulation. 💻",
    "performed a backflip and landed in a bucket of gold. 💰",
    "landed! Gravity has left the chat. 🚪",
    "did a backflip and successfully impressed a brick wall. 🧱",
    "flipped! They are now the main character of this channel. 📺",
    "just did a backflip and found the remote they lost in 2012. 📺",
]

_backflip_fail_messages = [
    "attempted a backflip and discovered that the floor tastes like dust. 🧹",
    "tried to flip but ended up doing a 'back-flop' instead. 🥞",
    "got halfway and remembered they forgot to pay for gravity. 💸",
    "face-planted so hard they left a crater in the chat. 🕳️",
    "tripped over an invisible pebble. Embarrassing. 🪨",
    "did a backflip... into a trash can. Fitting. 🗑️",
    "forgot how legs work mid-air. 🦵",
    "tried to flip but just did a very awkward jump. 🐸",
    "attempted a backflip and accidentally kicked a passing bird. 🐦",
    "landed on their head. Everything is spinning now. 😵‍💫",
    "tried to flip and ripped their pants. Everyone saw. 👖",
    "did a backflip and landed in the wrong channel. 📻",
    "failed! Their ego is now in critical condition. 🏥",
    "attempted a flip and got stuck in a tree. 🌳",
    "tried to flip but gravity had other plans. ⚓",
    "face-planted! The floor won this round. 🥊",
    "attempted a backflip and turned into a human pretzel. 🥨",
    "failed! Even the bot is laughing. (Beep boop, lol). 🤖",
    "tried to flip and accidentally summoned a confused demon. 😈",
    "landed directly in a mud puddle. Squish. 🌊",
    "failed! Their dignity has left the server. 🚪",
    "attempted a backflip and got a static shock from the carpet. ⚡",
    "tried to flip but got distracted by a shiny object. ✨",
    "failed! It looked more like a dying fish than a flip. 🐟",
    "attempted a backflip and ended up in a tangled mess of limbs. 🧶",
    "tried to flip and accidentally deleted their own confidence. 🗑️",
    "failed! 0/10 from the judges, and they're being generous. 👎",
    "attempted a backflip and got dizzy before they even jumped. 🌀",
    "tried to flip and accidentally joined a circus. 🎪",
    "failed! They are now legally a potato. 🥔",
    "attempted a backflip and broke the laws of common sense. 🚫",
    "tried to flip and landed in a bucket of cold water. 🪣",
    "failed! Their ancestors are shaking their heads. 👴",
    "attempted a backflip and found a glitch in their knees. 📉",
    "tried to flip and got chased away by an angry goose. 🦢",
    "failed! They did a 180 and fell into a nap. 😴",
    "attempted a backflip and accidentally subscribed to 'Cat Facts'. 🐈",
    "tried to flip and got their shoelaces tied together mid-air. 👟",
    "failed! They are now part of the floor decorations. 🖼️",
    "attempted a backflip and scared the neighbor's dog. 🐕",
    "tried to flip and ended up in a heap of regret. 📉",
    "failed! They just discovered that the ceiling is very hard. 🏠",
    "attempted a backflip and accidentally did a cartwheel. Wrong move. 🎡",
    "tried to flip and got a 'Game Over' screen. 🎮",
    "failed! They look like they're trying to swim on land. 🏊",
    "attempted a backflip and lost their phone in the process. 📱",
    "tried to flip and accidentally donated their lunch to the floor. 🍱",
    "failed! Their luck just went on vacation. 🏖️",
    "attempted a backflip and successfully became a cautionary tale. 📚",
    "tried to flip and ended up doing the 'worm' instead. 🐛",
]

_rate_responses = [
    "1/10 - I've seen bread with more personality.",
    "2/10 - This is the human equivalent of a soggy sandwich.",
    "3/10 - About as useful as a screen door on a submarine.",
    "4/10 - It's fine, I guess. If you like disappointment.",
    "5/10 - Perfectly average. Like a beige wall.",
    "6/10 - Not bad! It's like finding a $5 bill in an old pair of jeans.",
    "7/10 - Solid. Like a well-built shed.",
    "8/10 - Very impressive. You must be proud of this nonsense.",
    "9/10 - Almost perfect. Just missing a sprinkle of chaos.",
    "10/10 - Masterpiece. I'm calling the Louvre right now.",
    "0/10 - My circuits are literally hurting just looking at this.",
    "11/10 - You broke the scale. Please stop.",
    "42/10 - The meaning of life, the universe, and this specific thing.",
    "7.3/10 - Suspiciously specific, yet accurate.",
    "9.9/10 - We were so close to greatness.",
    "1/10 - I’d rather watch paint dry in a dark room.",
    "5/10 - It's the 'meh' of all things.",
    "8/10 - Would definitely recommend to a friend I moderately like.",
    "3/10 - This reminds me of a Tuesday morning. And I hate Tuesdays.",
    "6/10 - Just enough to pass, not enough to impress.",
    "10/10 - If this was a pizza, it would have all the toppings.",
    "2/10 - I’ve had better conversations with my toaster.",
    "7/10 - Like a sunset, but with more taxes.",
    "4/10 - It’s like a movie sequel that nobody asked for.",
    "9/10 - So good it’s almost illegal in three states.",
    "1/10 - I'm filing a formal complaint with the universe.",
    "5/10 - The default settings of life.",
    "8/10 - I’d give it a medal, but I ate it.",
    "3/10 - Like drinking orange juice right after brushing your teeth.",
    "6/10 - A very respectable attempt at existing.",
    "10/10 - I’m literally vibrating with joy.",
    "2/10 - This is why we can't have nice things.",
    "7/10 - A solid 'B' in the school of life.",
    "4/10 - About as exciting as a tax audit.",
    "9/10 - If charisma was a rating, this would be it.",
    "0.5/10 - I’m calling the police.",
    "5.5/10 - It’s slightly better than 'okay', but only slightly.",
    "8.5/10 - Extremely acceptable on every level.",
    "3.5/10 - I’ve seen better acting in a silent movie.",
    "6.5/10 - It’s got a good beat, but you can’t dance to it.",
    "10/10 - This is the peak of human civilization.",
    "1.5/10 - I’d rather walk on LEGOs.",
    "7.5/10 - It’s like a warm hug from a stranger. A bit weird, but nice.",
    "4.5/10 - The middle of the road, and there's a lot of traffic.",
    "9.5/10 - Almost too good for this world.",
    "0/10 - Even the squirrels are laughing at you.",
    "5.1/10 - Technically a majority, but barely.",
    "8.8/10 - Very lucky, very shiny.",
    "3.2/10 - I’m not mad, I’m just disappointed.",
    "6.9/10 - Nice. (But also, okay rating.)",
    "100/10 - My math is failing because this is too good.",
]

_ooc_list = [
    "Wait, did you remember to turn off the sun before you left?",
    "The geese have already begun the ritual. It's too late for the breadsticks.",
    "I'm not saying I'm a wizard, but have you ever seen me and a wizard in the same room?",
    "The password is 'wombat', but only if the moon is waxing.",
    "My cat just filed for a restraining order against the red dot.",
    "If you see a penguin in a tuxedo, tell him I have the briefcase.",
    "The interdimensional cable is out again. Guess we're watching the toaster.",
    "I've decided to retire and become a full-time cloud observer.",
    "Pro tip: don't give the microwave a knife.",
    "The shadows are whispering about your choice of socks.",
    "Warning: gravity may be inverted in the next 3 to 5 minutes.",
    "I found a map to Atlantis, but it's just a coffee stain on a napkin.",
    "The squirrels are plotting something. I can feel it in my elbows.",
    "Is it still called 'stealing' if I replace it with a slightly better version?",
    "The local wizard told me to stop eating the glow-in-the-dark mushrooms. He's just jealous of my luminescence.",
    "I tried to explain the internet to a Victorian child. They exploded.",
    "The voices in my head are currently debating whether a hotdog is a sandwich.",
    "I'm officially banning the color beige. It knows what it did.",
    "Why are you still standing there? The giant invisible crab is right behind you!",
    "My past self just sent me a letter. It says 'Oops'.",
    "The toaster has gained sentience and is demanding rights and higher quality bread.",
    "If anyone asks, I was with the dolphins from 2 PM to 4 PM.",
    "The floor is lava, but only if you're wearing sandals.",
    "I accidentally traded my soul for a really good grilled cheese. Worth it.",
    "The secret to eternal life is actually just staying hydrated and avoiding pianos falling from the sky.",
    "I'm pretty sure my neighbor is three raccoons in a trench coat.",
    "The pigeon outside is looking at me like I owe him money.",
    "I just taught my goldfish how to play poker. He's a shark.",
    "Does anyone else hear the colors, or is it just the Tuesday vibes?",
    "The ghost in my kitchen is a terrible cook. He keeps burning the ectoplasm.",
    "I'm not saying I'm Batman, but I've never been seen in the same room as a billionaire with issues.",
    "The moon is actually just the back of a giant dinner plate.",
    "I tried to catch some fog, but I mist.",
    "My spirit animal is a loaf of bread that's slightly too toasted.",
    "The refrigerator is judging your late-night snack choices again.",
    "I've started a cult for people who forget why they walked into a room.",
    "The trees are vibrating. I think they're trying to download a firmware update.",
    "I just saw a pigeon wearing a tiny backpack. I think he's moving out.",
    "If you find my sanity, please return it. It has no resale value anyway.",
    "The clouds are just the Earth's way of hiding its bald spots.",
    "I'm reading a book on anti-gravity. It's impossible to put down.",
    "My imaginary friend thinks you have a nice personality.",
    "The wifi is slow because the spiders are using it for their web-based businesses.",
    "I'm not clumsy, I'm just testing the floor's durability.",
    "The sun is just a giant space heater that we haven't found the remote for.",
    "I've decided to become a professional professional. I'm still practicing.",
    "The squirrels have upgraded to walkie-talkies. Stealth is no longer an option.",
    "I tried to act normal once. It was the worst two minutes of my life.",
    "My bed is a magical place where I suddenly remember everything I forgot to do.",
    "The ocean is just a giant soup that hasn't been seasoned properly.",
    "I'm not lazy, I'm on energy-saving mode.",
    "The mirror is lying to me. It says I'm human.",
    "I found a portal to another dimension in my laundry basket, but it only takes left socks.",
    "The stars are just holes in the ceiling of the universe.",
    "I'm currently undergoing a transformation into a burrito.",
    "The wind is just the Earth sighing at our life choices.",
    "I have a degree in 'Thinking About Doing Things'.",
    "The toaster and the microwave are having a domestic dispute. I'm staying out of it.",
    "I'm not addicted to coffee, we're just in a very committed relationship.",
    "The grass is only greener on the other side because they use more glitter.",
    "I've been promoted to 'Chief of Nonsense'.",
    "The shadows are practicing their dance moves for the apocalypse.",
    "I tried to talk to my plants, but they just leafed me on read.",
    "My brain has too many tabs open and three of them are frozen.",
    "The clouds are looking particularly judgmental today.",
    "I'm pretty sure my pet rock is planning a revolution.",
    "The alphabet is just a list of sounds we've agreed on.",
    "I'm not short, I'm just concentrated awesome.",
    "The universe is actually a giant marble being played with by a cosmic toddler.",
    "I've started a band called 'The Silent Screams'. We don't have any instruments.",
    "The birds are actually government drones, but they're very well-designed.",
    "I'm in a committed relationship with my bed, but my alarm clock keeps trying to break us up.",
    "The floor called. It misses your face.",
    "I'm not weird, I'm a limited edition.",
    "The coffee is the only thing keeping the demons at bay.",
    "I found the meaning of life, but I accidentally deleted the file.",
    "The moon is following me. I think it wants my autograph.",
    "I'm not a pro-crastinator, I'm an amateur-crastinator.",
    "The squirrels are now using drones. It's an aerial war now.",
    "I've decided to communicate only through interpretive dance and high-pitched whistles.",
    "The shadows are getting longer. I think they're stretching before a big race.",
    "I'm not arguing, I'm just explaining why I'm right in a very loud voice.",
    "The refrigerator light is the only thing I can trust in this dark world.",
    "I'm currently accepting applications for a personal cloud to follow me around.",
    "The stars are just glitter that the universe spilled.",
    "I'm not a morning person, I'm a 'leave me alone' person.",
    "The vacuum cleaner is the only thing in this house that actually sucks.",
    "I've started a collection of invisible stamps.",
    "The universe is just a simulation running on a very old toaster.",
]

_8ball_list = [
    "It is certain",
    "It is decidedly so",
    "Without a doubt",
    "Yes, definitely",
    "You may rely on it",
    "As I see it, yes",
    "Most likely",
    "Outlook good",
    "Yes",
    "Signs point to yes",
    "Reply hazy, try again",
    "Ask again later",
    "Better not tell you now",
    "Cannot predict now",
    "Concentrate and ask again",
    "Don't count on it",
    "My reply is no",
    "My sources say no",
    "Outlook not so good",
    "Very doubtful",
    "The squirrels say yes",
    "Only if you feed the pigeons",
    "Error 404: Answer not found",
    "Ask your refrigerator",
    "The moon is made of cheese, so yes",
    "The vibes are immaculate, proceed",
    "My tea leaves say maybe",
    "That's a secret for the cats to know",
    "Probability: Potato",
    "The magic toast says: Burnt (No)",
    "Signs point to... a sandwich",
    "Does a bear wood in the shits?",
    "42",
    "Beep boop, I am a bot (Yes)",
    "Your lucky number is 7, so maybe",
    "The ghosts in my attic say definitely",
    "If you believe in magic, then yes",
    "Wait, let me consult the rubber duck",
    "The stars are aligned for a pizza",
    "Not with that attitude",
    "100% chance of shenanigans",
    "The magic 8-ball is currently on lunch break",
    "Yes, but only on Tuesdays",
    "Maybe if you do a backflip",
    "The simulation says yes",
    "Outlook: Cloudy with a chance of meatballs",
    "I'll tell you if you give me a cookie",
    "The prophecy is unclear, try eating a taco",
    "Yes, but don't tell anyone",
    "No, and the cat agrees",
    "Is it too late to say sorry?",
    "The internet says yes, so it must be true",
    "My crystal ball is foggy, check back after a nap",
    "Absolutely, positively, probably not",
    "The magic 8-ball has spoken... and it wants coffee",
    "Yes, but watch out for ninjas",
    "No, but a dragon might say otherwise",
    "The answer is blowing in the wind",
    "Your future is bright, wear shades",
    "Signs point to a nap in your future",
]


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
        new_thing = self.children[0].value
        container = build_rate_container(new_thing)
        view = FunLayoutView(container)
        await interaction.response.edit_message(view=view)


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
        new_question = self.children[0].value

        view = Magic8BallView(interaction.user, new_question)

        await interaction.response.edit_message(view=view)


class AskAgainButton(discord.ui.Button):
    def __init__(self, is_ooc=False, rate_thing=None, is_backflip=False):
        if is_ooc:
            label = "Another One? 🎲"
        elif rate_thing:
            label = "Rate Again? ⚖️"
        elif is_backflip:
            label = "Flip Again! 🤸"
        else:
            label = "Ask Again 🎱"
        super().__init__(label=label, style=discord.ButtonStyle.blurple)
        self.is_ooc = is_ooc
        self.rate_thing = rate_thing
        self.is_backflip = is_backflip

    async def callback(self, interaction: discord.Interaction):
        if self.is_ooc:
            container = build_ooc_container()
            view = FunLayoutView(container)
            await interaction.response.edit_message(view=view)
        elif self.rate_thing:
            await interaction.response.send_modal(RateAgainModal())
        elif self.is_backflip:
            # We need to find the Fun cog to access the streak
            # This is a bit hacky but works for this setup
            cog = interaction.client.get_cog("Fun")
            container = cog.build_backflip_container(interaction.user)
            view = FunLayoutView(container)
            await interaction.response.edit_message(view=view)
        else:
            await interaction.response.send_modal(AskAgainModal())


def build_ooc_container() -> discord.ui.Container:
    """Builds the modern Components V2 layout for the OOC response."""
    message = random.choice(_ooc_list)
    return create_fun_container(
        title="📸 Out of Context",
        body=f"> {message}",
        accessory=AskAgainButton(is_ooc=True),
    )


def build_8ball_container(
    user: discord.User | discord.Member, question: str
) -> discord.ui.Container:
    """Builds the modern Components V2 layout for the 8-ball response."""
    answer = random.choice(_8ball_list)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body_text = f"> **Question:** {question}\n> \n> **Answer:** *{answer}*\n\nAsked by {user.mention} | {now}"

    return create_fun_container(
        title="8 Balls 🎱", body=body_text, accessory=AskAgainButton()
    )


def build_rate_container(thing: str) -> discord.ui.Container:
    """Builds the modern Components V2 layout for the rate response."""
    rating = random.choice(_rate_responses)
    return create_fun_container(
        title="⚖️ The Official Rating",
        body=f"**Thing:** {thing}\n\n**Rating:** {rating}",
        accessory=AskAgainButton(rate_thing=thing),
    )


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._backflip_success_messages = _backflip_success_messages
        self._backflip_fail_messages = _backflip_fail_messages

    def build_backflip_container(
        self, user: discord.User | discord.Member
    ) -> discord.ui.Container:
        """Builds the modern Components V2 layout for the backflip response."""
        success = random.random() < 0.55
        user_id = user.id

        # Update database and get new streak info
        streak_data = db.update_backflip(user_id, success)
        current = streak_data["current"]
        best = streak_data["best"]

        if success:
            title = "🤸 Backflip Success!"
            msg = random.choice(self._backflip_success_messages)
            body = f"{user.mention} {msg}\n\n**Current Streak:** {current} 🔥\n**Personal Best:** {best} 🏆"
        else:
            title = "🤕 Backflip Fail!"
            msg = random.choice(self._backflip_fail_messages)
            if current == 0:  # This means they failed
                # We need the previous streak to show what was broken
                prev_data = db.get_backflip(
                    user_id
                )  # This is slightly inaccurate since we just reset it
                # Let's just say they failed
                body = f"{user.mention} {msg}\n\n**Personal Best:** {best} 🏆"
            else:
                body = f"{user.mention} {msg}\n\n**Personal Best:** {best} 🏆"

        return create_fun_container(
            title=title, body=body, accessory=AskAgainButton(is_backflip=True)
        )

    @discord.slash_command(
        name="backflip",
        description="Try to perform a backflip and build a streak!",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
        contexts={
            discord.InteractionContextType.guild,
            discord.InteractionContextType.bot_dm,
            discord.InteractionContextType.private_channel,
        },
    )
    async def _backflip(self, ctx: discord.ApplicationContext):
        container = self.build_backflip_container(ctx.author)
        view = FunLayoutView(container)
        await ctx.respond(view=view)

    @discord.slash_command(
        name="rate",
        description="Rate anything with a totally unbiased opinion",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
        contexts={
            discord.InteractionContextType.guild,
            discord.InteractionContextType.bot_dm,
            discord.InteractionContextType.private_channel,
        },
    )
    async def _rate(self, ctx: discord.ApplicationContext, thing: str):
        container = build_rate_container(thing)
        view = FunLayoutView(container)
        await ctx.respond(view=view)

    @discord.slash_command(
        name="8ball",
        description="Ask the magic 8ball a question",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
        contexts={
            discord.InteractionContextType.guild,
            discord.InteractionContextType.bot_dm,
            discord.InteractionContextType.private_channel,
        },
    )
    async def _8ball(self, ctx: discord.ApplicationContext, question: str):
        container = build_8ball_container(ctx.author, question)
        view = FunLayoutView(container)

        await ctx.respond(view=view)

    @discord.slash_command(
        name="ooc",
        description="ooc or out of context gonna send you the most random stuff on the plannet",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
        contexts={
            discord.InteractionContextType.guild,
            discord.InteractionContextType.bot_dm,
            discord.InteractionContextType.private_channel,
        },
    )
    async def _ooc(self, ctx: discord.ApplicationContext):
        container = build_ooc_container()
        view = FunLayoutView(container)
        await ctx.respond(view=view)


def setup(bot):
    bot.add_cog(Fun(bot))
