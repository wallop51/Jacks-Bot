import discord
import logging
from card_format import format_card_emoji, format_card_list

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
        self.hand = hand
        sorted_hand = sorted(hand)

        # Create options for each card with emoji
        options = []
        for i, card in enumerate(hand):
            card_display = format_card_emoji(card)
            original_index = hand.index(card)
            options.append(discord.SelectOption(
                label=card_display,
                value=str(original_index),
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

        # Update the dropdown to show selected state with emojis
        selected_display = format_card_list(selected_cards, selected_cards=selected_cards)
        self.placeholder = f"Selected: {selected_display}"

        # Mark selected options
        for option in self.options:
            card_index = int(option.value)
            card = view.hand[card_index]

            if option.value in self.values:
                option.label = format_card_emoji(card, is_selected=True)
                option.description = "Selected"
            else:
                option.label = format_card_emoji(card)
                option.description = f"Card {card_index + 1}"

        # Add confirm button if not already present
        if not any(isinstance(item, ConfirmPassingButton) for item in view.children):
            view.add_item(ConfirmPassingButton())

        embed = discord.Embed(
            title="Card Selection",
            description=f"**Selected Cards:** {format_card_list(selected_cards)}",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Instructions",
            value="Click 'Confirm Pass' to finalize your selection, or use the dropdown to change your selection.",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=view)


class ConfirmPassingButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Confirm Pass", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        view = self.view

        if not view.selected_cards or len(view.selected_cards) != 3:
            await interaction.response.send_message("Please select exactly 3 cards first!", ephemeral=True)
            return

        current_index = view.game.players.index(view.player)
        next_index = (current_index + 1) % len(view.game.players)
        recipient = view.game.players[next_index]

        await view.game.process_card_passing(view.player, view.selected_cards)

        for item in view.children:
            item.disabled = True

        # Create final embed with emojis
        embed = discord.Embed(
            title="Cards Passed Successfully!",
            description=f"You passed: {format_card_list(view.selected_cards)} to **{recipient.name}**",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Status",
            value="Waiting for other players to finish passing...",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=view)


class CardPlayView(discord.ui.View):
    def __init__(self, game, player, valid_cards):
        super().__init__(timeout=300)  # 5 minute timeout
        self.game = game
        self.player = player
        self.valid_cards = valid_cards

        # Add dropdown for card selection
        self.add_item(CardPlayDropdown(valid_cards))

    async def on_timeout(self):
        # Disable all items when timeout
        for item in self.children:
            item.disabled = True


class CardPlayDropdown(discord.ui.Select):
    def __init__(self, valid_cards):
        self.valid_cards = valid_cards

        # Create options for each valid card
        options = []
        for i, card in enumerate(valid_cards):
            card_display = format_card_emoji(card)
            options.append(discord.SelectOption(
                label=card_display,
                value=str(i),
                description="Click to play this card"
            ))

        super().__init__(
            placeholder="Choose a card to play...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view

        # Get selected card
        selected_index = int(self.values[0])
        selected_card = view.valid_cards[selected_index]

        # Disable the view immediately to prevent double-plays
        for item in view.children:
            item.disabled = True

        # Show confirmation
        embed = discord.Embed(
            title="Card Played!",
            description=f"You played: {format_card_emoji(selected_card)}",
            color=discord.Color.green()
        )
        embed.add_field(name="Status", value="Card played successfully!", inline=False)

        await interaction.response.edit_message(embed=embed, view=view)

        # Process the card play
        await view.game.play_card(view.player, selected_card)