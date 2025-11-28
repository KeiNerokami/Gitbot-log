import nextcord
from nextcord.ext import commands
from nextcord import Interaction, Embed, SlashOption
import json
import os

MESSAGE_COUNT_FILE = "message_counts.json"

def load_message_counts():
    if os.path.exists(MESSAGE_COUNT_FILE):
        with open(MESSAGE_COUNT_FILE, "r") as f:
            return json.load(f)
    return {}

def save_message_counts(counts):
    with open(MESSAGE_COUNT_FILE, "w") as f:
        json.dump(counts, f, indent=4)

message_counts = load_message_counts()

# --- NEW: Session tracking ---
active_sessions = {}  # channel_id: True/False
session_counts = {}   # channel_id: {user_id: count}

class MessageCounter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # === SESSION COMMANDS ===
    @nextcord.slash_command(name="msgs_count", description="Start or stop a message counting session")
    async def msgs_count(self, interaction: Interaction):
        pass  # This is just the group parent

    @msgs_count.subcommand(name="start", description="Start counting messages in this channel")
    async def msgs_count_start(self, interaction: Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You need Manage Messages permission to start a session.", ephemeral=True)
            return
        channel_id = str(interaction.channel.id)
        active_sessions[channel_id] = True
        session_counts[channel_id] = {}
        await interaction.response.send_message("Message counting session started in this channel!", ephemeral=False)

    @msgs_count.subcommand(name="stop", description="Stop counting messages in this channel")
    async def msgs_count_stop(self, interaction: Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You need Manage Messages permission to stop a session.", ephemeral=True)
            return
        channel_id = str(interaction.channel.id)
        active_sessions[channel_id] = False
        await interaction.response.send_message("Message counting session stopped in this channel!", ephemeral=False)

    # === SESSION LEADERBOARD ===
    @nextcord.slash_command(name="msgs", description="Show the leaderboard for the current session in this channel")
    async def msgs(self, interaction: Interaction):
        channel_id = str(interaction.channel.id)
        if not active_sessions.get(channel_id, False) and channel_id not in session_counts:
            await interaction.response.send_message("No active or recent session in this channel.", ephemeral=True)
            return
        counts = session_counts.get(channel_id, {})
        if not counts:
            await interaction.response.send_message("No messages have been counted in this session.", ephemeral=True)
            return

        sorted_users = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        top_users = sorted_users[:10]

        embed = Embed(title="Session Message Leaderboard", color=nextcord.Color.green())
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/972365813468246036/1418687899297255556/chat_1.png?ex=68cf0791&is=68cdb611&hm=54bc7b42884df5aed417b3176756551bba850ea9d1d929b2e5ac49676e555d72&")
        for i, (user_id, count) in enumerate(top_users, start=1):
            user = interaction.guild.get_member(int(user_id))
            name = user.display_name if user else f"<@{user_id}>"
            embed.add_field(name=f"{i} {name}", value=f"{count} messages", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=False)

    # === MESSAGE LISTENER ===
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # --- Normal global counting ---
        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        if guild_id not in message_counts:
            message_counts[guild_id] = {}
        if user_id not in message_counts[guild_id]:
            message_counts[guild_id][user_id] = 0
        message_counts[guild_id][user_id] += 1
        save_message_counts(message_counts)

        # --- Session counting ---
        channel_id = str(message.channel.id)
        if active_sessions.get(channel_id, False):
            if channel_id not in session_counts:
                session_counts[channel_id] = {}
            if user_id not in session_counts[channel_id]:
                session_counts[channel_id][user_id] = 0
            session_counts[channel_id][user_id] += 1

def setup(bot):
    bot.add_cog(MessageCounter(bot))
