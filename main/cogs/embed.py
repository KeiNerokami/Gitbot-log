import random
from nextcord.ext import commands
import nextcord
from nextcord import Interaction, SlashOption
from datetime import datetime
import logging

logger = logging.getLogger("lunarbot.embed")

def ordinal(n):
    return "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")

class EmbedCommands(commands.Cog):
    """Cog for creating and editing embeds with both prefix and slash commands."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        user = getattr(ctx, "author", None) or getattr(ctx, "user", None)
        if user is None:
            return False
        return user.guild_permissions.administrator

    def replace_variables(self, text: str, ctx) -> str:
        """Replace variables in the input text with context values."""
        user = getattr(ctx, "author", None) or getattr(ctx, "user", None)
        guild = getattr(ctx, "guild", None)
        member = guild.get_member(user.id) if guild and user else None

        if not guild or not member:
            return text

        all_members = guild.members
        nonbot_members = [m for m in all_members if not m.bot]
        bot_members = [m for m in all_members if m.bot]
        random_member = random.choice(all_members) if all_members else user
        random_member_nobots = random.choice(nonbot_members) if nonbot_members else user

        var_map = {
            "user": user.mention,
            "user_tag": str(user),
            "user_name": user.name,
            "user_avatar": user.avatar.url if user.avatar else "",
            "user_discrim": user.discriminator if hasattr(user, "discriminator") else "",
            "user_id": user.id,
            "user_nick": member.nick if member.nick else user.name,
            "user_joindate": member.joined_at.strftime('%Y-%m-%d') if member.joined_at else "",
            "user_createdate": user.created_at.strftime('%Y-%m-%d') if user.created_at else "",
            "user_displaycolor": str(member.color) if hasattr(member, "color") else "",
            "user_boostsince": member.premium_since.strftime('%Y-%m-%d') if getattr(member, "premium_since", None) else "",
            "server_name": guild.name,
            "server_id": guild.id,
            "server_membercount": guild.member_count,
            "server_membercount_ordinal": f"{guild.member_count}{ordinal(guild.member_count)}",
            "server_membercount_nobots": len(nonbot_members),
            "server_membercount_nobots_ordinal": f"{len(nonbot_members)}{ordinal(len(nonbot_members))}",
            "server_botcount": len(bot_members),
            "server_botcount_ordinal": f"{len(bot_members)}{ordinal(len(bot_members))}",
            "server_icon": guild.icon.url if guild.icon else "",
            "server_rolecount": len(guild.roles),
            "server_channelcount": len(guild.channels),
            "server_randommember": random_member.mention,
            "server_randommember_tag": str(random_member),
            "server_randommember_nobots": random_member_nobots.mention,
            "server_owner": guild.owner.mention if guild.owner else "",
            "server_owner_id": guild.owner_id if hasattr(guild, "owner_id") else "",
            "server_createdate": guild.created_at.strftime('%Y-%m-%d') if guild.created_at else "",
            "newline": "\n",  # Add this for new lines
        }

        for var, value in var_map.items():
            text = text.replace(f"{{{var}}}", str(value))
        return text

    def parse_message_id(self, message_id):
        """Parse and validate message_id as integer, stripping whitespace. Raise ValueError if invalid."""
        if isinstance(message_id, int):
            return message_id
        if isinstance(message_id, str):
            message_id = message_id.strip()
            if message_id.isdigit():
                return int(message_id)
        raise ValueError("Message ID must be an integer.")

    # --- PREFIX GROUP ---
    @commands.group(invoke_without_command=True)
    async def embed(self, ctx):
        """Base command for embed editing."""
        await ctx.send("Usage: `!embed <create|footer|title|description|author|thumbnail|image> ...`")

    @embed.command()
    async def create(self, ctx, *, title: str):
        """Create a new embed with a title and send it."""
        try:
            title = self.replace_variables(title, ctx)
            embed = nextcord.Embed(title=title, color=0x7289da)
            msg = await ctx.send(embed=embed)
            await ctx.send(f"Embed created! Message ID: `{msg.id}`\nUse `!embed <subcommand> <...> {msg.id}` to edit.")
        except Exception as e:
            logger.error(f"Error in !embed create: {e}")
            await ctx.send(f"Error: {e}")

    @embed.command()
    async def footer(self, ctx, text: str, message_id, icon: str = None, timestamp: str = "false"):
        """Edit the footer of an embed."""
        try:
            try:
                message_id_int = self.parse_message_id(message_id)
            except ValueError as ve:
                await ctx.send(str(ve))
                return
            msg = await ctx.channel.fetch_message(message_id_int)
            if not msg.embeds:
                await ctx.send("That message does not contain an embed.")
                return
            embed = msg.embeds[0]
            text = self.replace_variables(text, ctx)
            new_embed = nextcord.Embed.from_dict(embed.to_dict())
            if icon:
                new_embed.set_footer(text=text, icon_url=icon)
            else:
                new_embed.set_footer(text=text)
            if str(timestamp).lower() == "true":
                new_embed.timestamp = datetime.utcnow()
            await msg.edit(embed=new_embed)
            await ctx.send("Embed footer updated.")
        except Exception as e:
            logger.error(f"Error in !embed footer: {e}")
            await ctx.send(f"Error: {e}")

    @embed.command()
    async def title(self, ctx, text: str, message_id):
        """Edit the title of an embed."""
        try:
            try:
                message_id_int = self.parse_message_id(message_id)
            except ValueError as ve:
                await ctx.send(str(ve))
                return
            msg = await ctx.channel.fetch_message(message_id_int)
            if not msg.embeds:
                await ctx.send("That message does not contain an embed.")
                return
            embed = msg.embeds[0]
            text = self.replace_variables(text, ctx)
            new_embed = nextcord.Embed.from_dict(embed.to_dict())
            new_embed.title = text
            await msg.edit(embed=new_embed)
            await ctx.send("Embed title updated.")
        except Exception as e:
            logger.error(f"Error in !embed title: {e}")
            await ctx.send(f"Error: {e}")

    @embed.command()
    async def description(self, ctx, text: str, message_id):
        """Edit the description of an embed."""
        try:
            try:
                message_id_int = self.parse_message_id(message_id)
            except ValueError as ve:
                await ctx.send(str(ve))
                return
            msg = await ctx.channel.fetch_message(message_id_int)
            if not msg.embeds:
                await ctx.send("That message does not contain an embed.")
                return
            embed = msg.embeds[0]
            text = self.replace_variables(text, ctx)
            new_embed = nextcord.Embed.from_dict(embed.to_dict())
            new_embed.description = text
            await msg.edit(embed=new_embed)
            await ctx.send("Embed description updated.")
        except Exception as e:
            logger.error(f"Error in !embed description: {e}")
            await ctx.send(f"Error: {e}")

    @embed.command()
    async def author(self, ctx, text: str, message_id):
        """Edit the author of an embed."""
        try:
            try:
                message_id_int = self.parse_message_id(message_id)
            except ValueError as ve:
                await ctx.send(str(ve))
                return
            msg = await ctx.channel.fetch_message(message_id_int)
            if not msg.embeds:
                await ctx.send("That message does not contain an embed.")
                return
            embed = msg.embeds[0]
            text = self.replace_variables(text, ctx)
            new_embed = nextcord.Embed.from_dict(embed.to_dict())
            new_embed.set_author(name=text)
            await msg.edit(embed=new_embed)
            await ctx.send("Embed author updated.")
        except Exception as e:
            logger.error(f"Error in !embed author: {e}")
            await ctx.send(f"Error: {e}")

    @embed.command()
    async def thumbnail(self, ctx, url: str, message_id):
        """Edit the thumbnail of an embed."""
        try:
            try:
                message_id_int = self.parse_message_id(message_id)
            except ValueError as ve:
                await ctx.send(str(ve))
                return
            msg = await ctx.channel.fetch_message(message_id_int)
            if not msg.embeds:
                await ctx.send("That message does not contain an embed.")
                return
            embed = msg.embeds[0]
            new_embed = nextcord.Embed.from_dict(embed.to_dict())
            new_embed.set_thumbnail(url=url)
            await msg.edit(embed=new_embed)
            await ctx.send("Embed thumbnail updated.")
        except Exception as e:
            logger.error(f"Error in !embed thumbnail: {e}")
            await ctx.send(f"Error: {e}")

    @embed.command()
    async def image(self, ctx, url: str, message_id):
        """Edit the image of an embed."""
        try:
            try:
                message_id_int = self.parse_message_id(message_id)
            except ValueError as ve:
                await ctx.send(str(ve))
                return
            msg = await ctx.channel.fetch_message(message_id_int)
            if not msg.embeds:
                await ctx.send("That message does not contain an embed.")
                return
            embed = msg.embeds[0]
            new_embed = nextcord.Embed.from_dict(embed.to_dict())
            new_embed.set_image(url=url)
            await msg.edit(embed=new_embed)
            await ctx.send("Embed image updated.")
        except Exception as e:
            logger.error(f"Error in !embed image: {e}")
            await ctx.send(f"Error: {e}")
    @embed.command()
    async def delete(self, ctx, message_id: int):
        try:
            msgs = await ctx.channel.fetch_message(message_id)
            await msgs.delete()
            await ctx.send(f"embed `{message_id}` deleted")
        except nextcord.NotFound:
            await ctx.send(f'Message not found, make sure {message_id} is correct')
        except nextcord.Forbidden:
            await ctx.send('I do not have permissions to delete that message')
        except Exception as e:
            await ctx.send(f'Error: {str(e)}')

    @embed.command()
    async def color(self, ctx, hex: str, message_id: str):
        try:
            message_id_int = self.parse_message_id(message_id)
            msg = await ctx.channel.fetch_message(message_id_int)
            if not msg.embeds:
                await ctx.send("That message does not contain an embed.")
                return
            embed = msg.embeds[0]
            new_embed = nextcord.Embed.from_dict(embed.to_dict())
            new_embed.color = int(hex.strip("#"), 16)
            await msg.edit(embed=new_embed)
            await ctx.send("Embed color updated.")
        except Exception as e:
            logger.error(f"Error in !embed color: {e}")
            await ctx.send(f"Error: {e}")

    # SLASH


    @nextcord.slash_command(name="embedx", description="Edit an embed with multiple fields at once")
    async def embedx(
        self,
        interaction: Interaction,
        message_id: str = SlashOption(description="Message ID to edit", required=True),
        title: str = SlashOption(description="Embed title", required=False, default=None),
        description: str = SlashOption(description="Embed description", required=False, default=None),
        footer: str = SlashOption(description="Embed footer", required=False, default=None),
        author: str = SlashOption(description="Embed author", required=False, default=None),
        thumbnail: str = SlashOption(description="Thumbnail URL", required=False, default=None),
        image: str = SlashOption(description="Image URL", required=False, default=None),
        color: str = SlashOption(description="Hex color (e.g. #7289da)", required=False, default=None)
    ):
        try:
            message_id_int = self.parse_message_id(message_id)
            msg = await interaction.channel.fetch_message(message_id_int)
            if not msg.embeds:
                await interaction.response.send_message("That message does not contain an embed.", ephemeral=True)
                return
            embed = msg.embeds[0]
            new_embed = nextcord.Embed.from_dict(embed.to_dict())

            # Replace variables and update fields if provided
            ctx = interaction
            if title:
                new_embed.title = self.replace_variables(title, ctx)
            if description:
                new_embed.description = self.replace_variables(description, ctx)
            if footer:
                new_embed.set_footer(text=self.replace_variables(footer, ctx))
            if author:
                new_embed.set_author(name=self.replace_variables(author, ctx))
            if thumbnail:
                new_embed.set_thumbnail(url=thumbnail)
            if image:
                new_embed.set_image(url=image)
            if color:
                try:
                    new_embed.color = int(color.strip("#"), 16)
                except Exception:
                    await interaction.response.send_message("Invalid hex color. Example: `#7289da`", ephemeral=True)
                    return

            await msg.edit(embed=new_embed)
            await interaction.response.send_message("Embed updated.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in /embedx: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

     
    @nextcord.slash_command(name="icon", description="Change embed icons",guild_ids=[983593136867643462])
    async def icon(
        self,
        interaction: nextcord.Interaction,
        message_id: str = SlashOption(description="Message ID of the embed", required=True),
        attribute: str = SlashOption(
            required=True,
            description="Choose which attribute will be affected",
            choices={"author": "author", "footer": "footer"}
        ),
        icon: str = SlashOption(
            required=True,
            description="Icon link"
        )
    ):
        try:
            message_id_int = self.parse_message_id(message_id)
            msg = await interaction.channel.fetch_message(message_id_int)
            if not msg.embeds:
                await interaction.response.send_message("That message does not contain an embed.", ephemeral=True)
                return
            embed = msg.embeds[0]
            new_embed = nextcord.Embed.from_dict(embed.to_dict())

            if attribute == "author":
                new_embed.set_author(name=new_embed.author.name if new_embed.author else "", icon_url=icon)
            elif attribute == "footer":
                new_embed.set_footer(text=new_embed.footer.text if new_embed.footer else "", icon_url=icon)
            await msg.edit(embed=new_embed)
            await interaction.response.send_message("Embed icon updated.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in /embed_slash icon: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True) 
    @nextcord.slash_command(name='embed_slash', description='Embed group')
    async def embed_slash(self, interaction: Interaction):
        pass

    @embed_slash.subcommand(description="Create a new embed with a title")
    async def create(
        self,
        interaction: Interaction,
        title: str = SlashOption(description="Embed title")
    ):
        try:
            title = self.replace_variables(title, interaction)
            embed = nextcord.Embed(title=title, color=0x7289da)
            msg = await interaction.channel.send(embed=embed)
            await interaction.response.send_message(
                f"Embed created! Message ID: `{msg.id}`\nUse `/embed_slash <subcommand> ... {msg.id}` to edit.",
                ephemeral=False
            )
        except Exception as e:
            logger.error(f"Error in /embed_slash create: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=False)

    


def setup(bot):
    bot.add_cog(EmbedCommands(bot))
