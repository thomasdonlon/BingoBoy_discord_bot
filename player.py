#the main machinery of the game, back-end for actions a player can take

from quest import Quest
import conversation
from text_storage import xp_level_thresholds, skill_level_thresholds, sidequest_ai_prompt, skill_level_descriptions
from utils import get_item_name, ctx_print, get_skill_description
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

async def get_player_skill_levels(state):
    return {
        'strength': await get_player_x(state, 'strength_level'),
        'agility': await get_player_x(state, 'agility_level'),
        'wisdom': await get_player_x(state, 'wisdom_level'),
    }

def get_active_skill_effects(skill_levels):
    effects = []
    for skill, level in skill_levels.items():
        for threshold, desc in skill_level_descriptions[skill].items():
            if level >= threshold:
                effects.append((skill, threshold, desc))
    return effects

#----------------------------------
# Tasks
#----------------------------------

async def log_task(state, task_name):
    skill_levels = await get_player_skill_levels(state)
    effects = get_active_skill_effects(skill_levels)
    # Strength 1: Debauchery task gives +2 XP
    if task_name[0] == 'b' and any(skill == 'strength' and threshold == 1 for skill, threshold, _ in effects):
        await award_xp(state, 2)
    # Agility 3: 25% chance to complete 2 Exploration Tasks
    if task_name[0] == 'e' and any(skill == 'agility' and threshold == 3 for skill, threshold, _ in effects):
        if random.random() < 0.25:
            await increment_player_x(state, 'exploration_avail', 2)
            return
    # Strength 3: 25% chance to complete 2 Combat Tasks
    if task_name[0] == 'c' and any(skill == 'strength' and threshold == 3 for skill, threshold, _ in effects):
        if random.random() < 0.25:
            await increment_player_x(state, 'combat_avail', 2)
            return
    # Wisdom 1: 25% chance to complete 2 Dialogue Tasks
    if task_name[0] == 'd' and any(skill == 'wisdom' and threshold == 1 for skill, threshold, _ in effects):
        if random.random() < 0.25:
            await increment_player_x(state, 'dialogue_avail', 2)
            return
    # Wisdom 3: 25% chance to complete 2 Puzzle-Solving Tasks
    if task_name[0] == 'p' and any(skill == 'wisdom' and threshold == 3 for skill, threshold, _ in effects):
        if random.random() < 0.25:
            await increment_player_x(state, 'puzzle_avail', 2)
            return
    # Default behavior
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
		await state.ctx.response.send_message("Error: No task to undo. If you are trying to undo more than one task, use `\\task undo <task_name>` for each task.", ephemeral=True)
		return

	return last_logged_task 

#----------------------------------
# Leveling
#----------------------------------
async def award_xp(state, xp_amount):
    skill_levels = await get_player_skill_levels(state)
    effects = get_active_skill_effects(skill_levels)
    # Wisdom 35: Double all sources of XP except completing quests and sidequests
    double_xp = any(skill == 'wisdom' and threshold == 35 for skill, threshold, _ in effects)
    if double_xp:
        xp_amount *= 2
    # Wisdom 10: Gain an additional 50 XP when you level up
    # (Handled in level_up)
    current_xp = await increment_player_x(state, 'xp', xp_amount)
    for threshold in xp_level_thresholds:
        if current_xp - xp_amount < threshold <= current_xp:
            await level_up(state)
    await ctx_print(state, f"Awarded {xp_amount} XP. Current XP: {current_xp}.\nXP needed for next level: {xp_level_thresholds[await get_player_x(state, 'level')] - current_xp}.")

async def level_up(state):
    skill_levels = await get_player_skill_levels(state)
    await increment_player_x(state, 'level', 1)
    await increment_player_x(state, 'skill_points', await get_player_x(state, 'level'))
    # Wisdom 10: Gain an additional 50 XP when you level up
    if skill_levels.get('wisdom', 0) >= 10:
        await increment_player_x(state, 'xp', 50)
        await ctx_print(state, "Wisdom 10: You gained an additional 50 XP for leveling up!")
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
	# Wisdom 28: Immediately gain 500 XP (cannot be boosted)
	if skill_name == 'wisdom' and old_skill_level < 28 <= new_skill_level:
		await increment_player_x(state, 'xp', 500)
		await ctx_print(state, "Wisdom 28: Epiphany! You immediately gain 500 XP.")
	#if the skill level crossed one or more thresholds, display the descriptions for the new skills
	for threshold in skill_level_thresholds:
		if old_skill_level < threshold <= new_skill_level:
			skill_description = get_skill_description(skill_name, threshold)
			await ctx_print(state, f"New skill unlocked:\n{skill_description}")

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

# --- Helper for quest step/task requirements (for skill effects that modify requirements) ---
def adjust_quest_step_requirements(state, quest, skill_levels, effects):
    # Strength 10: Quests never require max steps (except Drunken Dragon)
    if any(skill == 'strength' and threshold == 10 for skill, threshold, _ in effects):
        if quest.difficulty != 'drunken-dragon':
            if quest.current_step_num == quest.total_step_number - 1:
                quest.total_step_number -= 1
    # Drunken Dragon/sidequest step requirements (Agility 10, Dragon-Slaying Lance, etc.) can be handled here as needed
    # Strength 20: Debauchery tasks can cover missing non-debauchery tasks for quest steps
    # (Handled in progress_quest below)
    # Agility 10: Sidequests require only 2 non-debauchery tasks (handled in complete_sidequest)
    # Dragon-Slaying Lance: Drunken Dragon quest steps only require 2 of each type (handled in quest.py)
    # Scrying Orb: Quest steps always require smallest number of tasks (handled in quest.py)
    return quest

async def progress_quest(state):
    skill_levels = await get_player_skill_levels(state)
    effects = get_active_skill_effects(skill_levels)
    current_quest = await get_player_x(state, 'current_quest')
    if not current_quest:
        await state.ctx.followup.send("Error: You do not have an active quest.")
        return
    quest = await Quest.from_state(state)
    # Strength 10: Quests never require max steps (except Drunken Dragon)
    quest = adjust_quest_step_requirements(state, quest, skill_levels, effects)
    # Strength 28: Skip first two steps of Drunken Dragon quest
    if quest.difficulty == 'drunken-dragon' and skill_levels.get('strength', 0) >= 28 and quest.current_step_num == 0:
        quest.current_step_num = 2
        await quest.write_quest_to_db(state)
    # Strength 20: Debauchery tasks can cover missing non-debauchery tasks for quest steps
    use_debauchery_for_missing = any(skill == 'strength' and threshold == 20 for skill, threshold, _ in effects)
    task_type = quest.current_step_type
    n_tasks_needed = quest.current_step_num_tasks
    n_deb_tasks_needed = quest.current_step_num_deb_tasks
    # Use debauchery to cover missing non-debauchery tasks
    if use_debauchery_for_missing and task_type != 'drunken-dragon':
        available = await get_player_x(state, f'{task_type}_avail')
        if available < n_tasks_needed:
            missing = n_tasks_needed - available
            debauchery_avail = await get_player_x(state, 'debauchery_avail')
            if debauchery_avail >= missing + n_deb_tasks_needed:
                await increment_player_x(state, f'{task_type}_avail', -available)
                await increment_player_x(state, 'debauchery_avail', -(missing + n_deb_tasks_needed))
                n_tasks_needed = 0
                n_deb_tasks_needed = 0
            else:
                await state.ctx.followup.send("Error: Not enough debauchery tasks to cover missing tasks.")
                return
    #check if the player has enough banked tasks to progress the quest
    #and deduct the tasks from the player's available tasks
    if await get_player_x(state, 'debauchery_avail') < n_deb_tasks_needed:
        await state.ctx.followup.send("Error: Not enough debauchery tasks available to progress quest.")
        return
    if task_type == 'exploration':
        if await get_player_x(state, 'exploration_avail') < n_tasks_needed:
            await state.ctx.followup.send(f"Error: Not enough exploration tasks available to progress quest. Need {n_tasks_needed}, have {await get_player_x(state, 'exploration_avail') }.")
            return
        else:
            await increment_player_x(state, 'exploration_avail', -n_tasks_needed)
    elif task_type == 'combat':
        if await get_player_x(state, 'combat_avail') < n_tasks_needed:
            await state.ctx.followup.send(f"Error: Not enough combat tasks available to progress quest. Need {n_tasks_needed}, have {await get_player_x(state, 'combat_avail') }.")
            return
        else:
            await increment_player_x(state, 'combat_avail', -n_tasks_needed)
    elif task_type == 'puzzle':
        if await get_player_x(state, 'puzzle_avail') < n_tasks_needed:
            await state.ctx.followup.send(f"Error: Not enough puzzle tasks available to progress quest. Need {n_tasks_needed}, have {await get_player_x(state, 'puzzle_avail') }.")
            return
        else:
            await increment_player_x(state, 'puzzle_avail', -n_tasks_needed)
    elif task_type == 'dialogue':
        if await get_player_x(state, 'dialogue_avail') < n_tasks_needed:
            await state.ctx.followup.send(f"Error: Not enough dialogue tasks available to progress quest. Need {n_tasks_needed}, have {await get_player_x(state, 'dialogue_avail') }.")
            return
        else:
            await increment_player_x(state, 'dialogue_avail', -n_tasks_needed)
    elif task_type == 'drunken-dragon':
        if (await get_player_x(state, 'exploration_avail') < n_tasks_needed) or (await get_player_x(state, 'combat_avail') < n_tasks_needed) or (await get_player_x(state, 'puzzle_avail') < n_tasks_needed) or (await get_player_x(state, 'dialogue_avail') < n_tasks_needed):
            await state.ctx.followup.send(f"Error: Not enough tasks available to progress quest. Need {n_tasks_needed} of each type, have {await get_player_x(state, 'exploration_avail')}, {await get_player_x(state, 'combat_avail')}, {await get_player_x(state, 'puzzle_avail')}, {await get_player_x(state, 'dialogue_avail') }.")
            return
    await increment_player_x(state, 'debauchery_avail', -n_deb_tasks_needed) #have to run this at the end so that it doesn't deduct the debauchery tasks if the player doesn't have enough non-debauchery tasks
    #progress the quest
    # Wisdom 20: Gain 10 bonus XP whenever you complete a quest step
    wisdom20_bonus = 10 if skill_levels.get('wisdom', 0) >= 20 else 0
    # Strength 5: 30% chance for 10 bonus XP
    extra_xp = 0
    if any(skill == 'strength' and threshold == 5 for skill, threshold, _ in effects):
        if random.random() < 0.3:
            extra_xp = 10
    progress_result = await quest.progress_quest(state)
    # Wisdom 20: Add bonus XP for quest step
    if wisdom20_bonus:
        await award_xp(state, wisdom20_bonus)
        await state.ctx.followup.send(f"Wisdom 20: Oracle grants you {wisdom20_bonus} bonus XP for completing a quest step!")
    # Wisdom 15: 20% chance to also complete the next quest step
    if skill_levels.get('wisdom', 0) >= 15 and progress_result:
        if random.random() < 0.2:
            await state.ctx.followup.send("Wisdom 15: Chronomancy triggered! You also completed the next quest step.")
            await quest.progress_quest(state)
    # Strength 15: When you complete a quest, automatically complete 2 debauchery tasks
    if progress_result and skill_levels.get('strength', 0) >= 15:
        await increment_player_x(state, 'debauchery_avail', 2)
        await state.ctx.followup.send("Strength 15: You automatically completed 2 debauchery tasks!")
    # Strength 35: Double the number of items you get from quest rewards
    if progress_result and skill_levels.get('strength', 0) >= 35:
        if progress_result == 'easy':
            await increment_player_x(state, 'easy_quest_points', 1)
        elif progress_result == 'medium':
            await increment_player_x(state, 'medium_quest_points', 1)
        elif progress_result == 'hard':
            await increment_player_x(state, 'hard_quest_points', 1)
        await state.ctx.followup.send("Strength 35: You received double item rewards!")
    return progress_result

async def complete_sidequest(state, task_type):
    skill_levels = await get_player_skill_levels(state)
    effects = get_active_skill_effects(skill_levels)
    # Agility 10: Sidequests require only 2 non-debauchery tasks
    n_tasks_needed = 2 if any(skill == 'agility' and threshold == 10 for skill, threshold, _ in effects) else 3
    if await get_player_x(state, 'debauchery_avail') < 1:
        await state.ctx.followup.send("Error: Not enough debauchery tasks available to complete sidequest.")
        return
    if await get_player_x(state, f"{task_type}_avail") < n_tasks_needed:
        await state.ctx.followup.send(f"Error: Not enough {task_type} tasks available to complete sidequest.")
        return
    # Agility 5: Sidequest XP increases by +20 XP instead of +10 XP
    xp_per_sidequest = 20 if any(skill == 'agility' and threshold == 5 for skill, threshold, _ in effects) else 10
    # Wisdom 5: 5 bonus XP whenever you complete a sidequest
    wisdom5_bonus = 5 if skill_levels.get('wisdom', 0) >= 5 else 0
    # Agility 1: 10% chance to gain an Easy Quest Item Point
    if skill_levels.get('agility', 0) >= 1 and random.random() < 0.1:
        await increment_player_x(state, 'easy_quest_points', 1)
        await state.ctx.followup.send("Agility 1: Nature Spirit grants you an Easy Quest Item Point!")
    # Agility 20: 20% chance to also complete the current quest step
    if skill_levels.get('agility', 0) >= 20 and random.random() < 0.2:
        await state.ctx.followup.send("Agility 20: Multitasker triggered! You also progressed your current quest step.")
        await progress_quest(state)
    #generate the sidequest text
    sidequest_message = await conversation.ai_get_response(
        sidequest_ai_prompt(task_type)
    )
    await state.ctx.followup.send(sidequest_message)
    await increment_player_x(state, 'sidequest', 1)
    await increment_player_x(state, f"{task_type}_avail", -n_tasks_needed)
    await increment_player_x(state, 'debauchery_avail', -1)
    await award_xp(state, xp_per_sidequest * (await get_player_x(state, 'sidequest')) + wisdom5_bonus)
    await state.ctx.followup.send(f"You have completed a {task_type} sidequest! You have completed a total of {await get_player_x(state, 'sidequest')} sidequests.")

