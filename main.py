#central functionality of the bot, plus front-end command control

#TODO: generalize error handling throughout this whole package

import os, logging, asyncpg
import player
from quest import format_quest_status, Quest
from text_storage import get_item_name

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
    try:
        async with bot.pool.acquire() as con:
            players = await con.fetch('SELECT * FROM data')

        if not players:
            return

        embed = discord.Embed(title="Player Status", color=discord.Color.blue())
        for player in players:
            inventory_text = ', '.join([get_item_name(item) for item in player['inventory']]) if player['inventory'] else 'Empty'
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
    logger.setLevel(logging.DEBUG)    
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

# @bot.tree.command(name='sync', description='Owner only')
# @commands.is_owner()
# @run_with_error_handling
# async def sync(interaction: discord.Interaction):
#     await bot.tree.sync()
#     print('Global command tree synced.')

# @discord.app_commands.guilds(discord.Object(id = test_guild_id))
# async def sync_test(interaction: discord.Interaction):
#     await bot.tree.sync(guild=discord.Object(id=test_guild_id))

# @bot.slash_command(name="sync", description="Start bot in this channel (Admin Only).")
# async def sync(ctx : discord.Interaction):
#     fmt = await bot.tree.sync()
#     await ctx.send(f"{len(fmt)} commands synced.")
#     print('Global command tree synced.')

# @bot.command()
# @commands.is_owner()
# async def sync(ctx: commands.Context) -> None:
#     """Sync commands"""
#     synced = await ctx.bot.tree.sync()
#     await ctx.send(f"Synced {len(synced)} commands globally")

@bot.command()
@commands.is_owner()
async def sync(ctx: commands.Context) -> None:
    """Sync commands"""
    synced = await tree.sync()
    await ctx.send(f"Synced {len(synced)} commands locally.")

@tree.command(name="global_sync", description="Sync tree across all guilds (Owner Only).")
@commands.is_owner()
async def global_sync(ctx : discord.Interaction) -> None:
    """Sync tree across all guilds (Owner Only)."""
    await ctx.response.defer()  # Acknowledge the interaction immediately
    print("Starting global sync...")

    #sync to all whitelisted guilds
    guilds = [discord.Object(id=x) for x in whitelist]
    for guild in guilds:
        synced = await tree.sync(guild=guild)

    print(f"Global sync complete. Synced {len(synced)} commands.")
    await ctx.followup.send(f"Synced {len(synced)} commands globally.")

#--------------------------------------
# ADMIN COMMANDS/TOOLS
#--------------------------------------

@run_with_error_handling
@tree.command(name="init_channel", description="Start bot in this channel (Admin Only).")
@commands.has_role('Admin')
async def init_channel(ctx : discord.Interaction) -> None:
    await player.init(State(bot, ctx, ctx.channel))
    await ctx.response.send_message(f"Done. Initialized channel.", ephemeral=True)

@run_with_error_handling
@tree.command(name="override", description="Manual value override for debugging/triage (Admin Only).")
@commands.has_role('Admin')
async def override(ctx : discord.Interaction, player : str, parameter_name : str, value : str) -> None:
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

#--------------------------------------
# PLAYER COMMANDS
#--------------------------------------

@run_with_error_handling
@tree.command(name="quest", description="Manages a quest.")
async def quest(ctx : discord.Interaction, action : str, difficulty : str = None) -> None:
    state = State(bot, ctx, ctx.channel)

    #check if the action is valid
    if action not in ('start', 'progress', 'abandon'):
        await ctx.response.send_message("Error: Invalid action. Must be 'start', 'progress', or 'abandon'.", ephemeral=True)
        return

    if action == 'start':
        #ensure there is a difficulty argument
        args = ctx.data.get('options', [])
        if not difficulty:
            await ctx.response.send_message("Error: You must specify a difficulty for the quest. Use 'easy' ('e'), 'medium' ('m'), or 'hard' ('h').", ephemeral=True)
            return

        #start the quest with the given difficulty
        #check that the difficulty is valid, and convert it to a full word if necessary
        if difficulty not in ('easy', 'medium', 'hard', 'e', 'm', 'h', 'drunken-dragon'):
            if difficulty in ('e', 'easy'):
                difficulty = 'easy'
            elif difficulty in ('m', 'medium'):
                difficulty = 'medium'
            elif difficulty in ('h', 'hard'):
                difficulty = 'hard'
        else:
            #invalid difficulty
            print(f"ERROR start_quest PLAYER: {state.player} THREW: Invalid quest difficulty: {difficulty}")
            await state.ctx.reply("Error: Invalid quest difficulty. Must be 'easy', 'medium', or 'hard'.")
            return

        await player.start_quest(state, difficulty)
    
    elif action == 'progress':
        #progress the quest
        progress_result = await player.progress_quest(state) #is only not None if the quest is completed
        if progress_result == 'drunken-dragon':
            end_game(ctx.channel)

    elif action == 'abandon':
        #abandon the quest
        await player.abandon_quest(state)

@run_with_error_handling
@tree.command(name="sidequest", description="Completes a sidequest.")
async def sidequest(ctx : discord.Interaction) -> None:
    state = State(bot, ctx, ctx.channel)
    await player.complete_sidequest(state)
    #await ctx.response.send_message("Sidequest completed!", ephemeral=True)

@run_with_error_handling
@tree.command(name="status", description="Shows your current status.")
async def status(ctx : discord.Interaction) -> None:
    state = State(bot, ctx, ctx.channel)

    async with bot.pool.acquire() as con:
        current_player = await con.fetch('SELECT * FROM data WHERE id = $1', ctx.channel)
        current_player = current_player[0] if current_player else None

        if not current_player:
            return

    embed = discord.Embed(title=f"{current_player['name']}'", color=discord.Color.green())
    embed.add_field(name="Level", value=current_player['level'], inline=True)
    embed.add_field(name="XP", value=current_player['xp'], inline=True)
    embed.add_field(name="Strength", value=current_player['strength_level'], inline=True)
    embed.add_field(name="Agility", value=current_player['agility_level'], inline=True)
    embed.add_field(name="Wisdom", value=current_player['wisdom_level'], inline=True)
    embed.add_field(name="Skill Points", value=current_player['skill_points'], inline=True)
    embed.add_field(name="Quests", value=f"Easy: {current_player['easy_quest']}, Medium: {current_player['medium_quest']}, Hard: {current_player['hard_quest']}", inline=False)
    embed.add_field(name="Item Points:", value=f"Easy: {current_player['easy_quest_points']}, Medium: {current_player['medium_quest_points']}, Hard: {current_player['hard_quest_points']}", inline=False)
    current_quest = await Quest.from_state(state) if current_player['current_quest'] else 'None'
    if current_quest:
        embed.add_field(name="Current Quest", value=format_quest_status(current_quest), inline=False)
    embed.add_field(name="Sidequests", value=current_player['sidequest'], inline=False)
    embed.add_field(name="Tasks", value=f"Exploration: {current_player['exploration_avail']}\nCombat: {current_player['combat_avail']}\nPuzzle-Solving: {current_player['puzzle_avail']}\nDialogue: {current_player['dialogue_avail']}, \nDebauchery: {current_player['debauchery_avail']}\n", inline=False)
    inventory_text = '\n'.join([get_item_name(item) for item in current_player['inventory']]) if current_player['inventory'] else 'Empty'
    embed.add_field(name="Inventory", value=inventory_text, inline=False)

    await ctx.response.send_message(embed=embed, ephemeral=True)

@run_with_error_handling
@tree.command(name="task", description="Log the completion of a task.")
async def task(ctx : discord.Interaction, task_name : str, task_to_undo : str = None) -> None:

    state = State(bot, ctx, ctx.channel)

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
                
            # Then, increment its count
            await con.execute(f'UPDATE tasks SET {task_name} = {task_name} + 1 WHERE name = $1', state.player)
    
        # Log the task completion in the player's data
        await player.log_task(state, task_name)

        # Send a confirmation message
        await ctx.response.send_message(f"Task '{task_name}' logged successfully.", ephemeral=True)

@run_with_error_handling
@tree.command(name="skill", description="Level up a skill.")
async def skill(ctx : discord.Interaction, skill_name : str, number : int) -> None:
    #check if the skill name is valid
    if skill_name not in ('strength', 'agility', 'wisdom'):
        await ctx.response.send_message("Error: Invalid skill name. Must be 'strength', 'agility', or 'wisdom'.", ephemeral=True)
        return

    #check if the level is valid
    if number < 1:
        await ctx.response.send_message("Error: Level must be a positive integer.", ephemeral=True)
        return

    state = State(bot, ctx, ctx.channel)
    await player.allocate_skill_points(state, skill_name, number)
    
@run_with_error_handling
@tree.command(name="item", description="Buy an item from the shop.")
async def item(ctx : discord.Interaction, item_name : str) -> None:
    state = State(bot, ctx, ctx.channel)
    await player.buy_item(state, item_name) #this function handles all the purchase logic and checks for valid inputs, etc.
    
#--------------------------------------

bot.run(TOKEN)
