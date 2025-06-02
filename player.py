#the main machinery of the game, back-end for actions a player can take

from quest import Quest
import conversation
from text_storage import xp_level_thresholds, skill_level_thresholds, get_item_name, sidequest_ai_prompt

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
				last_logged_task      VARCHAR DEFAULT ''
				)''')

		# #set default values #no longer needed, now done in the table creation
		await con.execute(f"INSERT INTO data(name) VALUES('{state.player}') ON CONFLICT DO NOTHING")
		# await con.execute(f'INSERT INTO data(level) VALUES(1) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(xp) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(easy_quest) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(medium_quest) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(hard_quest) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(easy_quest_points) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(medium_quest_points) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(hard_quest_points) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(sidequest) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(strength_level) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(agility_level) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(wisdom_level) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(skill_points) VALUES(1) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(exploration_avail) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(combat_avail) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(puzzle_avail) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(dialogue_avail) VALUES(0) ON CONFLICT DO NOTHING')
		# await con.execute(f'INSERT INTO data(debauchery_avail) VALUES(0) ON CONFLICT DO NOTHING')

		print(f"Initialized channel: {state.player}")

#----------------------------------
# Helpers
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
# Tasks
#----------------------------------

async def log_task(state, task_name):
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

	#log the task in the database
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
		await state.ctx.response.send_message("Error: No task to undo. If you are trying to undo more than one task, use `\\task undo <task_name>` for each task.")
		return

	return last_logged_task 

#----------------------------------
# Leveling
#----------------------------------
async def award_xp(state, xp_amount):
		current_xp = await get_player_x(state, 'xp')
		current_xp += xp_amount

		#level up if you hit an xp threshold
		for threshold in xp_level_thresholds: #this may look silly but it automatically catches multiple level ups from one xp drop
			if current_xp - xp_amount < threshold < current_xp:
				await level_up(state)

async def level_up(state):
	await increment_player_x(state, 'level', 1)
	await increment_player_x(state, 'skill_points', await get_player_x(state, 'level') + 1)

#----------------------------------
# Skills
#----------------------------------
async def allocate_skill_points(state, skill_name, number): #TODO: on level up, when they get a new skill, say that they learned a new skill and display that skill's text

	#check that the player has enough skill points
	current_skill_points = await get_player_x(state, 'skill_points')
	if (current_skill_points == 0) or (current_skill_points < number):
		await state.ctx.response.send_message("Error: Not enough skill points in pool.")
		return

	#check that the input is valid
	if skill_name not in ('strength', 's', 'agility', 'a', 'wisdom', 'w'):
		await state.ctx.response.send_message("Error: Acceptable inputs are 'strength' (or 's'), 'agility' (or 'a'), 'wisdom' (or 'w').")
		return

	#clean input
	if skill_name in ('strength', 's'):
		skill_name = 'strength'
	elif skill_name in ('agility', 'a'):
		skill_name = 'agility'
	elif skill_name in ('wisdom', 'w'):
		skill_name = 'wisdom'

	#increment the skill level with a little message
	output_dict = {
		'strength': 'stronger',
		'agility': 'faster',
		'wisdom': 'smarter'
	}
	old_skill_level = await get_player_x(state, f"{skill_name}_level")
	new_skill_level = await increment_player_x(state, f"{skill_name}_level", number)
	await state.ctx.response.send_message(f"Your party grows {output_dict[skill_name]}.")

	#if the skill level crossed one or more thresholds, display the descriptions for the new skills
	for threshold in skill_level_thresholds:
		if old_skill_level < threshold <= new_skill_level:
			skill_description = skill_level_thresholds[threshold]
			await state.ctx.response.send_message(f"You have reached {skill_name} level {threshold}! New skill unlocked:\n{skill_description}")

	#decrement the skill points
	await set_player_x(state, 'skill_points', current_skill_points - number)

#----------------------------------
# Questing
#----------------------------------

async def start_quest(state, difficulty):
	#if difficulty is 'drunken-dragon', check that the player is level 10
	if difficulty == 'drunken-dragon':
		current_level = await get_player_x(state, 'level')
		if current_level < 10:
			await state.ctx.response.send_message("Error: You must be at least level 10 to start the Drunken Dragon quest.")
			return

	#initialize the quest object and write it to the database
	quest = Quest(difficulty)
	await quest.start_quest(state)

async def progress_quest(state):
	#check if the player has a quest
	current_quest = await get_player_x(state, 'current_quest')
	if not current_quest:
		await state.ctx.response.send_message("Error: You do not have an active quest.")
		return

	#read the quest from the database
	quest = await Quest.from_state(state)

	#check that the player has enough banked tasks to progress the quest
	#and deduct the tasks from the player's available tasks
	task_type = quest.current_step_type
	n_tasks_needed = quest.current_step_num_tasks
	n_deb_tasks_needed = quest.current_step_num_deb_tasks
	
	if await get_player_x(state, 'debauchery_avail') < n_deb_tasks_needed:
		await state.ctx.response.send_message("Error: Not enough debauchery tasks available to progress quest.")
		return

	if task_type == 'exploration':
		if await get_player_x(state, 'exploration_avail') < n_tasks_needed:
			await state.ctx.response.send_message(f"Error: Not enough exploration tasks available to progress quest. Need {n_tasks_needed}, have {await get_player_x(state, 'exploration_avail')}.")
			return
		else:
			await increment_player_x(state, 'exploration_avail', -n_tasks_needed)
	elif task_type == 'combat':
		if await get_player_x(state, 'combat_avail') < n_tasks_needed:
			await state.ctx.response.send_message(f"Error: Not enough combat tasks available to progress quest. Need {n_tasks_needed}, have {await get_player_x(state, 'combat_avail')}.")
			return
		else:
			await increment_player_x(state, 'combat_avail', -n_tasks_needed)
	elif task_type == 'puzzle':
		if await get_player_x(state, 'puzzle_avail') < n_tasks_needed:
			await state.ctx.response.send_message(f"Error: Not enough puzzle tasks available to progress quest. Need {n_tasks_needed}, have {await get_player_x(state, 'puzzle_avail')}.")
			return
		else:
			await increment_player_x(state, 'puzzle_avail', -n_tasks_needed)
	elif task_type == 'dialogue':
		if await get_player_x(state, 'dialogue_avail') < n_tasks_needed:
			await state.ctx.response.send_message(f"Error: Not enough dialogue tasks available to progress quest. Need {n_tasks_needed}, have {await get_player_x(state, 'dialogue_avail')}.")
			return
		else:
			await increment_player_x(state, 'dialogue_avail', -n_tasks_needed)
	elif task_type == 'drunken-dragon':
		if (await get_player_x(state, 'exploration_avail') < n_tasks_needed) or (await get_player_x(state, 'combat_avail') < n_tasks_needed) or (await get_player_x(state, 'puzzle_avail') < n_tasks_needed) or (await get_player_x(state, 'dialogue_avail') < n_tasks_needed):
			await state.ctx.response.send_message(f"Error: Not enough tasks available to progress quest. Need {n_tasks_needed} of each type, have {await get_player_x(state, 'exploration_avail')}, {await get_player_x(state, 'combat_avail')}, {await get_player_x(state, 'puzzle_avail')}, {await get_player_x(state, 'dialogue_avail')}.")
			return
	await increment_player_x(state, 'debauchery_avail', -n_deb_tasks_needed) #have to run this at the end so that it doesn't deduct the debauchery tasks if the player doesn't have enough non-debauchery tasks

	#progress the quest
	progress_result = await quest.progress_quest(state)

	#if the quest was completed, add XP and rewards
	if progress_result:
		if progress_result == 'easy':
			await increment_player_x(state, 'easy_quest', 1)
			await increment_player_x(state, 'easy_quest_points', 1)
			await award_xp(state, 100)
		elif progress_result == 'medium':
			await increment_player_x(state, 'medium_quest', 1)
			await increment_player_x(state, 'medium_quest_points', 1)
			await award_xp(state, 200)
		elif progress_result == 'hard':
			await increment_player_x(state, 'hard_quest', 1)
			await increment_player_x(state, 'hard_quest_points', 1)
			await award_xp(state, 400)
		return progress_result
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

async def complete_sidequest(state, type):
	#check if the player has enough banked tasks to complete the sidequest
	if await get_player_x(state, 'debauchery_avail') < 1:
		await state.ctx.response.send_message("Error: Not enough debauchery tasks available to complete sidequest.")
		return
	if await get_player_x(state, f"{type}_avail") < 3:
		await state.ctx.response.send_message(f"Error: Not enough {type} tasks available to complete sidequest.")
		return
	
	#generate the quest message
	sidequest_message = await conversation.ai_get_response(
		sidequest_ai_prompt(type)
	)
	
	#send the quest message to the player
	await state.ctx.response.send_message(sidequest_message)

	#do the actual machinery of completing the sidequest
	await increment_player_x(state, 'sidequest', 1)
	await increment_player_x(state, f"{type}_avail", -3)
	await increment_player_x(state, 'debauchery_avail', -1)
	await award_xp(state, 10*(await get_player_x(state, 'sidequest')))  #10 xp per sidequest, scaling with number of sidequests completed

#----------------------------------
# Items
#----------------------------------
async def buy_item(state, item_id):
	try:
		item_id[0] = item_id[0].lower()  #ensure the first letter is lowercase
	except Exception as e:
		await state.ctx.response.send_message("Error: Invalid item ID format. Must start with 'e', 'm', or 'h'.")
		print(f"ERROR buy_item PLAYER: {state.player} THREW: {e}")
		return

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

