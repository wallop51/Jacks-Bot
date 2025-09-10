import logging
import random
import views
from card_format import *

import discord
from discord import Member

SUITS = ["Hearts", "Clubs", "Diamonds", "Spades"]
RANKS = ["3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

LOGGER = logging.getLogger(__name__)

class Card:
    # Define the order for suits and ranks
    SUIT_ORDER = {'Hearts': 0, 'Clubs': 1, 'Diamonds': 2, 'Spades': 3}
    RANK_ORDER = {'3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                  '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}

    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank

    def __repr__(self):
        return f"{self.rank}{self.suit[0]}"  # e.g. "10H", "QS"

    def __lt__(self, other):
        # First compare by suit, then by rank
        if self.SUIT_ORDER[self.suit] != self.SUIT_ORDER[other.suit]:
            return self.SUIT_ORDER[self.suit] < self.SUIT_ORDER[other.suit]
        return self.RANK_ORDER[self.rank] < self.RANK_ORDER[other.rank]

    def __eq__(self, other):
        return self.rank == other.rank and self.suit == other.suit


def make_deck():
    return [Card(suit, rank) for suit in SUITS for rank in RANKS]

class Player:
    def __init__(self, name, discord_user=None):
        self.name = name
        self.discord_user = discord_user
        self.hand = []
        self.tricks = []
        self.score = 0

    def __repr__(self):
        return f"{self.name} (Score: {self.score})"

# --- Game Setup ---

class PreGame:
    def __init__(self, interaction):
        self.interaction = interaction
        self.master = interaction.user
        self.ready = False
        self.players = []
        self.lobby_message = None


    async def create_lobby(self, master: Member):
        LOGGER.info(f"Creating lobby for {master} in {self.interaction.channel.name}")
        embed = discord.Embed(title="Jacks",
                              description=f"{master.mention} has started a Jacks game!\nThe game will begin once 3-4 players have joined and {master.mention} uses /ready")
        await self.interaction.response.send_message(embed=embed, view=views.CreateLobbyView(self))
        self.lobby_message = await self.interaction.original_response()


class Game:
    def __init__(self, players: list):
        self.discord_players = players
        self.players = [Player(user.display_name, user) for user in players]
        self.deck = make_deck()
        self.trump_index = 0  # start with Hearts as trump
        self.passed_cards = {}

        # Game state tracking

        self.current_trick = []  # Cards played in current trick: [(player, card), ...]
        self.current_player_index = 0  # Index of player whose turn it is
        self.lead_player_index = 0  # Index of player who led the current trick
        self.game_phase = "passing"  # "passing", "playing", "finished"
        self.round_number = 1
        self.last_trick_messages = {}

        self.deal_cards()

    def get_trump_emoji(self):
        return SUIT_EMOJIS[SUITS[self.trump_index]]

    def get_current_player(self):
        # Get the player whose turn it is
        return self.players[self.current_player_index]

    def get_trump_suit(self):
        # Get the current trump suit name
        return SUITS[self.trump_index]

    def is_trump(self, card):
        # Check if a card is trump
        return card.suit == self.get_trump_suit()

    def get_lead_suit(self):
        # Get the suit that was led this trick (None if no cards played)
        if not self.current_trick:
            return None
        return self.current_trick[0][1].suit  # suit of first card played

    def can_follow_suit(self, player, lead_suit):
        # Check if player has cards of the lead suit
        return any(card.suit == lead_suit for card in player.hand)

    async def hide_previous_trick_cards(self):
        # Hide the cards from the previous trick announcement
        for player, message in self.last_trick_messages.items():
            if message:
                try:
                    # Create a new embed with hidden card details
                    embed = discord.Embed(
                        title="Trick Complete!",
                        description="*(Cards hidden - new trick has started)*",
                        color=discord.Color.greyple()
                    )

                    # Still show current scores
                    score_text = []
                    for p in self.players:
                        tricks_this_hand = len(p.tricks)
                        score_text.append(f"**{p.name}:** {tricks_this_hand} tricks (Total: {p.score})")

                    embed.add_field(name="Current Scores", value="\n".join(score_text), inline=False)
                    embed.set_footer(text=f"Trump: {self.get_trump_emoji()}")

                    await message.edit(embed=embed)
                except discord.NotFound:
                    # Message was deleted, ignore
                    pass
                except discord.Forbidden:
                    # No permission to edit, ignore
                    pass

        # Clear the stored messages
        self.last_trick_messages = {}

    def get_valid_plays(self, player):
        # Get list of cards the player can legally play
        if not self.current_trick:  # Leading the trick
            return player.hand.copy()

        lead_suit = self.get_lead_suit()

        # Must follow suit if possible
        same_suit_cards = [card for card in player.hand if card.suit == lead_suit]
        if same_suit_cards:
            return same_suit_cards

        # If can't follow suit, can play anything
        return player.hand.copy()

    async def play_card(self, player, card):
        # Handle when a player plays a card
        LOGGER.info(f"{player.name} played {card}")

        if len(self.current_trick) == 0 and self.last_trick_messages:
            await self.hide_previous_trick_cards()

        # Remove card from player's hand
        player.hand.remove(card)

        # Add to current trick
        self.current_trick.append((player, card))

        # Check if trick is complete
        if len(self.current_trick) == len(self.players):
            await self.complete_trick()
        else:
            # Move to next player
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            await self.prompt_current_player()

    async def complete_trick(self):
        # Complete the current trick and determine winner
        LOGGER.info(f"Completing trick with {len(self.current_trick)} cards")
        winning_player, winning_card = self.evaluate_trick()

        LOGGER.info(f"{winning_player.name} won the trick with {winning_card}")

        # Add trick to winner's tricks
        trick_cards = [card for player, card in self.current_trick]
        winning_player.tricks.append(trick_cards)

        # Announce winner to all players
        await self.announce_trick_winner(winning_player, winning_card)

        # Clear current trick
        self.current_trick = []

        # Winner leads next trick
        self.lead_player_index = self.players.index(winning_player)
        self.current_player_index = self.lead_player_index

        # Check if hand is complete (all cards played)
        if not any(player.hand for player in self.players):
            await self.complete_hand()
        else:
            # Start next trick
            await self.prompt_current_player()

    async def complete_hand(self):
        """Complete the current hand and calculate scores"""
        LOGGER.info("Hand complete! Calculating scores...")

        # Calculate scores for this hand
        for player in self.players:
            tricks_won = len(player.tricks)

            # Count jacks in tricks
            jacks_caught = 0
            for trick in player.tricks:
                jacks_caught += sum(1 for card in trick if card.rank == "J")

            # Calculate penalty based on number of players
            jack_penalty = -4 if len(self.players) == 3 else -3

            # Score = tricks won + (jacks * penalty)
            hand_score = tricks_won + (jacks_caught * jack_penalty)
            player.score += hand_score

            LOGGER.info(
                f"{player.name}: {tricks_won} tricks, {jacks_caught} jacks, score: {hand_score} (total: {player.score})")

        # Send results to all players
        await self.send_hand_results()

        # TODO: Check if game is complete or start next hand
        self.game_phase = "finished"

    async def send_hand_results(self):
        # Send hand results to all players
        embed = discord.Embed(
            title=f"Hand {self.round_number} Complete!",
            color=discord.Color.blue()
        )

        # Add results for each player
        results_text = []
        for player in self.players:
            tricks_won = len(player.tricks)
            jacks_caught = sum(sum(1 for card in trick if card.rank == "J") for trick in player.tricks)
            jack_penalty = -4 if len(self.players) == 3 else -3
            hand_score = tricks_won + (jacks_caught * jack_penalty)

            results_text.append(
                f"**{player.name}:** {tricks_won} tricks, {jacks_caught} jacks → {hand_score:+d} pts (Total: {player.score})")

        embed.add_field(name="Results", value="\n".join(results_text), inline=False)
        embed.set_footer(text=f"Trump was {self.get_trump_emoji()}")

        # Send to all players
        for player in self.players:
            try:
                await player.discord_user.send(embed=embed)
            except discord.Forbidden:
                LOGGER.warning(f"Could not send results to {player.name}")

    def evaluate_trick(self):
        # Determine who wins the current trick
        if len(self.current_trick) != len(self.players):
            return None  # Trick not complete

        lead_suit = self.get_lead_suit()
        trump_suit = self.get_trump_suit()

        # Separate cards into categories
        lead_suit_cards = []
        trump_cards = []

        for player, card in self.current_trick:
            if card.suit == lead_suit:
                lead_suit_cards.append((player, card))
            elif card.suit == trump_suit:
                trump_cards.append((player, card))
            # Other suits are ignored - can't win the trick

        # Trump beats everything (unless trump was led)
        if trump_cards and trump_suit != lead_suit:
            # Highest trump wins
            winning_player, winning_card = max(trump_cards,
                                               key=lambda x: Card.RANK_ORDER[x[1].rank])
        elif lead_suit_cards:
            # Highest card of lead suit wins
            winning_player, winning_card = max(lead_suit_cards,
                                               key=lambda x: Card.RANK_ORDER[x[1].rank])
        else:
            # This shouldn't happen - someone must have followed suit or played trump
            # But just in case, first player wins
            winning_player, winning_card = self.current_trick[0]

        return winning_player, winning_card

    async def start_playing_phase(self):
        # Start the actual card playing phase
        self.game_phase = "playing"
        self.current_player_index = 0  # Game master starts (or whoever created the lobby)
        self.lead_player_index = 0

        LOGGER.info(f"Starting playing phase. {self.get_current_player().name} leads.")
        await self.prompt_current_player()

    async def prompt_current_player(self):
        # Send the current player their hand and ask them to play a card
        current_player = self.get_current_player()
        LOGGER.info(f"Prompting {current_player.name} to play (trick has {len(self.current_trick)} cards)")
        valid_cards = self.get_valid_plays(current_player)

        # Create embed showing current game state
        embed = discord.Embed(
            title="Your Turn!",
            color=discord.Color.gold()
        )

        # Show current trick if any cards played
        if self.current_trick:
            trick_text = []
            for player, card in self.current_trick:
                trick_text.append(f"{player.name}: {format_card_emoji(card)}")
            embed.add_field(name="Current Trick", value="\n".join(trick_text), inline=False)

        # Show their hand
        hand_text = format_card_list(sorted(current_player.hand))
        embed.add_field(name="Your Hand", value=hand_text, inline=False)

        # Show valid plays if restricted
        if len(valid_cards) < len(current_player.hand):
            valid_text = format_card_list(sorted(valid_cards))
            embed.add_field(name="Valid Plays", value=valid_text, inline=False)

        embed.set_footer(text=f"Trump: {self.get_trump_emoji()}")

        try:
            card_play_view = views.CardPlayView(self, current_player, valid_cards)
            await current_player.discord_user.send(embed=embed, view=card_play_view)
        except discord.Forbidden:
            LOGGER.warning(f"Could not DM {current_player.name} for card play")

    async def announce_trick_winner(self, winning_player, winning_card):
        # Announce the trick winner to all players
        # Create trick summary
        trick_text = []
        for player, card in self.current_trick:
            if player == winning_player:
                trick_text.append(f"**{player.name}: {format_card_emoji(card)}** 🏆")
            else:
                trick_text.append(f"{player.name}: {format_card_emoji(card)}")

        embed = discord.Embed(
            title="Trick Complete!",
            description=f"**{winning_player.name}** wins!",
            color=discord.Color.gold()
        )
        embed.add_field(name="Cards Played", value="\n".join(trick_text), inline=False)

        # Add current scores
        score_text = []
        for player in self.players:
            tricks_this_hand = len(player.tricks)
            score_text.append(f"**{player.name}:** {tricks_this_hand} tricks (Total: {player.score})")

        embed.add_field(name="Current Scores", value="\n".join(score_text), inline=False)
        embed.set_footer(text=f"Trump: {self.get_trump_emoji()}")

        # Send to all players
        self.last_trick_messages = {}
        for player in self.players:
            try:
                message = await player.discord_user.send(embed=embed)
                self.last_trick_messages[player] = message
            except discord.Forbidden:
                LOGGER.warning(f"Could not send trick result to {player.name}")
                self.last_trick_messages[player] = None

    async def start_passing_phase(self):
        LOGGER.info(f"Starting passing phase for {self.discord_players}")
        for player in self.players:
            await self.send_passing_request(player)

    async def send_passing_request(self, player):
        # Send passing request with emoji formatting
        sorted_hand = sorted(player.hand)

        embed = discord.Embed(
            title="Choose 3 Cards to Pass",
            description="Select exactly 3 cards to pass to the next player",
            color=discord.Color.orange()
        )

        hand_text = format_card_list(sorted_hand)
        embed.add_field(name="Your Hand", value=hand_text, inline=False)

        try:
            view = views.CardPassingView(self, player, sorted_hand)
            await player.discord_user.send(embed=embed, view=view)
        except discord.Forbidden:
            LOGGER.warning(f"Could not DM {player.name} for card passing")

    async def process_card_passing(self, player, cards_to_pass):
        # Handle when a player passes their cards
        # Remove cards from player's hand
        for card in cards_to_pass:
            player.hand.remove(card)

        # Find next player (player to the left)
        current_index = self.players.index(player)
        next_index = (current_index + 1) % len(self.players)
        next_player = self.players[next_index]

        # Store the passed cards
        self.passed_cards[player] = cards_to_pass

        LOGGER.info(f"{player.name} passed {len(cards_to_pass)} cards to {next_player.name}")

        # Check if all players have passed
        if len(self.passed_cards) == len(self.players):
            await self.complete_passing_phase()

    async def complete_passing_phase(self):
        # Give players their received cards after everyone has passed
        # Distribute received cards
        for i, player in enumerate(self.players):
            previous_index = (i - 1) % len(self.players)
            previous_player = self.players[previous_index]

            if previous_player in self.passed_cards:
                received_cards = self.passed_cards[previous_player]
                player.hand.extend(received_cards)

        # Send updated hands to all players
        for i, player in enumerate(self.players):
            previous_index = (i - 1) % len(self.players)
            previous_player = self.players[previous_index]
            received_cards = self.passed_cards.get(previous_player, [])

            sorted_hand = sorted(player.hand)
            hand_text = format_card_list(sorted_hand, passed_cards=received_cards)

            embed = discord.Embed(
                title="Your Updated Hand",
                description=hand_text,
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Bold cards were passed to you by {previous_player.name} | Trump: {self.get_trump_emoji()}")

            try:
                await player.discord_user.send(embed=embed)
            except discord.Forbidden:
                LOGGER.warning(f"Could not send updated hand to {player.name}")

        await self.start_playing_phase()

    def deal_cards(self):
        random.shuffle(self.deck)
        num_players = len(self.players)
        hand_size = len(self.deck) // num_players
        for i, player in enumerate(self.players):
            player.hand = self.deck[i * hand_size:(i + 1) * hand_size]

    async def send_hands_to_players(self):
        for player in self.players:
            sorted_hand = sorted(player.hand)
            hand_text = format_card_list(sorted_hand)

            embed = discord.Embed(
                title="Your Hand",
                description=f"{hand_text}\n\n**Trumps this round:** {self.get_trump_emoji()}",
                color=discord.Color.blue()
            )

            try:
                await player.discord_user.send(embed=embed)
                LOGGER.info(f"Sent hand to {player.name}")
            except discord.Forbidden:
                LOGGER.warning(f"Could not DM {player.name} - DMs might be disabled")
                # Could fallback to ephemeral message in channel here

    def show_hands(self):
        for player in self.players:
            sorted_hand = sorted(player.hand)
            hand_display = format_card_list(sorted_hand)
            print(f"\n{player.name}'s hand:")
            print(hand_display)