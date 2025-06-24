#the main machinery of the game, back-end for actions a player can take

from quest import Quest
import conversation
from text_storage import xp_level_thresholds, skill_level_thresholds, sidequest_ai_prompt
from utils import get_item_name, ctx_print, get_skill_description, get_player_x, set_player_x, increment_player_x, inventory_contains
import random

#initialize the channel/player
async def init(state):
	async with state.bot.pool.acquire() as con:   
		await con.execute(f'''CREATE TABLE IF NOT EXISTS data (
						
				name				  VARCHAR PRIMARY KEY NOT NULL,
				level                 INT DEFAULT 1,
				xp                    INT DEFAULT 0,
				easy_quest            INT DEFAULT 0,
				medium_quest          INT DEFAULT 0,
				hard_quest            INT DEFAULT 0,
				easy_quest_points     INT DEFAULT 0,
				medium_quest_points   INT DEFAULT 0,
				hard_quest_points     INT DEFAULT 0,
				sidequest             INT DEFAULT 0,
				strength_level        INT DEFAULT 0,
				agility_level         INT DEFAULT 0,
				wisdom_level          INT DEFAULT 0,
				skill_points          INT DEFAULT 1,
				exploration_avail     INT DEFAULT 0,
				combat_avail          INT DEFAULT 0,
				puzzle_avail          INT DEFAULT 0,
				dialogue_avail        INT DEFAULT 0,
				debauchery_avail      INT DEFAULT 0,
				inventory             TEXT DEFAULT '',
				current_quest         TEXT DEFAULT NULL,
				last_logged_task      VARCHAR DEFAULT '',
                sq_xp_bonus         INT DEFAULT 0
				)''')

		#initialize the player data if it doesn't exist
		await con.execute(f"INSERT INTO data(name) VALUES('{state.player}') ON CONFLICT DO NOTHING")

		print(f"Initialized channel: {state.player}")

#----------------------------------
# Tasks
#----------------------------------

async def log_task(state, task_name):
    # Check for skill-based extra task completion
    extra_task = False
    extra_task_type = None
    # Get player skill levels
    strength_level = await get_player_x(state, 'strength_level')
    agility_level = await get_player_x(state, 'agility_level')
    wisdom_level = await get_player_x(state, 'wisdom_level')

    # Strength 3: 25% chance for extra combat task
    if task_name[0] == 'c' and strength_level >= 3:
        if random.random() < 0.25:
            extra_task = True
            extra_task_type = 'combat_avail'
    # Agility 3: 25% chance for extra exploration task
    elif task_name[0] == 'e' and agility_level >= 3:
        if random.random() < 0.25:
            extra_task = True
            extra_task_type = 'exploration_avail'
    # Wisdom 1: 25% chance for extra dialogue task
    elif task_name[0] == 'd' and wisdom_level >= 1:
        if random.random() < 0.25:
            extra_task = True
            extra_task_type = 'dialogue_avail'
    # Wisdom 3: 25% chance for extra puzzle task
    elif task_name[0] == 'p' and wisdom_level >= 3:
        if random.random() < 0.25:
            extra_task = True
            extra_task_type = 'puzzle_avail'

    # Normal task logging
    if task_name[0] == 'e':
        await increment_player_x(state, 'exploration_avail', 1)
    elif task_name[0] == 'c':
        await increment_player_x(state, 'combat_avail', 1)
    elif task_name[0] == 'p':
        await increment_player_x(state, 'puzzle_avail', 1)
    elif task_name[0] == 'd':
        await increment_player_x(state, 'dialogue_avail', 1)
    elif task_name[0] == 'b':
        await increment_player_x(state, 'debauchery_avail', 1)
        # Strength 1: Completing a Debauchery Task also provides +2 XP
        if strength_level >= 1:
            await award_xp(state, 2)

    # Apply extra task if triggered
    if extra_task and extra_task_type:
        await increment_player_x(state, extra_task_type, 1)
        await ctx_print(state, f"Skill bonus! You completed an extra {extra_task_type.split('_')[0]} task.")

    # Log the task in the database
    async with state.bot.pool.acquire() as con:
        await con.execute(f"UPDATE data SET last_logged_task = '{task_name}' WHERE name = '{state.player}'")

async def remove_task(state, task_name):
	#remove the task from the player's available tasks
	if task_name[0] == 'e':
		await increment_player_x(state, 'exploration_avail', -1)
	elif task_name[0] == 'c':
		await increment_player_x(state, 'combat_avail', -1)
	elif task_name[0] == 'p':
		await increment_player_x(state, 'puzzle_avail', -1)
	elif task_name[0] == 'd':
		await increment_player_x(state, 'dialogue_avail', -1)
	elif task_name[0] == 'b':
		await increment_player_x(state, 'debauchery_avail', -1)

	#clear the last_logged_task from the database
	async with state.bot.pool.acquire() as con:
		await con.execute(f"UPDATE data SET last_logged_task = '' WHERE name = '{state.player}'")
	
	await state.ctx.response.send_message(f"Removed task: {task_name}")

async def get_last_logged_task(state):
	#check if the player has a last logged task
	last_logged_task = await get_player_x(state, 'last_logged_task')
	if not last_logged_task:
		await state.ctx.response.send_message("Error: No task to undo. If you are trying to undo more than one task, use `\\task undo <task_name>` for each task.", ephemeral=True)
		return

	return last_logged_task 

#----------------------------------
# Leveling
#----------------------------------
async def award_xp(state, xp_amount, double_allowed=True):
	wisdom_level = await get_player_x(state, 'wisdom_level')
	if double_allowed and wisdom_level >= 35: # Wisdom 35: Mastery: Doubles all XP gains
		xp_amount *= 2
	current_xp = await increment_player_x(state, 'xp', xp_amount)

	#level up if you hit an xp threshold
	for threshold in xp_level_thresholds: #catches multiple level ups from one xp drop
		if current_xp - xp_amount < threshold <= current_xp:
			await level_up(state)

	#print an xp award message
	await ctx_print(state, f"Awarded {xp_amount} XP. Current XP: {current_xp}.\nXP needed for next level: {xp_level_thresholds[await get_player_x(state, 'level')] - current_xp}.")

async def level_up(state):
	await increment_player_x(state, 'level', 1)
	await increment_player_x(state, 'skill_points', await get_player_x(state, 'level'))
	# Wisdom 10: Gain an additional 50 XP when you level up
	wisdom_level = await get_player_x(state, 'wisdom_level')
	if wisdom_level >= 10:
		await award_xp(state, 50)
		await ctx_print(state, "Skill bonus! Gifted: You gained 50 bonus XP for leveling up.")
	await ctx_print(state, f"You have leveled up! You are now level {await get_player_x(state, 'level')}.\nYou have gained {await get_player_x(state, 'level')} skill points to spend on skills.")

#----------------------------------
# Skills
#----------------------------------
async def allocate_skill_points(state, skill_name, number): #TODO: on level up, when they get a new skill, say that they learned a new skill and display that skill's text

	#check if the level is valid
	if number < 1:
		await state.ctx.response.send_message("Error: Level must be a positive integer.", ephemeral=True)
		return

	#check that the player has enough skill points
	current_skill_points = await get_player_x(state, 'skill_points')
	if (current_skill_points == 0) or (current_skill_points < number):
		await state.ctx.response.send_message("Error: Not enough skill points in pool.", ephemeral=True)
		return

	#check that the input is valid
	if skill_name not in ('strength', 's', 'agility', 'a', 'wisdom', 'w'):
		await state.ctx.response.send_message("Error: Acceptable inputs are 'strength' (or 's'), 'agility' (or 'a'), 'wisdom' (or 'w').", ephemeral=True)
		return

	#clean input
	if skill_name in ('strength', 's'):
		skill_name = 'strength'
	elif skill_name in ('agility', 'a'):
		skill_name = 'agility'
	elif skill_name in ('wisdom', 'w'):
		skill_name = 'wisdom'

	#make sure that the player is not trying to increment their skill level above 35
	old_skill_level = await get_player_x(state, f"{skill_name}_level")
	if old_skill_level == 35:
		state.ctx.response.send_message(f"{skill_name} is already at max level!")
		return

	elif old_skill_level + number > 35:
		number = 35 - old_skill_level
		state.ctx.response.send_message(f"Skill levels can only be increased up to 35. Only {number} skill points have been spent.")

	#increment the skill level with a little message
	output_dict = {
		'strength': 'stronger',
		'agility': 'faster',
		'wisdom': 'smarter'
	}
	new_skill_level = await increment_player_x(state, f"{skill_name}_level", number)
	await state.ctx.response.send_message(f"You have reached {skill_name} level {new_skill_level}! Your party grows {output_dict[skill_name]}.")

	#if the skill level crossed one or more thresholds, display the descriptions for the new skills
	for threshold in skill_level_thresholds:
		if old_skill_level < threshold <= new_skill_level:
			skill_description = get_skill_description(skill_name, threshold)
			await ctx_print(state, f"New skill unlocked:\n{skill_description}")
			# Wisdom 28: Epiphany: Immediately gain 500 XP. This XP cannot be boosted by other skills or items.
			if skill_name == 'wisdom' and threshold == 28:
				await increment_player_x(state, 'xp', 500)
				await ctx_print(state, "Skill bonus! Epiphany: You immediately gain 500 XP (not boosted by other effects).")

	#decrement the skill points
	await increment_player_x(state, 'skill_points', -number)

#----------------------------------
# Questing
#----------------------------------

async def start_quest(state, difficulty):
	#if difficulty is 'drunken-dragon', check that the player is level 10
	if difficulty == 'drunken-dragon':
		current_level = await get_player_x(state, 'level')
		if current_level < 10:
			await state.ctx.response.send_message("Error: You must be at least level 10 to start the Drunken Dragon quest.", ephemeral=True)
			return

	#initialize the quest object (starts the quest and writes it to the database)
	await Quest.create(state, difficulty)

async def progress_quest(state):
	#check if the player has a quest
	current_quest = await get_player_x(state, 'current_quest')
	if not current_quest:
		await state.ctx.followup.send("Error: You do not have an active quest.")
		return

	#read the quest from the database
	quest = await Quest.from_state(state)

	#check that the player has enough banked tasks to progress the quest
	#and deduct the tasks from the player's available tasks
	task_type = quest.current_step_type
	n_tasks_needed = quest.current_step_num_tasks
	n_deb_tasks_needed = quest.current_step_num_deb_tasks
	
	#check debauchery tasks first
	if await get_player_x(state, 'debauchery_avail') < n_deb_tasks_needed:
		await state.ctx.followup.send("Error: Not enough debauchery tasks available to progress quest.")
		return
	
	if task_type == 'drunken-dragon':
		if (await get_player_x(state, 'exploration_avail') < n_tasks_needed) or (await get_player_x(state, 'combat_avail') < n_tasks_needed) or (await get_player_x(state, 'puzzle_avail') < n_tasks_needed) or (await get_player_x(state, 'dialogue_avail') < n_tasks_needed):
			await state.ctx.followup.send(f"Error: Not enough tasks available to progress quest. Need {n_tasks_needed} of each type, have {await get_player_x(state, 'exploration_avail')}, {await get_player_x(state, 'combat_avail')}, {await get_player_x(state, 'puzzle_avail')}, {await get_player_x(state, 'dialogue_avail')}.")
			return
		else:
			await increment_player_x(state, 'exploration_avail', -n_tasks_needed)
			await increment_player_x(state, 'combat_avail', -n_tasks_needed)
			await increment_player_x(state, 'puzzle_avail', -n_tasks_needed)
			await increment_player_x(state, 'dialogue_avail', -n_tasks_needed)

	else: #cover the regular task types
		if await get_player_x(state, f'{task_type}_avail') < n_tasks_needed:
			await state.ctx.followup.send(f"Error: Not enough {task_type} tasks available to progress quest. Need {n_tasks_needed}, have {await get_player_x(state, f'{task_type}_avail')}.")
			return
		else:
			await increment_player_x(state, f'{task_type}_avail', -n_tasks_needed)

	#have to run this at the end so that it doesn't deduct the debauchery tasks if the player doesn't have enough non-debauchery tasks
	await increment_player_x(state, 'debauchery_avail', -n_deb_tasks_needed) 

	#progress the quest
	complete_result = await quest.progress_quest(state) #returns None if the quest is not completed, or the difficulty of the quest if it is completed

	# Strength 5: Each completed quest step has a 30% chance to award 10 XP
	strength_level = await get_player_x(state, 'strength_level')
	wisdom_level = await get_player_x(state, 'wisdom_level')
	if strength_level >= 5 and random.random() < 0.3:
		await award_xp(state, 10)
		await ctx_print(state, "Skill bonus! Booze Boost: You gained 10 bonus XP for completing a quest step.")
	# Wisdom 20: Gain 10 bonus XP whenever you complete a quest step
	if wisdom_level >= 20:
		await award_xp(state, 10)
		await ctx_print(state, "Skill bonus! Oracle: You gained 10 bonus XP for completing a quest step.")
	# Wisdom 15: 20% chance to also complete the next quest step
	if complete_result is None and wisdom_level >= 15 and random.random() < 0.20:
		# Only attempt to progress if quest is not already completed
		current_quest = await get_player_x(state, 'current_quest')
		if current_quest:
			quest = await Quest.from_state(state)
			complete_result = await quest.progress_quest(state)
			await ctx_print(state, "Skill bonus! Chronomancy: You also completed the next quest step.")

	#if the quest was completed, add XP and rewards
	quest_xp = {
		'easy': 100,
		'medium': 200,
		'hard': 400
	}
	if complete_result:
		# Strength 35: Double the number of items you get from quest rewards
		strength_level = await get_player_x(state, 'strength_level')
		item_multiplier = 2 if strength_level >= 35 else 1
		# Strength 15: Complete 2 debauchery tasks on quest completion
		if strength_level >= 15:
			await increment_player_x(state, 'debauchery_avail', 2)
			await ctx_print(state, "Skill bonus! Take the Edge Off: You completed 2 debauchery tasks.")
			
		if complete_result in ('easy', 'medium', 'hard'):
			await increment_player_x(state, f'{complete_result}_quest', 1)
			await increment_player_x(state, f'{complete_result}_quest_points', item_multiplier)
			await award_xp(state, quest_xp[complete_result], double_allowed=False)
			if item_multiplier == 2:
				await ctx_print(state, "Skill bonus! Strength Mastery: You received double quest item points.")
		return complete_result
	return

async def abandon_quest(state):
	#check if the player has a quest
	current_quest = await get_player_x(state, 'current_quest')
	if not current_quest:
		await state.ctx.response.send_message("Error: You do not have an active quest.")
		return

	#abandon the quest
	quest = await Quest.from_state(state)
	await quest.abandon_quest(state)

async def complete_sidequest(state, task_type):
    # Agility 10: Sidequests require only 2 non-Debauchery Tasks
    agility_level = await get_player_x(state, 'agility_level')
    required_tasks = 2 if agility_level >= 10 else 3
    #check if the player has enough banked tasks to complete the sidequest
    if await get_player_x(state, 'debauchery_avail') < 1:
        await state.ctx.followup.send("Error: Not enough debauchery tasks available to complete sidequest.")
        return
    if await get_player_x(state, f"{task_type}_avail") < required_tasks:
        await state.ctx.followup.send(f"Error: Not enough {task_type} tasks available to complete sidequest.")
        return
    
    #generate the quest message
    sidequest_message = await conversation.ai_get_response(
        sidequest_ai_prompt(task_type)
    )
    
    #send the quest message to the player
    await state.ctx.followup.send(sidequest_message)

    #do the actual machinery of completing the sidequest
    await increment_player_x(state, 'sidequest', 1)
    await increment_player_x(state, f"{task_type}_avail", -required_tasks)
    await increment_player_x(state, 'debauchery_avail', -1)

    # Sidequest XP bonus logic
    agility_level = await get_player_x(state, 'agility_level')
    wisdom_level = await get_player_x(state, 'wisdom_level')
    sq_xp_bonus = await get_player_x(state, 'sq_xp_bonus')
    if agility_level >= 5:
        sq_xp_bonus += 20
        await set_player_x(state, 'sq_xp_bonus', sq_xp_bonus)
        await ctx_print(state, f"Skill bonus! Farsighted: Your sidequest XP bonus is now {sq_xp_bonus}.")
    else:
        sq_xp_bonus += 10
        await set_player_x(state, 'sq_xp_bonus', sq_xp_bonus)

	# Award the main XP for completing the sidequest
    await award_xp(state, sq_xp_bonus, double_allowed=False)

	# Wisdom 5: Scrying Eye: Receive 5 bonus XP whenever you complete a sidequest
    if wisdom_level >= 5:
        await award_xp(state, 5)
        await ctx_print(state, f"Skill bonus! Scrying Eye: You gained bonus XP for this sidequest.")

    # --- Skill Effects: Agility 1, 20, 28 ---
    agility_level = await get_player_x(state, 'agility_level')
    # Agility 1: 10% chance for Easy Quest Item Point
    if agility_level >= 1 and random.random() < 0.10:
        await increment_player_x(state, 'easy_quest_points', 1)
        await ctx_print(state, "Skill bonus! You gained an Easy Quest Item Point.")
    # Agility 20: 20% chance to also complete the current quest step
    if agility_level >= 20 and random.random() < 0.20:
        # Progress the current quest if one exists
        current_quest = await get_player_x(state, 'current_quest')
        if current_quest:
            quest = await Quest.from_state(state)
            await quest.progress_quest(state)
            await ctx_print(state, "Skill bonus! You also progressed your current quest step.")
    # Agility 28: 20% chance for random item point
    if agility_level >= 28 and random.random() < 0.20:
        rarity = random.choice(['easy_quest_points', 'medium_quest_points', 'hard_quest_points'])
        await increment_player_x(state, rarity, 1)
        await ctx_print(state, f"Skill bonus! You gained a {rarity.replace('_', ' ').title()}.")

    await state.ctx.followup.send(f"You have completed a {task_type} sidequest! You have completed a total of {await get_player_x(state, 'sidequest')} sidequests.")

#----------------------------------
# Items
#----------------------------------
async def buy_item(state, item_id):
	item_id = item_id.lower()  #ensure the first letter is lowercase

	#check that the item id has the correct format
	if item_id[0] not in ('e', 'm', 'h'):
		await state.ctx.response.send_message("Error: Invalid item ID format. Must start with 'e', 'm', or 'h'.")
		return

	#check if the player has enough item points for that tier of item
	if item_id[0] == 'e':
		if await get_player_x(state, 'easy_quest_points') < 1:
			await state.ctx.response.send_message("Error: Not enough easy quest points to buy this item.")
			return
	elif item_id[0] == 'm':
		if await get_player_x(state, 'medium_quest_points') < 1:
			await state.ctx.response.send_message("Error: Not enough medium quest points to buy this item.")
			return
	elif item_id[0] == 'h':
		if await get_player_x(state, 'hard_quest_points') < 1:
			await state.ctx.response.send_message("Error: Not enough hard quest points to buy this item.")
			return

	#check if the player already has that item 
	if await inventory_contains(state, item_id):
		await state.ctx.response.send_message("Error: You already have this item.")
		return

	#add the item to the player's inventory
	inventory_text = await get_player_x(state, 'inventory')
	if inventory_text:
		inventory_text += f",{item_id}"
	else:
		inventory_text = item_id
	await set_player_x(state, 'inventory', inventory_text)

	#decrement the player's quest points
	if item_id[0] == 'e':
		await increment_player_x(state, 'easy_quest_points', -1)
	elif item_id[0] == 'm':
		await increment_player_x(state, 'medium_quest_points', -1)
	elif item_id[0] == 'h':
		await increment_player_x(state, 'hard_quest_points', -1)
	await state.ctx.response.send_message(f"You have purchased {get_item_name(item_id)}.")

