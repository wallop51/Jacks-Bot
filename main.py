import logging
from logging.handlers import RotatingFileHandler

import discord
from discord import app_commands
from jacks import PreGame, Game
from discord.ext import commands
from dotenv import load_dotenv
import os

from views import CreateLobbyView

#Setup logger
handler = RotatingFileHandler(
    'discord.log',
    maxBytes=5*1024*1024,  # 5MB per file
    backupCount=3,          # Keep 3 old files
    encoding='utf-8'
)
logging.basicConfig(
    handlers=[handler],
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

LOGGER = logging.getLogger(__name__)

#load .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

active_pregames = {}


bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

@bot.event
async def on_ready():
    LOGGER.info('Logged in as %s' % bot.user.name)
    try:
        synced = await bot.tree.sync()
        LOGGER.info(f'Synced {len(synced)} commands')
    except Exception as e:
        LOGGER.error(f"Sync failed: {e}")
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    LOGGER.info(f"[{message.author} in #{message.channel}] {message.content}")

@bot.tree.command(name="help")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Help",
        color=discord.Color.orange()
    ).add_field(
        name="Learn How to Play",
        value="https://www.tiktok.com/@jacks.master/video/7079103590769478917",
                inline=False
    ).add_field(name="Commands",
                value="**/jacks** - create a new lobby\n"
                      "**/cancelgame** - close the lobby\n"
                      "**/remove** `@user` - kick a player from the lobby\n"
                      "**/leavegame** - leave a lobby\n"
                      "**/ready** - start the game",
                inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="jacks")
async def create_lobby(interaction: discord.Interaction):
    channel_id = interaction.channel_id

    # Check if there's already a game in this channel
    if channel_id in active_pregames:
        await interaction.response.send_message("There's already a Jacks game in this channel!", ephemeral=True)
        return

    pregame = PreGame(interaction)  # Updated to use direct import
    active_pregames[channel_id] = pregame
    await pregame.create_lobby(interaction.user)


@bot.tree.command(name="remove")
@app_commands.describe(player="The player to kick from the game")
async def kick_player(interaction: discord.Interaction, player: discord.Member):
    channel_id = interaction.channel_id

    # Check if there's a game in this channel
    if channel_id not in active_pregames:
        await interaction.response.send_message("No active Jacks game in this channel!", ephemeral=True)
        return

    pregame = active_pregames[channel_id]

    # Check if the user trying to kick is the game master
    if interaction.user != pregame.master:
        await interaction.response.send_message("Only the game master can kick players!", ephemeral=True)
        return

    # Check if the player is actually in the game
    if player not in pregame.players:
        await interaction.response.send_message(f"{player.mention} is not in the game!", ephemeral=True)
        return

    # Don't allow kicking yourself (the master)
    if player == pregame.master:
        await interaction.response.send_message("You cannot kick yourself! Use a different command to cancel the game.",
                                                ephemeral=True)
        return

    # Remove the player
    pregame.players.remove(player)
    LOGGER.info(f"{interaction.user} kicked {player} from the game in {interaction.channel.name}")

    await interaction.response.send_message(
        f"{player.mention} has been kicked from the game by {interaction.user.mention}.")


@bot.tree.command(name="leavegame")
async def leave_game(interaction: discord.Interaction):
    channel_id = interaction.channel_id

    # Check if there's a game in this channel
    if channel_id not in active_pregames:
        await interaction.response.send_message("No active Jacks game in this channel!", ephemeral=True)
        return

    pregame = active_pregames[channel_id]

    # Check if the player is in the game
    if interaction.user not in pregame.players:
        # Check if they're the master
        if interaction.user == pregame.master:
            await interaction.response.send_message("As the game master, use `/cancel` to cancel the game instead.",
                                                    ephemeral=True)
        else:
            await interaction.response.send_message("You're not in this game!", ephemeral=True)
        return

    # Remove the player
    pregame.players.remove(interaction.user)
    LOGGER.info(f"{interaction.user} left the game in {interaction.channel.name}")

    await interaction.response.send_message(f"{interaction.user.mention} has left the game.")


@bot.tree.command(name="cancelgame")
async def cancel_game(interaction: discord.Interaction):
    channel_id = interaction.channel_id

    # Check if there's a game in this channel
    if channel_id not in active_pregames:
        await interaction.response.send_message("No active Jacks game in this channel!", ephemeral=True)
        return

    pregame = active_pregames[channel_id]

    # Check if the user is the game master
    if interaction.user != pregame.master:
        await interaction.response.send_message("Only the game master can cancel the game!", ephemeral=True)
        return

    if pregame.lobby_message:
        disabled_view = CreateLobbyView(pregame)
        for item in disabled_view.children:
            item.disabled = True

        embed = discord.Embed(title="Jacks - CANCELLED",
                              description=f"~~{pregame.master.mention} has started a Jacks game!~~\n**This game has been cancelled.**")
        await pregame.lobby_message.edit(embed=embed, view=disabled_view)

    # Remove the game
    del active_pregames[channel_id]

    LOGGER.info(f"{interaction.user} cancelled the game in {interaction.channel.name}")

    await interaction.response.send_message(f"The Jacks game has been cancelled by {interaction.user.mention}.")

@bot.tree.command(name="ready")
async def ready(interaction: discord.Interaction):
    channel_id = interaction.channel_id

    if channel_id not in active_pregames:
        await interaction.response.send_message("No active Jacks game in this channel!", ephemeral=True)
        return

    pregame = active_pregames[channel_id]

    if interaction.user != pregame.master:
        await interaction.response.send_message(f"Only {pregame.master.mention} can start the game.", ephemeral=True)
        return

    if len(pregame.players) < 3 or len(pregame.players) > 4:
        await interaction.response.send_message("Jacks can only be played with 3 or 4 players.", ephemeral=True)
        return

    if pregame.lobby_message:
        await pregame.lobby_message.delete()

    await interaction.response.send_message(f"Game started! Check your DMs for your hand.")

    #Start game
    game = Game(pregame.players)
    await game.send_hands_to_players()
    await game.start_passing_phase()


    # TODO store active game
    # active_games[channel_id] = game

    del active_pregames[channel_id]
bot.run(TOKEN)