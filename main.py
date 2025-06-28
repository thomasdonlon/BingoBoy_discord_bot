#central functionality of the bot, plus front-end command control

#TODO: add name of character, and use channel id to track player data rather than using channel name as player name
#TODO: Add skills
#TODO: add items
#TODO: test the undo system

import os, logging, asyncpg
import player
from quest import format_quest_status, Quest
from utils import get_item_name, inventory_contains, ctx_print, get_player_x
from typing import Literal, Optional
import hashlib

import discord
from discord.ext import commands, tasks
import openai

openai.api_key =        os.getenv('OPENAI_API_KEY')
TOKEN =                 os.getenv('DISCORD_TOKEN')
PG_USER =               os.getenv('PGUSER')
PG_PW =                 os.getenv('PGPASSWORD')
PG_HOST =               os.getenv('PGHOST')
PG_PORT =               os.getenv('PGPORT')
PG_DB =                 os.getenv('PGPDATABASE')

test_guild_id = 1371909216138166474  #ID of the test server, which can be used to globally sync commands
whitelist = (1371909216138166474,)  #currently only whitelisting the test server, add more IDs as needed
summary_channel_id = 1373405473209847949  #channel ID for the bot status display, where the bot will post the player status updates

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='$', intents=intents)
tree = bot.tree

pass_hash = '714bbceba09595a65bf4c9c15e4a9d35302009cc6de1c684c636876ef0d8d863' #hash used to password protect the bot commands we really don't want other people running

#--------------------------------------
# HELPERS/CONVENIENCE
#--------------------------------------

#this helps pass the needed context into subroutines (without passing a bunch of values by hand)
#can edit this and add more if we need to later on
#there is probably a better way to do this that I'm not aware of, but here we are
class State:
    def __init__(self, bot, ctx, player):
        self.bot = bot
        self.ctx = ctx
        self.player = player

display_running = False #tracks whether the status display is running or not
display_embed = None #this is the embed that will be edited with the current player status

#edits a message with the current state of each player
#performs this action every 10 seconds
@tasks.loop(seconds = 10, reconnect=True)
async def display_player_status():
    global display_embed
    try:
        async with bot.pool.acquire() as con:
            players = await con.fetch('SELECT * FROM data')

        if not players:
            return

        embed = discord.Embed(title="Player Status", color=discord.Color.blue())
        for player in players:
            inventory_text = ', '.join([get_item_name(item).split(':')[0] for item in player['inventory'].split(',')]) if player['inventory'] else 'Empty'
            embed.add_field(name=player['name'], value=f"Level: {player['level']}\nXP: {player['xp']}\nStrength: {player['strength_level']}\nAgility: {player['agility_level']}\nWisdom: {player['wisdom_level']}\nQuests: Easy - {player['easy_quest']}, Medium - {player['medium_quest']}, Hard - {player['hard_quest']}\nSidequests: {player['sidequest']}\nInventory: {inventory_text}", inline=False)

        channel = bot.get_channel(summary_channel_id)  # Replace with your channel ID
        if channel:
            if display_embed:
                await display_embed.edit(embed=embed)
            else:
                display_embed = await channel.send(embed=embed)

    except Exception as e:
        print(f'display_player_status threw an error: {e}')

#decorator that runs a function as a try/except block, catching any exceptions and printing them to the console
def run_with_error_handling(func : callable) -> callable:
    """Decorator to run a function with error handling."""
    async def wrapper(*args : tuple, **kwargs : dict) -> None:
        #the first argument is expected to be a ctx object
        ctx = args[0]
        if not isinstance(ctx, discord.Interaction) and not isinstance(ctx, discord.Message):
            raise ValueError("First argument in function must be a discord.Interaction or discord.Message object for run_with_error_handling decorator.")
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            await ctx.reply("Error (something went wrong - check bot logs)")
            print(f'Error in {func.__name__}: {e}')
    return wrapper

def is_valid_task_name(task_name):
    # Check if the task name is valid
    # A task name should be a single letter ('e', 'c', 'p', 'd', or 'b') plus an arbitrary number of numeric characters
    return bool(task_name) and task_name[0].isalpha() and task_name[1:].isdigit() and task_name[0] in ('e', 'c', 'p', 'd', 'b')

async def end_game(winning_player):
    #stop the status display if it's running
    global display_running
    if display_running:
        display_running = False
        print(f"Status display stopped.")
        display_player_status.stop()
    else:
        print(f"Status display is not running.")

    #print a message to the summary channel
    channel = bot.get_channel(summary_channel_id)  # Replace with your channel ID
    if channel:
        await channel.send(f"{winning_player} has defeated the Drunken Dragon! Thanks for playing!")
        await channel.send(f"The game will continue to run if you wish to keep playing for fun. However, the game has officially ended.")

#--------------------------------------
# BOT SETUP
# These are basic discord functionality that let the bot run
#--------------------------------------

@bot.event
async def on_ready():
    bot.pool = await asyncpg.create_pool(user=PG_USER, password=PG_PW, host=PG_HOST, port=PG_PORT, database=PG_DB, max_size=10, max_inactive_connection_lifetime=15)
    logger = logging.getLogger('discord')
    logger.setLevel(logging.INFO)    
    print(f'{bot.user} is connected to the following guild(s):')

    for guild in bot.guilds:
        print(f'{guild.name} (id: {guild.id})')

    #create the task table if it doesn't exist
    #the tasks table has a name column for the player name, 
    #and an arbitrary number of task columns that can be added later
    async with bot.pool.acquire() as con:   
        await con.execute(f'''CREATE TABLE IF NOT EXISTS tasks (
            name				  VARCHAR PRIMARY KEY NOT NULL
            )''')
    
@bot.event
async def on_guild_join(guild:discord.Guild):
    if guild.id not in whitelist: 
        await guild.leave()
        print(f"[X][X] {guild.name} is not in whitelist, leaving...")
        return

    print(f"added to {guild}")

@bot.event
async def on_guild_remove(guild:discord.Guild):
    async with bot.pool.acquire() as con:
        await con.execute(f'DELETE FROM context WHERE id = {guild.id}')

    print(f"removed from {guild}")

# see https://about.abstractumbra.dev/discord.py/2023/01/29/sync-command-example.html for usage of this command
# it is generally enough to run $sync and then $sync *
#@commands.is_owner()
@bot.command()
@commands.guild_only()
async def sync(ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()

        await ctx.send(
            f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return

    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

#--------------------------------------
# ADMIN COMMANDS/TOOLS
#--------------------------------------

@run_with_error_handling
@tree.command(name="init_channel", description="Start bot in this channel (Admin Only).")
@commands.has_role('Admin')
async def init_channel(ctx : discord.Interaction) -> None:
    state = State(bot, ctx, ctx.channel.name)
    await player.init(state)

    #create the task table if it doesn't exist
    async with bot.pool.acquire() as con:
        await con.execute(f'''CREATE TABLE IF NOT EXISTS tasks (
                    name				  VARCHAR PRIMARY KEY NOT NULL
                    )''')
        
        #add the player to the task table if they aren't already in it
        await con.execute(f"INSERT INTO tasks(name) VALUES('{state.player}') ON CONFLICT DO NOTHING")

    #verification message
    await ctx.response.send_message(f"Done. Initialized channel.", ephemeral=True)

@run_with_error_handling
@tree.command(name="override", description="Manual value override for debugging/triage (Admin Only).")
@commands.has_role('Admin')
async def override(ctx : discord.Interaction, password : str, player : str, parameter_name : str, value : str) -> None:
    if hashlib.sha256(bytes(password.encode('utf-8'))).hexdigest() != pass_hash:
        await ctx.response.send_message("Error: Invalid password.", ephemeral=True)
        return
    async with bot.pool.acquire() as con:
        await con.execute(f"UPDATE data SET {parameter_name} = '{value}' WHERE name = '{player}'")
    await ctx.response.send_message(f"Value override successful.", ephemeral=True)

@run_with_error_handling
@tree.command(name="start_status_display", description="Starts the game status tracker in this channel (Admin Only).")
async def start_status_display(ctx : discord.Interaction) -> None:
    global display_running
    if not display_running:
        display_running = True
        await ctx.response.send_message(f"Status display started.", ephemeral=True)
        display_player_status.start()
    else:
        await ctx.response.send_message(f"Status display is already running.", ephemeral=True)

@run_with_error_handling
@tree.command(name="stop_status_display", description="Stops the game status tracker (Admin Only).")
async def stop_status_display(ctx : discord.Interaction) -> None:
    global display_running
    if display_running:
        display_running = False
        await ctx.response.send_message(f"Status display stopped.", ephemeral=True)
        display_player_status.stop()
    else:
        await ctx.response.send_message(f"Status display is not running.", ephemeral=True)

@run_with_error_handling
@tree.command(name="reset_game", description="Resets the game data (Admin Only).")
async def reset_game(ctx : discord.Interaction, password : str) -> None:
    if hashlib.sha256(bytes(password.encode('utf-8'))).hexdigest() != pass_hash:
        await ctx.response.send_message("Error: Invalid password.", ephemeral=True)
        return
    async with bot.pool.acquire() as con:
        await con.execute(f"DROP TABLE data")
        await con.execute(f"DROP TABLE tasks")
    await ctx.response.send_message(f"Game data reset.", ephemeral=True)

#--------------------------------------
# PLAYER COMMANDS
#--------------------------------------

@run_with_error_handling
@tree.command(name="quest", description="Manages a quest.")
async def quest(ctx : discord.Interaction, action : str, difficulty : str = None) -> None:
    state = State(bot, ctx, ctx.channel.name)

    #check if the action is valid
    if action not in ('start', 'progress', 'abandon'):
        await ctx.response.send_message("Error: Invalid action. Must be 'start', 'progress', or 'abandon'.", ephemeral=True)
        return

    if action == 'start':
        #ensure there is a difficulty argument
        if not difficulty:
            await ctx.response.send_message("Error: You must specify a difficulty for the quest. Use 'easy' ('e'), 'medium' ('m'), or 'hard' ('h').", ephemeral=True)
            return
        
        #ensure the player has no current quest
        async with bot.pool.acquire() as con:
            if await get_player_x(state, 'current_quest'):
                await ctx.response.send_message("Error: You already have a quest in progress. Please complete or abandon it before starting a new one.", ephemeral=True)
                return

        #start the quest with the given difficulty
        #check that the difficulty is valid, and convert it to a full word if necessary
        if difficulty in ('easy', 'medium', 'hard', 'e', 'm', 'h', 'drunken-dragon'):
            if difficulty in ('e', 'easy'):
                difficulty = 'easy'
            elif difficulty in ('m', 'medium'):
                difficulty = 'medium'
            elif difficulty in ('h', 'hard'):
                difficulty = 'hard'
        else:
            #invalid difficulty
            print(f"ERROR start_quest PLAYER: {state.player} THREW: Invalid quest difficulty: {difficulty}")
            await state.ctx.response.send_message("Error: Invalid quest difficulty. Must be 'easy', 'medium', or 'hard'.")
            return

        await state.ctx.response.defer() #this takes a while to interact with chatgpt
        await player.start_quest(state, difficulty)
    
    elif action == 'progress':
        #progress the quest
        await state.ctx.response.defer() #this takes a while to interact with chatgpt
        progress_result = await player.progress_quest(state) #is only not None if the quest is completed
        if progress_result == 'drunken-dragon':
            end_game(ctx.channel)

    elif action == 'abandon':
        #abandon the quest
        await player.abandon_quest(state)

@run_with_error_handling
@tree.command(name="sidequest", description="Completes a sidequest.")
async def sidequest(ctx : discord.Interaction, task_type : str) -> None:
    state = State(bot, ctx, ctx.channel.name)

    #check if the task type is valid
    if task_type not in ('exploration', 'combat', 'puzzle', 'dialogue', 'debauchery', 'e', 'c', 'p', 'd', 'b'):
        await ctx.response.send_message("Error: Invalid task type. Must be 'exploration', 'combat', 'puzzle', 'dialogue', or 'debauchery'.", ephemeral=True)
        return
    #convert the task type to a full word if it is a single letter
    if task_type in ('e', 'exploration'):
        task_type = 'exploration'
    elif task_type in ('c', 'combat'):
        task_type = 'combat'
    elif task_type in ('p', 'puzzle'):
        task_type = 'puzzle'
    elif task_type in ('d', 'dialogue'):
        task_type = 'dialogue'
    elif task_type in ('b', 'debauchery'):
        task_type = 'debauchery'
    
    await state.ctx.response.defer() #this takes a while to interact with chatgpt
    await player.complete_sidequest(state, task_type)
    #await ctx.response.send_message("Sidequest completed!", ephemeral=True)

@run_with_error_handling
@tree.command(name="status", description="Shows your current status.")
async def status(ctx : discord.Interaction) -> None:
    state = State(bot, ctx, ctx.channel.name)

    async with bot.pool.acquire() as con:
        current_player = await con.fetch('SELECT * FROM data WHERE name = $1', state.player)
        current_player = current_player[0] if current_player else None

        if not current_player:
            return

    embed = discord.Embed(title=f"{current_player['name']}", color=discord.Color.green())
    embed.add_field(name="Level", value=current_player['level'], inline=True)
    embed.add_field(name="XP", value=current_player['xp'], inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True) #workaround for inline spacing
    embed.add_field(name="Strength", value=current_player['strength_level'], inline=True)
    embed.add_field(name="Agility", value=current_player['agility_level'], inline=True)
    embed.add_field(name="Wisdom", value=current_player['wisdom_level'], inline=True)
    embed.add_field(name="Skill Points", value=current_player['skill_points'], inline=False)
    embed.add_field(name="Quests", value=f"Easy: {current_player['easy_quest']}, Medium: {current_player['medium_quest']}, Hard: {current_player['hard_quest']}", inline=False)
    embed.add_field(name="Item Points:", value=f"Easy: {current_player['easy_quest_points']}, Medium: {current_player['medium_quest_points']}, Hard: {current_player['hard_quest_points']}", inline=False)
    current_quest = await Quest.from_state(state) if current_player['current_quest'] else None
    if current_quest:
        embed.add_field(name="Current Quest", value=format_quest_status(current_quest), inline=False)
    else:
        embed.add_field(name="Current Quest", value="None", inline=False)
    embed.add_field(name="Sidequests", value=current_player['sidequest'], inline=False)
    embed.add_field(name="Tasks", value=f"Exploration: {current_player['exploration_avail']}\nCombat: {current_player['combat_avail']}\nPuzzle-Solving: {current_player['puzzle_avail']}\nDialogue: {current_player['dialogue_avail']}\nDebauchery: {current_player['debauchery_avail']}\n", inline=False)
    inventory_text = '\n'.join([get_item_name(item).split(':')[0] for item in current_player['inventory'].split(',')]) if current_player['inventory'] else 'Empty'
    embed.add_field(name="Inventory", value=inventory_text, inline=False)

    await ctx.response.send_message(embed=embed, ephemeral=True)

@run_with_error_handling
@tree.command(name="task", description="Log the completion of a task.")
async def task(ctx : discord.Interaction, task_name : str, task_to_undo : str = None) -> None:

    state = State(bot, ctx, ctx.channel.name)

    #if task_name is 'undo', remove the last task logged or look for a specific task to remove
    if task_name == 'undo':
        if not task_to_undo:
            task_to_undo = await player.get_last_logged_task(state)
        elif not is_valid_task_name(task_to_undo):
            await ctx.response.send_message("Error: Invalid task name. Must start with 'e', 'c', 'p', 'd', or 'b', followed by numbers.", ephemeral=True)
            return
            
        #then decrement the task count in the database
        async with bot.pool.acquire() as con:
            # Check if the task exists
            existing_tasks = await con.fetch('SELECT column_name FROM information_schema.columns WHERE table_name = $1', 'tasks')
            task_columns = [row['column_name'] for row in existing_tasks]

            if task_to_undo not in task_columns:
                await ctx.response.send_message(f"Error: Task '{task_to_undo}' does not exist.", ephemeral=True)
                return

            # Decrement the task count
            await con.execute(f'UPDATE tasks SET {task_to_undo} = GREATEST({task_to_undo} - 1, 0) WHERE name = $1', state.player)

        #then take away the points from the player
        await player.remove_task(state, task_to_undo)

    else:

        #check if the task name is valid
        #a task name should be a single letter ('e', 'c', 'p', 'd', or 'b') plus an arbitrary number of numeric characters
        if not is_valid_task_name(task_name):
            await ctx.response.send_message("Error: Invalid task name. Must start with 'e', 'c', 'p', 'd', or 'b', followed by numbers.", ephemeral=True)
            return

        async with bot.pool.acquire() as con:
            # Check if the task already exists
            # if not, create a column for that task
            existing_tasks = await con.fetch('SELECT column_name FROM information_schema.columns WHERE table_name = $1', 'tasks')
            task_columns = [row['column_name'] for row in existing_tasks]

            # Insert the task into the tasks table if it doesn't already exist
            if task_name not in task_columns:
                # Create a new column for the task
                await con.execute(f'ALTER TABLE tasks ADD COLUMN IF NOT EXISTS {task_name} INTEGER DEFAULT 0')

            #check that the player hasn't logged this task 5 times already
            # and that they don't have the mead of madness item (m9)
            if task_name[0] != 'b' and not await inventory_contains(state, 'm9'): #debauchery tasks can be completed as many times as you want, and mead of madness allows you to complete non-debauchery tasks without limit
                query_result = await con.fetch(f'SELECT {task_name} FROM tasks WHERE name = $1', state.player) 
                num_completions = query_result[0][task_name] #get the value we care about out of the query
                if num_completions >= 5:
                    await ctx.response.send_message(f"Task '{task_name}' cannot be logged more than 5 times.", ephemeral=True)
                    return
                
            # Then, increment its count
            await con.execute(f'UPDATE tasks SET {task_name} = {task_name} + 1 WHERE name = $1', state.player)
    
        # Log the task completion in the player's data
        await state.ctx.response.defer() #this can take a little while sometimes
        await player.log_task(state, task_name)

        # Send a confirmation message
        await ctx_print(state, f"Task '{task_name}' logged successfully.", ephemeral=True)

@run_with_error_handling
@tree.command(name="skill", description="Level up a skill.")
async def skill(ctx : discord.Interaction, skill_name : str, number : int) -> None:
    state = State(bot, ctx, ctx.channel.name)
    await state.ctx.response.defer() #this can take a little while sometimes
    await player.allocate_skill_points(state, skill_name, number)
    
@run_with_error_handling
@tree.command(name="item", description="Buy an item from the shop.")
async def item(ctx : discord.Interaction, item_name : str) -> None:
    state = State(bot, ctx, ctx.channel.name)
    await state.ctx.response.defer() #this can take a little while sometimes
    await player.buy_item(state, item_name) #this function handles all the purchase logic and checks for valid inputs, etc.
    
#--------------------------------------

bot.run(TOKEN)
