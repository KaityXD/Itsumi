import discord
from discord.ext import commands

from utils.error_handler.handler import UniversalErrorHandler


class ErrorHandlerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.handler = UniversalErrorHandler()

    @commands.Cog.listener()
    async def on_application_command(self, ctx: discord.ApplicationContext):
        self.handler.log_command(ctx)

    @commands.Cog.listener()
    async def on_application_command_error(
        self, ctx: discord.ApplicationContext, error: discord.DiscordException
    ):
        await self.handler.handle_error(ctx, error)


def setup(bot):
    bot.add_cog(ErrorHandlerCog(bot))
