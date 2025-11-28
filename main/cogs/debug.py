import nextcord
from nextcord.ext import commands
from nextcord import SlashOption
class SerVerDeBug(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @nextcord.slash_command(guild_ids=[1442581624481910827])
    async def test(
        self,
        interaction: nextcord.Interaction,
        choice: int = SlashOption(
            description="Test Choices",
            choices={"first": 1, "second": 2}
        )
    ):
        if choice == 1:
            await interaction.response.send_message(f"you choosed True")
        elif choice == 2:
            await interaction.response.send_message(f"you choosed False")

def setup(bot):
    bot.add_cog(SerVerDeBug(bot))