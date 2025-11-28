import nextcord
from nextcord.ext import commands
import os, time, logging

logger = logging.getLogger("lunarbot")



class UtilityCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.devown = 1006187617987068014
        self.start_time = time.time()


class UtilityCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.devown = 1006187617987068014
        self.start_time = time.time()

    # ping
    @commands.command(name="ping")
    async def ping(self, ctx):
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! {latency}ms")

    # stats
    @commands.command(name="stats")
    async def stats(self, ctx):
        uptime = int(time.time() - self.start_time)
        await ctx.send(f"Bot Uptime: {uptime} seconds")

    # link
    @commands.command(name="link")
    async def link(self, ctx):
        await ctx.send("Bot invite link: <YOUR_INVITE_LINK>")

    # disable (example: disables a command)
    @commands.command(name="disable")
    async def disable(self, ctx, command_name: str):
        command = self.bot.get_command(command_name)
        if command:
            command.enabled = False
            await ctx.send(f"Command `{command_name}` has been disabled.")
        else:
            await ctx.send(f"No command named `{command_name}` found.")

    # shards
    @commands.command(name="shards")
    async def shards(self, ctx):
        if hasattr(self.bot, "shards"):
            await ctx.send(f"Shards: {len(self.bot.shards)}")
        else:
            await ctx.send("No shard information available.")

    # math (simple eval, restricted for safety)
    @commands.command(name="math")
    async def math(self, ctx, *, expression: str):
        try:
            result = eval(expression, {"__builtins__": {}})
            await ctx.send(f"Result: {result}")
        except Exception as e:
            await ctx.send(f"Error: {e}")

    # color (returns role color or hex)
    @commands.command(name="color")
    async def color(self, ctx, member: nextcord.Member = None):
        member = member or ctx.author
        color = member.top_role.color
        await ctx.send(f"{member.display_name}'s top role color: {color}")

    # prefix (show bot prefix)
    @commands.command(name="prefix")
    async def prefix(self, ctx):
        await ctx.send(f"Current prefix: {self.bot.command_prefix}")

    # log (restricted to console-accessible)
    @commands.command(name="log")
    async def log(self, ctx, *, message: str):
        if ctx.author.id == self.devown:  # only bot owner can use
            print(f"{message}")
            await ctx.send("Message logged to console.")
        else:
            await ctx.send("You are not authorized to use this command.")

    # purge/clear <amount>
    @commands.command(name="purge")
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("Please specify a number greater than 0.")
        deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command message
        await ctx.send(f"Deleted {len(deleted)-1} messages.", delete_after=5)

    @commands.command(name="clear")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int):
        await self.purge(ctx, amount)

    # say <message>
    @commands.command(name="say")
    async def say(self, ctx, *, message: str):
        await ctx.send(message)

    # echo <message>
    @commands.command(name="echo")
    async def echo(self, ctx, *, message: str):
        await ctx.send(message)

    # userinfo <user>
    @commands.command(name="userinfo")
    async def userinfo(self, ctx, member: nextcord.Member = None):
        member = member or ctx.author
        embed = nextcord.Embed(title=f"User Info - {member}", color=member.top_role.color)
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Display Name", value=member.display_name)
        embed.add_field(name="Top Role", value=member.top_role.name)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"))
        await ctx.send(embed=embed)

    # serverinfo
    @commands.command(name="serverinfo")
    async def serverinfo(self, ctx):
        guild = ctx.guild
        embed = nextcord.Embed(title=f"Server Info - {guild.name}", color=0x00FF00)
        embed.add_field(name="Server ID", value=guild.id)
        embed.add_field(name="Owner", value=str(guild.owner))
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Created At", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        embed.add_field(name="Channels", value=len(guild.channels))
        await ctx.send(embed=embed)

    # ping/stats/link/prefix/log/etc. already exist in your utility.py

    @commands.command(name="refresh")
    async def refresh(self, ctx):
        if ctx.author.id != self.devown:
            return await ctx.send("You are not authorized to use this command.")

        embed = nextcord.Embed(
            title="Refreshing all cogs...",
            description="Starting refresh...",
            color=0x00FF00
        )
        msg = await ctx.send(embed=embed)

        COGS_DIR = os.path.join(os.path.dirname(__file__), "../cogs")
        reloaded = []
        failed = []

        for fn in os.listdir(COGS_DIR):
            if fn.endswith(".py") and not fn.startswith("_"):
                cog_name = f"cogs.{fn[:-3]}"
                try:
                    self.bot.reload_extension(cog_name)
                    reloaded.append(cog_name)
                    logger.info(f"Reloaded {cog_name} via command")
                    embed.description = f"Reloaded: {', '.join(reloaded)}"
                except Exception as e:
                    failed.append((cog_name, str(e)))
                    logger.error(f"Failed to reload {cog_name}: {e}")
                    embed.description = (
                        f"Reloaded: {', '.join(reloaded)}\n"
                        f"Failed: {', '.join(f'{cog} ({err})' for cog, err in failed)}"
                    )

                await msg.edit(embed=embed)  # update embed after each cog

        embed.title = "Refresh complete"
        if failed:
            embed.color = 0xFF0000
            embed.description = (
                f"Reloaded: {', '.join(reloaded)}\n"
                f"Failed: {', '.join(f'{cog} ({err})' for cog, err in failed)}"
            )
        else:
            embed.color = 0x00FF00
            embed.description = f"Reloaded all cogs: {', '.join(reloaded)}"

        await msg.edit(embed=embed, delete_after=20)


def setup(bot):
    bot.add_cog(UtilityCommands(bot))
