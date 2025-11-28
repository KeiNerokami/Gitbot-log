import nextcord
from nextcord.ext import commands
from nextcord.ui import View, Button
import aiohttp
import random
import os
from dotenv import load_dotenv

load_dotenv()

# prefer TENOR_API_KEY env var, but allow TenorKey for backwards compatibility
TENOR_API_KEY = os.getenv("TENOR_API_KEY") or os.getenv("TenorKey")

# more precise queries per action to avoid returning duplicate/overlapping gifs
ACTION_QUERIES = {
    "cuddle": "anime cuddle cozy cute",
    "hug": "anime hug warm cute",
    "kiss": "anime kiss romantic adorable",
    "lick": "anime lick playful",
    "nom": "anime eating nom food anime",
    "pat": "anime pat head gentle",
    "poke": "anime poke",
    "slap": "anime slap comical",
    "stare": "anime stare awkward",
    "highfive": "anime high five celebration",
    "bite": "anime bite playful",
    "greet": "anime wave greeting",
    "punch": "anime punch action",
    "handholding": "anime holding hands couple",
    "tickle": "anime tickle laugh",
    "kill": "anime dramatic fight (non-graphic)",
    "hold": "anime hold embrace",
    "pats": "anime pats gentle",
    "wave": "anime wave hello",
    "boop": "anime boop nose cute",
    "snuggle": "anime snuggle cozy",
    "bully": "anime bully playful teasing",
}

# curated per-action fallbacks to guarantee different GIFs when Tenor fails
ACTION_FALLBACKS = {
    "cuddle": [
        "https://c.tenor.com/0Yv0f8y3F8UAAAAC/anime-cuddle.gif",
        "https://c.tenor.com/_k0x6q5m3mIAAAAC/anime-cuddles.gif",
    ],
    "hug": [
        "https://c.tenor.com/Ph0k0J7-3XAAAAAC/hug-anime.gif",
        "https://c.tenor.com/2roX3uxz_4sAAAAC/anime-hug.gif",
    ],
    "kiss": [
        "https://c.tenor.com/W9fX5vJ8e-IAAAAC/anime-kiss.gif",
        "https://c.tenor.com/4sQv4wr5gZsAAAAC/anime-kissing.gif",
    ],
    "pat": [
        "https://c.tenor.com/HrF3Q9gq4OcAAAAC/pat-anime.gif",
        "https://c.tenor.com/Y9w0Cq0AY2kAAAAC/pat-head.gif",
    ],
    "slap": [
        "https://c.tenor.com/9w2sUyqjF2gAAAAC/anime-slap.gif",
        "https://c.tenor.com/J7eGDvGeP9IAAAAC/tenor.gif",
    ],
    # generic fallback for other actions
}

ACTIONS = [
    "cuddle", "hug", "kiss", "lick", "nom", "pat", "poke", "slap", "stare",
    "highfive", "bite", "greet", "punch", "handholding", "tickle", "kill",
    "hold", "pats", "wave", "boop", "snuggle", "bully"
]


class ActionButton(View):
    def __init__(self, bot, action, author, member):
        super().__init__(timeout=50)
        self.bot = bot
        self.action = action
        self.author = author
        self.member = member

    @nextcord.ui.button(label="Respond back!", style=nextcord.ButtonStyle.blurple)
    async def action_button(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("You are not the author of this command.", ephemeral=True, delete_after=2)

        await interaction.response.defer()
        gif_url = await self.bot.get_cog("ActionCommands").fetch_action_gif(self.action)
        embed = nextcord.Embed(
            title=f"{self.author.display_name} {self.action}s {self.member.display_name}",
            color=nextcord.Color.random()
        )
        embed.set_image(url=gif_url)
        await interaction.followup.send(embed=embed)

class ActionCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.action_stats = {}

    async def fetch_action_gif(self, action):
        # if no Tenor key available, use curated fallbacks to ensure variety
        if not TENOR_API_KEY:
            fall = ACTION_FALLBACKS.get(action) or []
            if fall:
                return random.choice(fall)
            return "https://c.tenor.com/J7eGDvGeP9IAAAAC/tenor.gif"

        query = ACTION_QUERIES.get(action, f"{action} anime")
        search_url = "https://tenor.googleapis.com/v2/search"
        params = {
            "q": query,
            "key": TENOR_API_KEY,
            "limit": "25",
            "media_filter": "gif",
            "contentfilter": "medium",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, params=params, timeout=8) as response:
                    if response.status != 200:
                        results = []
                    else:
                        data = await response.json()
                        results = data.get("results", [])
        except Exception:
            results = []

        # extract valid gif urls from results
        urls = []
        for item in results:
            url = self._extract_gif_url(item)
            if url:
                urls.append(url)

        if urls:
            # pick one at random to avoid returning the same for different actions
            return random.choice(urls)

        # last-resort: per-action fallback or global fallback
        fall = ACTION_FALLBACKS.get(action) or []
        if fall:
            return random.choice(fall)

        return "https://c.tenor.com/J7eGDvGeP9IAAAAC/tenor.gif"

    def _extract_gif_url(self, result: dict) -> str | None:
        # handle Tenor v2 -> media_formats -> gif -> url
        if not isinstance(result, dict):
            return None

        mf = result.get("media_formats")
        if isinstance(mf, dict):
            gif = mf.get("gif")
            if isinstance(gif, dict):
                return gif.get("url") or gif.get("src")

        # v1 shape -> media -> list
        media = result.get("media") or []
        if isinstance(media, list):
            for m in media:
                if isinstance(m, dict):
                    candidate = m.get("gif") or m.get("mediumgif")
                    if isinstance(candidate, dict):
                        url = candidate.get("url") or candidate.get("src")
                        if url:
                            return url

        # try top-level urls
        for alt in ("url", "itemurl", "source"):
            val = result.get(alt)
            if isinstance(val, str) and val:
                return val

        return None

    async def send_action(self, ctx, action, member: nextcord.Member = None):

        # Determine target user
        if member is None and ctx.message.reference:
            replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if replied_message and replied_message.author:
                member = replied_message.author

        # No target
        if member is None:
            msg = await ctx.reply("Please mention a user")
            await msg.delete(delay=3)
            return

        # Self prevention
        if member.id == ctx.author.id:
            return await ctx.reply(f"You cannot {action} yourself.")

        # Bot prevention
        if member.id == self.bot.user.id:
            return await ctx.reply("Thank you.")

        # Tracking
        self.action_stats.setdefault(action, {})
        self.action_stats[action][ctx.author.id] = self.action_stats[action].get(ctx.author.id, 0) + 1
        total = self.action_stats[action][ctx.author.id]

        # Role color
        role_color = ctx.author.top_role.color
        if role_color.value == 0:
            role_color = 0xAABBCC

        # Tenor API GIF
        gif_url = await self.fetch_action_gif(action)

        embed = nextcord.Embed(
            description=f"{ctx.author.display_name} {action}s {member.display_name}.",
            color=role_color
        )

        embed.set_image(url=gif_url)
        embed.set_footer(text=f"{action.capitalize()}s given by you: {total}")
        view = ActionButton(self.bot, action, ctx.author, member)
        
        await ctx.reply(embed=embed, view=view)


    # cuddle <user>
    @commands.command(name="cuddle")
    async def cuddle(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "cuddle", member)
        
    # hug <user>
    @commands.command(name="hug")
    async def hug(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "hug", member)

    # kiss <user>
    @commands.command(name="kiss")
    async def kiss(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "kiss", member)

    # lick <user>
    @commands.command(name="lick")
    async def lick(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "lick", member)

    # nom <user>
    @commands.command(name="nom")
    async def nom(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "nom", member)

    # pat <user>
    @commands.command(name="pat")
    async def pat(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "pat", member)

    # poke <user>
    @commands.command(name="poke")
    async def poke(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "poke", member)

    # slap <user>
    @commands.command(name="slap")
    async def slap(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "slap", member)

    # stare <user>
    @commands.command(name="stare")
    async def stare(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "stare", member)

    # highfive <user>
    @commands.command(name="highfive")
    async def highfive(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "highfive", member)

    # bite <user>
    @commands.command(name="bite")
    async def bite(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "bite", member)

    # greet <user>
    @commands.command(name="greet")
    async def greet(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "greet", member)

    # punch <user>
    @commands.command(name="punch")
    async def punch(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "punch", member)

    # handholding <user>
    @commands.command(name="handholding")
    async def handholding(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "handholding", member)

    # tickle <user>
    @commands.command(name="tickle")
    async def tickle(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "tickle", member)

    # kill <user>
    @commands.command(name="kill")
    async def kill(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "kill", member)

    # hold <user>
    @commands.command(name="hold")
    async def hold(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "hold", member)

    # pats <user>
    @commands.command(name="pats")
    async def pats(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "pats", member)

    # wave <user>
    @commands.command(name="wave")
    async def wave(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "wave", member)

    # boop <user>
    @commands.command(name="boop")
    async def boop(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "boop", member)

    # snuggle <user>
    @commands.command(name="snuggle")
    async def snuggle(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "snuggle", member)

    # bully <user>
    @commands.command(name="bully")
    async def bully(self, ctx, member: nextcord.Member = None):
        await self.send_action(ctx, "bully", member)


def setup(bot):
    bot.add_cog(ActionCommands(bot))
