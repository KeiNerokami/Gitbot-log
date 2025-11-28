import nextcord
from nextcord.ext import commands
from nextcord.ui import View, Button

# Example command dictionary: {category: {command_name: description}}
HELP_DATA = {
    "ActionCommands": {
        "bite": "Bite a user",
        "boop": "Boop a user",
        "bully": "Playfully bully a user",
        "cuddle": "Cuddle with a user",
        "greet": "Greet a user",
        "handholding": "Hold hands with a user",
        "highfive": "High five a user",
        "hold": "Hold a user",
        "hug": "Hug a user",
        "kill": "Pretend to kill a user",
        "kiss": "Kiss a user",
        "lick": "Lick a user",
        "nom": "Nom a user",
        "pat": "Pat a user",
        "pats": "Give multiple pats",
        "poke": "Poke a user",
        "punch": "Punch a user",
        "slap": "Slap a user",
        "snuggle": "Snuggle with a user",
        "stare": "Stare at a user",
        "tickle": "Tickle a user",
        "wave": "Wave at a user"
    },
    "EmbedCommands": {
        "embed": "Base command for embed editing."
    },
    "Giffy": {
        "gif": "Search GIFs from Tenor"
    },
    "No Category": {
        "help": "Shows this message"
    }
}

class HelpPaginator(View):
    def __init__(self, pages, timeout=120):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current = 0
        self.message = None

    async def update_page(self, interaction=None):
        embed = nextcord.Embed(
            title=f"Help Page {self.current+1}/{len(self.pages)}",
            description=self.pages[self.current],
            color=0x2ECC71
        )
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.message.edit(embed=embed, view=self)

    @nextcord.ui.button(label="◀", style=nextcord.ButtonStyle.secondary)
    async def previous(self, button: Button, interaction: nextcord.Interaction):
        self.current = (self.current - 1) % len(self.pages)
        await self.update_page(interaction)

    @nextcord.ui.button(label="▶", style=nextcord.ButtonStyle.secondary)
    async def next(self, button: Button, interaction: nextcord.Interaction):
        self.current = (self.current + 1) % len(self.pages)
        await self.update_page(interaction)

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def generate_pages(self):
        pages = []
        for category, commands_dict in HELP_DATA.items():
            items = list(commands_dict.items())
            for i in range(0, len(items), 5):
                chunk = items[i:i+5]
                text = f"**{category}:**\n"
                for cmd, desc in chunk:
                    text += f"  `{cmd}` - {desc}\n"
                pages.append(text)
        return pages

    @commands.command(name="help")
    async def help_command(self, ctx):
        pages = self.generate_pages()
        view = HelpPaginator(pages)
        embed = nextcord.Embed(
            title=f"Help Page 1/{len(pages)}",
            description=pages[0],
            color=0x2ECC71
        )
        message = await ctx.send(embed=embed, view=view)
        view.message = message

def setup(bot):
    bot.add_cog(Help(bot))
