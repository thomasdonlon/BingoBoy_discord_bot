import random
from discord import NotFound
from text_storage import item_descriptions, skill_level_descriptions

#---------------------------------
# SQL Text Sanitization and Helpers
#---------------------------------

def sanitize_text(text):
    """
    Cleans the text to remove any naughty SQL characters. This also prevents the chatgpt output from breaking the SQL query.
    """

    #replace any pause characters with a corresponding code to try to retain the original formatting
    text = text.replace(':', '$c').replace(';', '$s').replace('--', '$m').replace('-', '$n').replace("'", '$q').replace('"', '$d')

    #remove any naughty characters that could be used for SQL injection or other nefarious purposes (or just break the query)
    naughty_strings = ['\\', '(', ')', '[', ']', '{', '}', '<', '>', '=', '@', '#', '%', '^', '&', '*', '+', '/', '|', '~']

    for naughty in naughty_strings:
        text = text.replace(naughty, '')
    
    return text.strip()

def replace_text_codes(text):
    """
    Replaces text codes with their original characters.
    This is used to restore the original formatting after sanitization.
    """
    
    text = text.replace('$c', ':').replace('$s', ';').replace('$m', '--').replace('$n', '-').replace('$q', "'").replace('$d', '"')
    
    return text.strip()

#---------------------------------
# Helpers
#---------------------------------

def get_item_name(item_id):
    """
    Returns the name of the item based on its ID.
    """
    if item_id in item_descriptions:
        return item_descriptions[item_id]
    else:
        return "Unknown Item"
    
def get_skill_description(skill, level):
    """
    Returns the description of a skill at a given level.
    """
    if skill in skill_level_descriptions and level in skill_level_descriptions[skill]:
        return skill_level_descriptions[skill][level]
    else:
        return "Unknown Skill Level"
    
async def ctx_print(state, text, ephemeral=False):
    try: #try a deferred context response 
        await state.ctx.followup.send(text, ephemeral=ephemeral)
    except NotFound: #if the deferred response fails, send a regular interaction message instead
        await state.ctx.response.send_message(text, ephemeral=ephemeral)

#----------------------------------
# Helpers for Player Data
#----------------------------------

async def get_player_x(state, x):
	async with state.bot.pool.acquire() as con:
		return await con.fetchval(f"SELECT {x} FROM data WHERE name = '{state.player}'")

async def set_player_x(state, x, val):                                                                  
	async with state.bot.pool.acquire() as con:
		await con.execute(f"UPDATE data SET {x} = '{val}' WHERE name = '{state.player}'")

	return val
	#return await get_player_x(state, state.player, x)

async def increment_player_x(state, x, num):                                                                  
	async with state.bot.pool.acquire() as con:
		current_val = await get_player_x(state, x)
		val = current_val + num
		await con.execute(f"UPDATE data SET {x} = '{val}' WHERE name = '{state.player}'")

	return val

async def inventory_contains(state, item):
	inventory_text = await get_player_x(state, 'inventory')
	inventory_text = inventory_text.split(',')
	return item in inventory_text

#----------------------------------
# Random functionality that includes the items that change percentages for skills and items
#----------------------------------

async def random_with_bonus(state):
    """
    Returns a random number between 0 and 1, plus any bonuses from the player's skills and items
    """

    bonus = 0.

    agility_level = await get_player_x(state, 'agility_level')
    mult = 2 if agility_level > 35 else 1 #a couple edge cases for Agility Master

    # Tankard of Tenacity (d7): +0.02 per banked debauchery task
    if await inventory_contains(state, 'd7'):
        debauchery = await get_player_x(state, 'debauchery_avail')
        bonus += debauchery * 0.02 * mult

    # Sleight of Hand (Agility 15): +0.15 to all percentage-based effects
    if agility_level >= 15:
        bonus += 0.15 * mult

    # Agility Master (Agility 35): Double the base percentage of all item and skills
    if agility_level >= 35:
        return (random.random() - bonus)/2 #equal to rand_num < 2*chance + bonus, i.e. doubling the base chance

    return random.random() - bonus #subtracting the bonus makes the number more likely to hit
