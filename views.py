import discord
import logging

LOGGER = logging.getLogger(__name__)

class CreateLobbyView(discord.ui.View):
    def __init__(self, pregame):
        super().__init__()
        self.pregame = pregame

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green)
    async def button_join(self, interaction, button):
        ## TODO add leave button visible only to joined player that stops working when game has started
        if not interaction.user in self.pregame.players:
            self.pregame.players.append(interaction.user)
            LOGGER.info(f"Added {interaction.user} to the lobby.")
            await interaction.response.send_message(f"{interaction.user.mention} has joined the game.")
        else:
            LOGGER.info(f"{interaction.user} tried to join but is already in the lobby.")
            await interaction.response.send_message("You are already in the lobby", ephemeral=True)
