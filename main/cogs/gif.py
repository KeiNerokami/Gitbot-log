import nextcord
from nextcord.ext import commands
from nextcord import Interaction, SlashOption
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

# prefer TENOR_API_KEY env var, but allow TenorKey in .env for backwards compatibility
TENOR_API_KEY = os.getenv("TENOR_API_KEY") or os.getenv("TenorKey")

class GifView(nextcord.ui.View):
    def __init__(self, ctx_or_interaction, results, index=0, ephemeral=False):
        super().__init__(timeout=60)
        self.results = results
        self.index = index
        self.ctx_or_interaction = ctx_or_interaction
        self.ephemeral = ephemeral

    async def update_message(self, interaction=None):
        gif = self.results[self.index]
        embed = nextcord.Embed(
            title=f"GIF Result {self.index+1}/{len(self.results)}",
            color=0x2ECC71
        )
        url = Giffy._get_gif_url(gif)
        if url:
            embed.set_image(url=url)
        embed.set_footer(text="Powered by Tenor")

        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.message.edit(embed=embed, view=self)

    @nextcord.ui.button(label="◀", style=nextcord.ButtonStyle.secondary)
    async def previous(self, button, interaction):
        self.index = (self.index - 1) % len(self.results)
        await self.update_message(interaction)

    @nextcord.ui.button(label="🔗", style=nextcord.ButtonStyle.primary)
    async def link(self, button, interaction):
        gif = self.results[self.index]
        url = Giffy._get_gif_url(gif)
        if not url:
            return await interaction.response.send_message("No URL available for this result.", ephemeral=True)
        await interaction.response.send_message(f"GIF URL: {url}", ephemeral=True)

    @nextcord.ui.button(label="▶", style=nextcord.ButtonStyle.secondary)
    async def next(self, button, interaction):
        self.index = (self.index + 1) % len(self.results)
        await self.update_message(interaction)


class Giffy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_gifs(self, query):
        if not TENOR_API_KEY:
            return []

        search_url = "https://tenor.googleapis.com/v2/search"
        params = {
            "q": query,
            "key": TENOR_API_KEY,
            "limit": "10",
            # ask Tenor to return gif media and moderate content
            "media_filter": "gif",
            "contentfilter": "medium",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, params=params, timeout=8) as response:
                    if response.status != 200:
                        return []
                    data = await response.json()
        except Exception:
            return []

        return data.get("results", [])

    # Prefix !!gif <query>
    @commands.command(name="gif")
    async def gif_prefix(self, ctx, *, query=None):
        if not query:
            msg = await ctx.reply("Please provide something to search")
            await msg.delete(delay=3)
            return

        results = await self.fetch_gifs(query)
        if not results:
            # provide a small curated fallback if Tenor returns nothing or if key missing
            fallback = [
                {"media_formats": {"gif": {"url": "https://media.tenor.com/Ph0k0J7-3XAAAAAC/hug-anime.gif"}}},
                {"media_formats": {"gif": {"url": "https://media.tenor.com/2roX3uxz_4sAAAAC/anime-hug.gif"}}},
                {"media_formats": {"gif": {"url": "https://media.tenor.com/NEvZhkGQlq8AAAAC/hug.gif"}}},
            ]
            results = fallback

        view = GifView(ctx, results)

        gif = results[0]
        embed = nextcord.Embed(
            title=f"GIF Result 1/{len(results)}",
            color=ctx.author.top_role.color or nextcord.Color.blue()
        )
        embed.set_image(url=self._get_gif_url(gif))

        sent = await ctx.reply(embed=embed, view=view)
        view.message = sent

    # Slash /gif <query> <ephemeral>
    @nextcord.slash_command(name="gif", description="Search for a GIF")
    async def gif_slash(
        self,
        interaction: Interaction,
        query: str = SlashOption(description="Search GIF", required=True),
        ephemeral: bool = SlashOption(description="Send privately?", required=False, default=False)
    ):
        results = await self.fetch_gifs(query)
        if not results:
            # fallback to curated images if Tenor not available
            fallback = [
                {"media_formats": {"gif": {"url": "https://media.tenor.com/Ph0k0J7-3XAAAAAC/hug-anime.gif"}}},
                {"media_formats": {"gif": {"url": "https://media.tenor.com/2roX3uxz_4sAAAAC/anime-hug.gif"}}},
                {"media_formats": {"gif": {"url": "https://media.tenor.com/NEvZhkGQlq8AAAAC/hug.gif"}}},
            ]
            results = fallback

        view = GifView(interaction, results, ephemeral=ephemeral)

        gif = results[0]
        embed = nextcord.Embed(
            title=f"GIF Result 1/{len(results)}",
            color=nextcord.Color.blurple()
        )
        embed.set_image(url=self._get_gif_url(gif))

    @staticmethod
    def _get_gif_url(result: dict) -> str | None:
        """Return best possible gif URL from Tenor-like result shapes.

        Handles Tenor v2 'media_formats', older 'media' lists, and common fallback keys.
        """
        if not isinstance(result, dict):
            return None

        # Tenor v2 structure: media_formats -> gif -> url
        media_formats = result.get("media_formats")
        if isinstance(media_formats, dict):
            gif = media_formats.get("gif")
            if isinstance(gif, dict):
                return gif.get("url") or gif.get("src")

        # Tenor v1: media -> list -> {"gif": {"url": ...}}
        media = result.get("media") or []
        if isinstance(media, list):
            for item in media:
                if not isinstance(item, dict):
                    continue
                for key in ("gif", "mediumgif", "tinygif", "nanogif"):
                    candidate = item.get(key)
                    if isinstance(candidate, dict):
                        url = candidate.get("url") or candidate.get("src")
                        if url:
                            return url

        # other possible top-level fields
        for alt in ("url", "itemurl", "source"):
            value = result.get(alt)
            if isinstance(value, str) and value:
                return value

        return None

def setup(bot):
    bot.add_cog(Giffy(bot))
