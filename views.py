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


class CardPassingView(discord.ui.View):
    def __init__(self, game, player, hand):
        super().__init__(timeout=300)  # 5 minute timeout
        self.game = game
        self.player = player
        self.hand = hand
        self.selected_cards = []

        # Add dropdown for card selection
        self.add_item(CardSelectionDropdown(hand))

    async def on_timeout(self):
        # Disable all items when timeout
        for item in self.children:
            item.disabled = True


class CardSelectionDropdown(discord.ui.Select):
    def __init__(self, hand):
        # Create options for each card
        options = []
        for i, card in enumerate(hand):
            options.append(discord.SelectOption(
                label=f"{card}",
                value=str(i),
                description=f"Card {i + 1}"
            ))

        super().__init__(
            placeholder="Choose 3 cards to pass...",
            min_values=3,
            max_values=3,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view

        # Get selected cards by index
        selected_indices = [int(value) for value in self.values]
        selected_cards = [view.hand[i] for i in selected_indices]

        # Store the selection
        view.selected_cards = selected_cards

        # Add confirm button
        if not any(isinstance(item, ConfirmPassingButton) for item in view.children):
            view.add_item(ConfirmPassingButton())

        # Update the interaction
        card_names = ", ".join(str(card) for card in selected_cards)
        await interaction.response.edit_message(
            content=f"Selected cards: **{card_names}**\nClick Confirm to pass these cards.",
            view=view
        )


class ConfirmPassingButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Confirm Pass", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        view = self.view

        # Process the card passing
        await view.game.process_card_passing(view.player, view.selected_cards)

        # Disable the view
        for item in view.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="Cards passed successfully! Waiting for other players...",
            view=view
        )