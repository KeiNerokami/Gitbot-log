import nextcord
from nextcord.ext import commands
from nextcord import Interaction, SlashOption, ButtonStyle, Embed, ui

class ResponseButton(ui.View):
    def __init__(self, response: str, ephemeral: bool):
        super().__init__(timeout=None)
        self.response = response
        self.ephemeral = ephemeral

    async def interaction_check(self, interaction: Interaction) -> bool:
        return True
# Temp 0.5.1
    @ui.button(label="", style=ButtonStyle.primary)
    async def button_callback(self, button: ui.Button, interaction: Interaction):
        clean_response, embed_obj, add_roles, remove_roles = parse_special_variables(self.response, interaction)

        if embed_obj:
            await interaction.send(embed=embed_obj, ephemeral=self.ephemeral)
        else:
            await interaction.send(clean_response, ephemeral=self.ephemeral)

        if add_roles:
            await interaction.user.add_roles(*add_roles)
        if remove_roles:
            await interaction.user.remove_roles(*remove_roles)
# User callable variables
def parse_special_variables(response: str, interaction: Interaction):
    embed_obj = None
    add_roles = []
    remove_roles = []

    clean_response = response

    if "{embed}" in response:
        embed_obj = Embed(description=clean_response.replace("{embed}", "").strip())
        clean_response = ""  # Don't send plain text if embed is used

    import re

    add_match = re.search(r"{addrole:([^}]+)}", response)
    if add_match:
        role_ids_or_mentions = add_match.group(1).strip().split()
        for role_str in role_ids_or_mentions:
            role = None
            if role_str.startswith("<@&") and role_str.endswith(">"):
                role_id = int(role_str[3:-1])
                role = interaction.guild.get_role(role_id)
            elif role_str.isdigit():
                role = interaction.guild.get_role(int(role_str))
            if role:
                add_roles.append(role)
        clean_response = clean_response.replace(add_match.group(0), "").strip()

    remove_match = re.search(r"{removerole:([^}]+)}", response)
    if remove_match:
        role_ids_or_mentions = remove_match.group(1).strip().split()
        for role_str in role_ids_or_mentions:
            role = None
            if role_str.startswith("<@&") and role_str.endswith(">"):
                role_id = int(role_str[3:-1])
                role = interaction.guild.get_role(role_id)
            elif role_str.isdigit():
                role = interaction.guild.get_role(int(role_str))
            if role:
                remove_roles.append(role)
        clean_response = clean_response.replace(remove_match.group(0), "").strip()

    return clean_response, embed_obj, add_roles, remove_roles
# Main cog / Command
class ButtonCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @nextcord.slash_command(name="button", description="Create or modify a button")
    async def button(self, interaction: Interaction):
        pass

    @button.subcommand(name="create", description="Create a new message with a button")
    async def create(
        self,
        interaction: Interaction,
        emoji: str = SlashOption(description="Emoji for the button"),
        response: str = SlashOption(description="Response message (supports {embed}, {addrole:}, {removerole:})"),
        color: str = SlashOption(description="Hex color for embed", required=False),
        ephemeral: bool = SlashOption(description="Only visible to user?", required=False, default=False),
        label: str = SlashOption(description="Label text on the button", required=False, default="")
    ):
        view = ResponseButton(response=response, ephemeral=ephemeral)
        view.children[0].emoji = emoji
        view.children[0].label = label

        if "{embed}" in response:
            embed = Embed(description=response.replace("{embed}", "").strip())
            if color:
                try:
                    embed.color = nextcord.Color(int(color.replace("#", ""), 16))
                except ValueError:
                    await interaction.response.send_message("Invalid hex color.", ephemeral=True)
                    return
            await interaction.response.send_message(embed=embed, view=view, ephemeral=ephemeral)
        else:
            clean_response, *_ = parse_special_variables(response, interaction)
            await interaction.response.send_message(clean_response, view=view, ephemeral=ephemeral)

    @button.subcommand(name="add", description="Add a button to an existing message")
    async def add(
        self,
        interaction: Interaction,
        channel_id: str = SlashOption(description="Channel ID containing the message"),
        message_id: str = SlashOption(description="Message ID to modify"),
        emoji: str = SlashOption(description="Emoji for the button"),
        response: str = SlashOption(description="Response message (supports {embed}, {addrole:}, {removerole:})"),
        ephemeral: bool = SlashOption(description="Only visible to user?", required=False, default=False),
        label: str = SlashOption(description="Label text on the button", required=False, default="")
    ):
        try:
            channel = interaction.guild.get_channel(int(channel_id))
            if not channel:
                await interaction.response.send_message("Invalid channel ID.", ephemeral=True)
                return

            message = await channel.fetch_message(int(message_id))
            if not message:
                await interaction.response.send_message("Message not found.", ephemeral=True)
                return

            # Create new button
            new_view = ResponseButton(response=response, ephemeral=ephemeral)
            new_button = new_view.children[0]
            new_button.emoji = emoji
            new_button.label = label

            # Copy existing view if present
            existing_view = None
            if message.components:
                existing_view = ui.View.from_message(message)

            if existing_view:
                # Preserve all current buttons
                for item in existing_view.children:
                    new_view.add_item(item)

            await message.edit(view=new_view)
            await interaction.response.send_message("Button added to the message.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message("Failed to add button to the message.", ephemeral=True)
            raise e
# Too much iteration button may respond with an error fix those in the future
def setup(bot):
    bot.add_cog(ButtonCog(bot))
