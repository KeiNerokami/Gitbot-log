import logging
import nextcord
from nextcord.ext import commands
from nextcord.ui import View, Select, Modal, TextInput
from typing import Optional
import json
import os

logger = logging.getLogger(__name__)

# ---- CONFIGURATION ----
GUILD_ID = 1442581624481910827  # replace with your server ID
CHANNEL_ID = 1442592828919255142  # replace with your channel ID

# Booster color roles {name: role_id}
BOOSTER_COLOR_ROLES = {
    "Red": 123456789012345678,   # replace with actual role IDs
    "Green": 234567890123456789,
    "Blue": 345678901234567890,
    "Pink": 456789012345678901,
}

# --- Custom Role JSON Storage ---
CUSTOM_ROLE_FILE = "custom_roles.json"

def load_custom_roles():
    if os.path.exists(CUSTOM_ROLE_FILE):
        with open(CUSTOM_ROLE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_custom_roles(data):
    with open(CUSTOM_ROLE_FILE, "w") as f:
        json.dump(data, f, indent=4)

custom_roles = load_custom_roles()

class BoosterColorSelect(Select):
    def __init__(self, member: nextcord.Member):
        options = [
            nextcord.SelectOption(label=name, description=f"Assign booster color role", value=str(role_id))
            for name, role_id in BOOSTER_COLOR_ROLES.items()
        ]
        super().__init__(placeholder="Choose your booster color...", options=options, min_values=1, max_values=1)
        self.member = member

    async def callback(self, interaction: nextcord.Interaction):
        guild = interaction.guild
        selected_role_id = int(self.values[0])
        selected_role = guild.get_role(selected_role_id)

        # Remove all other booster color roles
        roles_to_remove = [role for role in self.member.roles if role.id in BOOSTER_COLOR_ROLES.values() and role.id != selected_role_id]
        if roles_to_remove:
            try:
                await self.member.remove_roles(*roles_to_remove, reason="Changing booster color")
            except Exception as e:
                logger.error(f"Error removing old booster color roles: {e}")

        # Add selected booster color role if not already present
        if selected_role and selected_role not in self.member.roles:
            try:
                await self.member.add_roles(selected_role)
                await interaction.response.send_message(f"✅ Your booster color role has been set to {selected_role.name}", ephemeral=True)
                logger.info(f"Set booster color for {self.member} ({self.member.id}) to {selected_role.name} in guild {guild.id}")
            except Exception as e:
                logger.error(f"Error assigning booster role: {e}")
        else:
            await interaction.response.send_message("❌ Selected role not found or already assigned.", ephemeral=True)

class CustomRoleModal(Modal):
    def __init__(self, bot: commands.Bot, existing_role: Optional[nextcord.Role] = None):
        super().__init__("Create / Update Custom Role")
        self.bot = bot
        self.existing_role = existing_role
        self.name = TextInput(label="Role Name (you may include emoji)", required=True, max_length=30)
        self.color = TextInput(label="Role Color (hex only, e.g. #FF5733)", required=True, max_length=7)
        self.add_item(self.name)
        self.add_item(self.color)

    async def callback(self, interaction: nextcord.Interaction):
        note = (
            "ℹ️ **Note:** If you want a custom icon or gradient for your role, "
            "please make a ticket and ask staff to add it for you."
        )
        guild = interaction.guild
        member = interaction.user

        # Validate hex color
        if not self.color.value.startswith("#") or len(self.color.value) != 7:
            await interaction.response.send_message("Invalid hex color. Example: `#FF5733`", ephemeral=True)
            return

        try:
            hex_color = int(self.color.value[1:], 16)
            discord_color = nextcord.Colour(hex_color)
        except Exception:
            await interaction.response.send_message("Invalid hex color. Example: `#FF5733`", ephemeral=True)
            return

        role_kwargs = {
            "name": self.name.value,  # No "Custom: " prefix
            "colour": discord_color,
            "reason": f"Custom role for {member}",
        }

        if self.existing_role:
            try:
                await self.existing_role.edit(**role_kwargs)
                # Update mapping
                custom_roles[str(member.id)] = self.existing_role.id
                save_custom_roles(custom_roles)
                await interaction.response.send_message(
                    f"Your custom role has been updated: {self.existing_role.mention}\n{note}",
                    ephemeral=True
                )
                logger.info(f"Updated custom role for {member} ({member.id}) in guild {guild.id}")
            except Exception as e:
                logger.error(f"Error updating custom role: {e}")
        else:
            try:
                role = await guild.create_role(**role_kwargs)
                await member.add_roles(role)
                # Save mapping
                custom_roles[str(member.id)] = role.id
                save_custom_roles(custom_roles)
                await interaction.response.send_message(
                    f"Your custom role has been created: {role.mention}\n{note}",
                    ephemeral=True
                )
                logger.info(f"Created custom role for {member} ({member.id}) in guild {guild.id}")
            except Exception as e:
                logger.error(f"Error creating custom role: {e}")

class EditRoleButton(nextcord.ui.Button):
    def __init__(self, bot, existing_role):
        super().__init__(label="Edit Your Custom Role", style=nextcord.ButtonStyle.primary)
        self.bot = bot
        self.existing_role = existing_role

    async def callback(self, interaction: nextcord.Interaction):
        modal = CustomRoleModal(self.bot, existing_role=self.existing_role)
        await interaction.response.send_modal(modal)

class BoosterMenuSelect(Select):
    def __init__(self, bot: commands.Bot):
        options = [
            nextcord.SelectOption(label="Booster Color", description="Choose a custom booster color", value="booster"),
            nextcord.SelectOption(label="Custom Role", description="Create or view your custom role", value="custom"),
        ]
        super().__init__(placeholder="Select an option...", options=options, min_values=1, max_values=1)
        self.bot = bot

    async def callback(self, interaction: nextcord.Interaction):
        member = interaction.user
        guild = interaction.guild

        if self.values[0] == "booster":
            view = View()
            view.add_item(BoosterColorSelect(member))
            await interaction.response.send_message("Choose your booster color:", view=view, ephemeral=True)

        elif self.values[0] == "custom":
            # Check if user already has a custom role using the mapping
            role_id = custom_roles.get(str(member.id))
            existing_role = None
            if role_id:
                existing_role = guild.get_role(role_id)
                # Optionally, check if the member still has the role
                if existing_role and existing_role not in member.roles:
                    existing_role = None

            if existing_role:
                view = View()
                view.add_item(EditRoleButton(self.bot, existing_role))
                await interaction.response.send_message(
                    f"You already have a custom role: {existing_role.mention}",
                    view=view,
                    ephemeral=True
                )
            else:
                modal = CustomRoleModal(self.bot)
                await interaction.response.send_modal(modal)

class BoosterRoleView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.add_item(BoosterMenuSelect(bot))

class BoosterRoleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            logger.warning(f"Guild with ID {GUILD_ID} not found")
            return

        channel = guild.get_channel(CHANNEL_ID)
        if not channel:
            logger.warning(f"Channel with ID {CHANNEL_ID} not found in guild {guild.id}")
            return

        # Delete previous booster perk embed sent by the bot
        async for msg in channel.history(limit=20):
            if msg.author == self.bot.user and msg.embeds:
                if msg.embeds[0].title == "Booster Perks":
                    try:
                        await msg.delete()
                        logger.info(f"Deleted previous booster perks embed in {channel.name} ({channel.id})")
                    except Exception as e:
                        logger.error(f"Failed to delete previous booster perks embed: {e}")

        embed = nextcord.Embed(
            title="Booster Perks",
            description="Choose one of the options below to customize your perks!",
            color=nextcord.Color.purple()
        )

        view = BoosterRoleView(self.bot)
        await channel.send(embed=embed, view=view)
        logger.info(f"Sent booster role menu in {channel.name} ({channel.id}) of guild {guild.name} ({guild.id})")

def setup(bot: commands.Bot):
    bot.add_cog(BoosterRoleCog(bot))
