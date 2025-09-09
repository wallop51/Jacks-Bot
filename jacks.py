import logging
import random
import views

import discord
from discord import Member

SUITS = ["Hearts", "Clubs", "Diamonds", "Spades"]
RANKS = ["3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

LOGGER = logging.getLogger(__name__)

class Card:
    # Define the order for suits and ranks
    SUIT_ORDER = {'Hearts': 0, 'Clubs': 1, 'Diamonds': 2, 'Spades': 3}
    RANK_ORDER = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                  '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}

    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank

    def __repr__(self):
        return f"{self.rank} of {self.suit}"

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
        self.deal_cards()

    def deal_cards(self):
        random.shuffle(self.deck)
        num_players = len(self.players)
        hand_size = len(self.deck) // num_players
        for i, player in enumerate(self.players):
            player.hand = self.deck[i * hand_size:(i + 1) * hand_size]

    async def send_hands_to_players(self):
        #DM players hands
        for player in self.players:
            sorted_hand = sorted(player.hand)
            hand_text = ", ".join(str(card) for card in sorted_hand)

            embed = discord.Embed(
                title="Your Hand",
                description=hand_text,
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
            print(f"\n{player.name}'s hand:")
            print(", ".join(map(str, sorted_hand)))
