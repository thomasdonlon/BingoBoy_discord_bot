#the main machinery of the game, back-end for actions a player can take

from quest import Quest
import conversation
from text_storage import xp_level_thresholds, skill_level_thresholds, sidequest_ai_prompt
from utils import get_item_name, ctx_print, get_skill_description, get_player_x, set_player_x, increment_player_x, inventory_contains, random_with_bonus
import random

#initialize the channel/player
async def init(state):
    async with state.bot.pool.acquire() as con:   
        await con.execute(f'''CREATE TABLE IF NOT EXISTS data (
                        
                name                  VARCHAR PRIMARY KEY NOT NULL,
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

async def increment_task(state, task_name, n=1, log_task=True):
    # Increment the task count for the specified task
    
    #things that proc for non-debauchery tasks
    if task_name[0] != 'b':
        # e7: Lucky Coin - 10% chance to provide 10 XP when you complete a non-Debauchery Task
        if await inventory_contains(state, 'e7') and random_with_bonus(state) < 0.10:
            await award_xp(state, 10)
            await ctx_print(state, "Item bonus! Lucky Coin: You gained 10 XP!")
        # e5: Strength Potion - 10% chance to complete a Combat Task whenever you complete a non-Debauchery Task
        if await inventory_contains(state, 'e5') and random_with_bonus(state) < 0.10:
            await increment_task(state, 'c', 1, log_task=False)
            await ctx_print(state, "Item bonus! Strength Potion: You completed a bonus Combat Task!")

    if task_name[0] == 'e':
        await increment_player_x(state, 'exploration_avail', n)
        # m1: Pathfinder Potion - Completing an Exploration task now awards 10 XP
        if await inventory_contains(state, 'm1'):
            await award_xp(state, 10)
            await ctx_print(state, "Item bonus! Pathfinder Potion: You gained 10 XP for an Exploration task!")
    elif task_name[0] == 'c':
        await increment_player_x(state, 'combat_avail', n)
        # m2: Mithril Sword - Completing a Combat task now awards 10 XP
        if await inventory_contains(state, 'm2'):
            await award_xp(state, 10)
            await ctx_print(state, "Item bonus! Mithril Sword: You gained 10 XP for a Combat task!")
    elif task_name[0] == 'p':
        await increment_player_x(state, 'puzzle_avail', n)
        # m3: Arcane Eye - Completing a Puzzle-Solving task now awards 10 XP
        if await inventory_contains(state, 'm3'):
            await award_xp(state, 10)
            await ctx_print(state, "Item bonus! Arcane Eye: You gained 10 XP for a Puzzle-Solving task!")
    elif task_name[0] == 'd':
        await increment_player_x(state, 'dialogue_avail', n)
        # m4: Golden Lip Balm - Completing a Dialogue task now awards 10 XP
        if await inventory_contains(state, 'm4'):
            await award_xp(state, 10)
            await ctx_print(state, "Item bonus! Golden Lip Balm: You gained 10 XP for a Dialogue task!")
    elif task_name[0] == 'b':
        await increment_player_x(state, 'debauchery_avail', n)
        # Strength 1: Completing a Debauchery Task also provides +2 XP
        strength_level = await get_player_x(state, 'strength_level')
        if strength_level >= 1:
            await award_xp(state, 2)

    if log_task:
        # Log the task in the database
        async with state.bot.pool.acquire() as con:
            await con.execute(f"UPDATE data SET last_logged_task = '{task_name}' WHERE name = '{state.player}'")

async def log_task(state, task_name, rune_of_rep=False):
    # Check for skill-based extra task completion
    extra_task = False
    extra_task_type = None
    
    # Get player skill levels
    strength_level = await get_player_x(state, 'strength_level')
    agility_level = await get_player_x(state, 'agility_level')
    wisdom_level = await get_player_x(state, 'wisdom_level')

    # Runestone of Repetition (d3): 30% chance to complete each Task twice
    if not rune_of_rep and await inventory_contains(state, 'd3') and random_with_bonus(state) < 0.3: #avoid runestone activating off of a runestone proc
        # Log the task twice
        await ctx_print(state, "Item bonus! Runestone of Repetition: You completed this task twice!")
        await log_task(state, task_name)
        return

    # Strength 3: 25% chance for extra combat task
    if task_name[0] == 'c' and strength_level >= 3:
        if random_with_bonus(state) < 0.25:
            extra_task = True
            extra_task_type = 'combat_avail'
    # Agility 3: 25% chance for extra exploration task
    elif task_name[0] == 'e' and agility_level >= 3:
        if random_with_bonus(state) < 0.25:
            extra_task = True
            extra_task_type = 'exploration_avail'
    # Wisdom 1: 25% chance for extra dialogue task
    elif task_name[0] == 'd' and wisdom_level >= 1:
        if random_with_bonus(state) < 0.25:
            extra_task = True
            extra_task_type = 'dialogue_avail'
    # Wisdom 3: 25% chance for extra puzzle task
    elif task_name[0] == 'p' and wisdom_level >= 3:
        if random_with_bonus(state) < 0.25:
            extra_task = True
            extra_task_type = 'puzzle_avail'

    # Normal task logging
    await increment_task(state, task_name)

    # Apply extra task if triggered
    if extra_task and extra_task_type:
        await increment_task(state, extra_task_type[0], log_task=False)
        await ctx_print(state, f"Skill bonus! You completed an extra {extra_task_type.split('_')[0]} task.")

async def remove_task(state, task_name):
    #remove the task from the player's available tasks
    await increment_player_x(state, task_name, -1, log_task=False)

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
    # d8: Bejeweled Scepter - All XP drops are increased by 1 x the number of items you have
    if await inventory_contains(state, 'd8'):
        inventory_text = await get_player_x(state, 'inventory')
        num_items = len([item for item in inventory_text.split(',') if item])
        if num_items > 0:
            xp_amount += num_items
            await ctx_print(state, f"Item bonus! Bejeweled Scepter: XP increased by {num_items} (total {xp_amount}).")

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
    skill_points_to_add = await get_player_x(state, 'level')
    # m9: Robe of Stars - Gain 1 additional skill point when you level up
    if await inventory_contains(state, 'm9'):
        skill_points_to_add += 1
        await ctx_print(state, "Item bonus! Robe of Stars: You gained 1 extra skill point for leveling up!")
    await increment_player_x(state, 'skill_points', skill_points_to_add)
    # Wisdom 10: Gain an additional 50 XP when you level up
    wisdom_level = await get_player_x(state, 'wisdom_level')
    if wisdom_level >= 10:
        await award_xp(state, 50)
        await ctx_print(state, "Skill bonus! Gifted: You gained 50 bonus XP for leveling up.")
    await ctx_print(state, f"You have leveled up! You are now level {await get_player_x(state, 'level')}.\nYou have gained {skill_points_to_add} skill points to spend on skills.")

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

    # Scroll of Misty Step (m8): Start each quest on the 2nd step
    if difficulty != 'drunken-dragon' and await inventory_contains(state, 'm8'):
        await ctx_print(state, "Item bonus! Scroll of Misty Step: You start this quest on the 2nd step.")
        quest = await Quest.from_state(state)
        quest.current_step_num = 2

async def progress_quest(state, skip_task_check=False):
    # check if the player has a quest
    current_quest = await get_player_x(state, 'current_quest')
    if not current_quest:
        await state.ctx.followup.send("Error: You do not have an active quest.")
        return

    # read the quest from the database
    quest = await Quest.from_state(state)

    if not skip_task_check:
        # check that the player has enough banked tasks to progress the quest
        # and deduct the tasks from the player's available tasks
        task_type = quest.current_step_type
        n_tasks_needed = quest.current_step_num_tasks
        n_deb_tasks_needed = quest.current_step_num_deb_tasks

        # check debauchery tasks first
        if await get_player_x(state, 'debauchery_avail') < n_deb_tasks_needed:
            await state.ctx.followup.send("Error: Not enough debauchery tasks available to progress quest.")
            return

        strength_level = await get_player_x(state, 'strength_level')
        # Monk of the Drunken Fist: Use debauchery tasks to cover missing non-debauchery tasks
        if strength_level >= 20:
            if task_type == 'drunken-dragon':
                # For each type, use debauchery to cover missing
                types = ['exploration', 'combat', 'puzzle', 'dialogue']
                avail = {t: await get_player_x(state, f'{t}_avail') for t in types}
                missing = {t: n_tasks_needed - avail[t] for t in types}
                total_missing = sum(max(0, m) for m in missing.values())
                debauchery_needed = n_deb_tasks_needed + total_missing
                if await get_player_x(state, 'debauchery_avail') < debauchery_needed:
                    await state.ctx.followup.send(f"Error: Not enough debauchery tasks available to cover missing tasks for Drunken Dragon quest (need {debauchery_needed}).")
                    return
                # Deduct all available non-debauchery tasks, and cover the rest with debauchery
                for t in types:
                    to_deduct = min(avail[t], n_tasks_needed)
                    await increment_player_x(state, f'{t}_avail', -to_deduct)
                if total_missing > 0:
                    await ctx_print(state, f"Skill bonus! Monk of the Drunken Fist: Used {total_missing} debauchery tasks to cover missing tasks for Drunken Dragon quest.")
                await increment_player_x(state, 'debauchery_avail', -debauchery_needed)
            else:
                available = await get_player_x(state, f'{task_type}_avail')
                missing = n_tasks_needed - available
                debauchery_needed = n_deb_tasks_needed
                if missing > 0:
                    if await get_player_x(state, 'debauchery_avail') < (n_deb_tasks_needed + missing):
                        await state.ctx.followup.send(f"Error: Not enough debauchery tasks available to cover missing {task_type} tasks (need {n_deb_tasks_needed + missing}).")
                        return
                    # Deduct all available non-debauchery tasks, and cover the rest with debauchery
                    await increment_player_x(state, f'{task_type}_avail', -available)
                    debauchery_needed += missing
                    await ctx_print(state, f"Skill bonus! Monk of the Drunken Fist: Used {missing} debauchery tasks to cover missing {task_type} tasks.")
                else:
                    await increment_player_x(state, f'{task_type}_avail', -n_tasks_needed)
                await increment_player_x(state, 'debauchery_avail', -debauchery_needed)
        elif task_type == 'drunken-dragon':
            if (
                await get_player_x(state, 'exploration_avail') < n_tasks_needed
                or await get_player_x(state, 'combat_avail') < n_tasks_needed
                or await get_player_x(state, 'puzzle_avail') < n_tasks_needed
                or await get_player_x(state, 'dialogue_avail') < n_tasks_needed
            ):
                await state.ctx.followup.send(
                    f"Error: Not enough tasks available to progress quest. Need {n_tasks_needed} of each type, have {await get_player_x(state, 'exploration_avail')}, {await get_player_x(state, 'combat_avail')}, {await get_player_x(state, 'puzzle_avail')}, {await get_player_x(state, 'dialogue_avail')}."
                )
                return
            else:
                await increment_player_x(state, 'exploration_avail', -n_tasks_needed)
                await increment_player_x(state, 'combat_avail', -n_tasks_needed)
                await increment_player_x(state, 'puzzle_avail', -n_tasks_needed)
                await increment_player_x(state, 'dialogue_avail', -n_tasks_needed)
                await increment_player_x(state, 'debauchery_avail', -n_deb_tasks_needed)
        else:  # cover the regular task types
            if await get_player_x(state, f'{task_type}_avail') < n_tasks_needed:
                await state.ctx.followup.send(f"Error: Not enough {task_type} tasks available to progress quest.")
                return
            if await get_player_x(state, 'debauchery_avail') < n_deb_tasks_needed:
                await state.ctx.followup.send("Error: Not enough debauchery tasks available to progress quest.")
                return
            else:
                await increment_player_x(state, f'{task_type}_avail', -n_tasks_needed)
                await increment_player_x(state, 'debauchery_avail', -n_deb_tasks_needed)

    # progress the quest
    complete_result = await quest.progress_quest(state)  # returns None if the quest is not completed, or the difficulty of the quest if it is completed

    # Strength 5: Each completed quest step has a 30% chance to award 10 XP
    strength_level = await get_player_x(state, 'strength_level')
    wisdom_level = await get_player_x(state, 'wisdom_level')
    if strength_level >= 5 and random_with_bonus(state) < 0.3:
        await award_xp(state, 10)
        await ctx_print(state, "Skill bonus! Booze Boost: You gained 10 bonus XP for completing a quest step.")
    # Wisdom 20: Gain 10 bonus XP whenever you complete a quest step
    if wisdom_level >= 20:
        await award_xp(state, 10)
        await ctx_print(state, "Skill bonus! Oracle: You gained 10 bonus XP for completing a quest step.")
    # Wisdom 15: 20% chance to also complete the next quest step
    if complete_result is None and wisdom_level >= 15 and random_with_bonus(state) < 0.20:
        # Only attempt to progress if quest is not already completed
        current_quest = await get_player_x(state, 'current_quest')
        if current_quest:
            quest = await Quest.from_state(state)
            complete_result = await quest.progress_quest(state)
            await ctx_print(state, "Skill bonus! Chronomancy: You also completed the next quest step.")

    # if the quest was completed, add XP and rewards
    quest_xp = {
        'easy': 100,
        'medium': 200,
        'hard': 400
    }

    if complete_result: # the quest was completed
        # Increment the quest completion count
        await increment_player_x(state, f'{complete_result}_quest', 1)

        # Strength 35: Double the number of items you get from quest rewards
        strength_level = await get_player_x(state, 'strength_level')
        item_multiplier = 2 if strength_level >= 35 else 1
        # Strength 15: Complete 2 debauchery tasks on quest completion
        if strength_level >= 15:
            await increment_task(state, 'b', 2, log_task=False)
            await ctx_print(state, "Skill bonus! Take the Edge Off: You completed 2 debauchery tasks.")
        if complete_result in ('easy', 'medium', 'hard'):
            base_xp = quest_xp[complete_result]
            # e10: Buckler Shield - Quests are worth an additional 50 XP
            if await inventory_contains(state, 'e10'):
                base_xp += 50
                await ctx_print(state, "Item bonus! Buckler Shield: Quest XP increased by 50.")
            # m5: Cursed Keg - Quests give 50% more XP
            if await inventory_contains(state, 'm5'):
                base_xp = int(base_xp * 1.5)
                await ctx_print(state, "Item bonus! Cursed Keg: Quest XP increased by 50%")
            await increment_player_x(state, f'{complete_result}_quest', 1)
            await increment_player_x(state, f'{complete_result}_quest_points', item_multiplier)
            await award_xp(state, base_xp, double_allowed=False)
            if item_multiplier == 2:
                await ctx_print(state, "Skill bonus! Strength Mastery: You received double quest item points.")
        return complete_result
    else:
        # if the quest was not completed, check for item abilities to skip steps
        # Elven Compass (e1) - 25% chance to skip an exploration quest step
        if await inventory_contains(state, 'e1') and random_with_bonus(state) < 0.25 and task_type == 'exploration':
            await ctx_print(state, "Item bonus! Elven Compass: You skipped an exploration quest step.")
            complete_result = await quest.progress_quest(state)
        # Invisibility Cloak (e2) - 25% chance to skip a combat quest step
        elif await inventory_contains(state, 'e2') and random_with_bonus(state) < 0.25 and task_type == 'combat':
            await ctx_print(state, "Item bonus! Invisibility Cloak: You skipped a combat quest step.")
            complete_result = await quest.progress_quest(state)
        # Lockpick Set (e3) - 25% chance to skip a puzzle quest step
        elif await inventory_contains(state, 'e3') and random_with_bonus(state) < 0.25 and task_type == 'puzzle':
            await ctx_print(state, "Item bonus! Lockpick Set: You skipped a puzzle-solving quest step.")
            complete_result = await quest.progress_quest(state)
        # Silver Tongue (e4) - 25% chance to skip a dialogue quest step
        elif await inventory_contains(state, 'e4') and random_with_bonus(state) < 0.25 and task_type == 'dialogue':
            await ctx_print(state, "Item bonus! Silver Tongue: You skipped a dialogue quest step.")
            complete_result = await quest.progress_quest(state)
        # Lucky Rabbit's Foot (m10) - 15% chance to skip any quest step
        if not complete_result and await inventory_contains(state, 'm10') and random_with_bonus(state) < 0.15:
            complete_result = await quest.progress_quest(state)
            await ctx_print(state, "Item bonus! Lucky Rabbit's Foot: You skipped a quest step.")
    # Magic Rune (d5): 30% chance to complete an additional quest step when you complete a quest step
    if not complete_result and await inventory_contains(state, 'd5') and random_with_bonus(state) < 0.3:
        complete_result = progress_quest(state, skip_task_check=True) # skip the task check since this is a bonus step
        await ctx_print(state, "Item bonus! Magic Rune: You completed an additional quest step.")
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

async def complete_sidequest(state, task_type, skip_task_check=False):
    # Agility 10: Sidequests require only 2 non-Debauchery Tasks
    agility_level = await get_player_x(state, 'agility_level')
    required_tasks = 2 if agility_level >= 10 else 3

    if not skip_task_check:
    
        # d1: Map of Many Sips - Debauchery Tasks will be used to cover any missing non-Debauchery Tasks when completing sidequests
        non_deb_tasks_available = await get_player_x(state, f"{task_type}_avail")
        debauchery_available = await get_player_x(state, 'debauchery_avail')
        non_deb_to_spend = min(non_deb_tasks_available, required_tasks)
        debauchery_to_spend = 1
        if await inventory_contains(state, 'd1'):
            # Use debauchery tasks to cover any missing non-debauchery tasks
            missing = required_tasks - non_deb_tasks_available
            if missing > 0:
                if debauchery_available < (1 + missing):
                    await state.ctx.followup.send("Error: Not enough debauchery tasks available to complete sidequest (including covering missing non-debauchery tasks).")
                    return
                debauchery_to_spend += missing
                non_deb_to_spend = non_deb_tasks_available
        else:
            #normal check if the player has enough banked tasks to complete the sidequest
            if debauchery_available < 1:
                await state.ctx.followup.send("Error: Not enough debauchery tasks available to complete sidequest.")
                return
            if non_deb_tasks_available < required_tasks:
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
    await increment_player_x(state, f"{task_type}_avail", -non_deb_to_spend)
    await increment_player_x(state, 'debauchery_avail', -debauchery_to_spend)

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

    # Talking Wizard Hat (d9): A sidequest of Puzzle-Solving Tasks is worth twice as much XP
    if task_type == 'puzzle' and await inventory_contains(state, 'd9'):
        sq_xp_bonus *= 2
        await ctx_print(state, "Item bonus! Talking Wizard Hat: Your Puzzle-Solving sidequest is worth double XP!")

    # Award the main XP for completing the sidequest
    await award_xp(state, sq_xp_bonus, double_allowed=False)

    # Wisdom 5: Scrying Eye: Receive 5 bonus XP whenever you complete a sidequest
    if wisdom_level >= 5:
        await award_xp(state, 5)
        await ctx_print(state, f"Skill bonus! Scrying Eye: You gained bonus XP for this sidequest.")

    # --- Skill Effects: Agility 1, 20, 28 ---
    agility_level = await get_player_x(state, 'agility_level')
    # Agility 1: 10% chance for Easy Quest Item Point
    if agility_level >= 1 and random_with_bonus(state) < 0.10:
        await increment_player_x(state, 'easy_quest_points', 1)
        await ctx_print(state, "Skill bonus! You gained an Easy Quest Item Point.")
    # Agility 20: 20% chance to also complete the current quest step
    if agility_level >= 20 and random_with_bonus(state) < 0.20:
        # Progress the current quest if one exists
        current_quest = await get_player_x(state, 'current_quest')
        if current_quest:
            quest = await Quest.from_state(state)
            await quest.progress_quest(state)
            await ctx_print(state, "Skill bonus! You also progressed your current quest step.")
    # Agility 28: 20% chance for random item point
    if agility_level >= 28 and random_with_bonus(state) < 0.20:
        rarity = random.choice(['easy_quest_points', 'medium_quest_points', 'hard_quest_points'])
        await increment_player_x(state, rarity, 1)
        await ctx_print(state, f"Skill bonus! You gained a {rarity.replace('_', ' ').title()}.")

    # Game Genie Totem (m7): Completing a sidequest completes 1 of each type of non-Debauchery Task
    if await inventory_contains(state, 'm7'):
        await increment_task(state, 'e', 1, log_task=False)
        await increment_task(state, 'c', 1, log_task=False)
        await increment_task(state, 'p', 1, log_task=False)
        await increment_task(state, 'd', 1, log_task=False)
        await ctx_print(state, "Item bonus! Game Genie Totem: You completed 1 of each non-Debauchery Task.")

    # Potion of Progress (d4): 30% chance to produce an Easy Quest Item Point when completing a sidequest
    if await inventory_contains(state, 'd4') and random_with_bonus(state) < 0.3:
        await increment_player_x(state, 'easy_quest_points', 1)
        await ctx_print(state, "Item bonus! Potion of Progress: You gained an Easy Quest Item Point.")

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

    # Immediate effect items
    if item_id == 'e6': #Beer Belly +1
        await increment_task(state, 'b', 10, log_task=False) 
        await ctx_print(state, "Item bonus! Beer Belly +1: You immediately completed 10 Debauchery Tasks.")

    elif item_id == 'e8': # Magic Mirror
        sidequest_types = ['exploration', 'combat', 'puzzle', 'dialogue']
        chosen_type = random.choice(sidequest_types)
        await ctx_print(state, f"Item bonus! Sidequest Map: You immediately completed a {chosen_type} sidequest.")
        await complete_sidequest(state, chosen_type, skip_task_check=True)

    elif item_id == 'e9': # Emergency Rations
        await increment_task(state, 'e', 2, log_task=False)
        await increment_task(state, 'c', 2, log_task=False)
        await increment_task(state, 'p', 2, log_task=False)
        await increment_task(state, 'd', 2, log_task=False)
        await ctx_print(state, "Item bonus! Emergency Rations: You immediately completed 2 of each non-Debauchery Task.")

    elif item_id == 'm6': # Skill Shard
        current_level = await get_player_x(state, 'level')
        xp_award = current_level * 50
        await award_xp(state, xp_award)
        await ctx_print(state, f"Item bonus! Skill Shard: You immediately gained {xp_award} XP (Level {current_level} x 50 XP).")

    #decrement the player's quest points
    if item_id[0] == 'e':
        await increment_player_x(state, 'easy_quest_points', -1)
    elif item_id[0] == 'm':
        await increment_player_x(state, 'medium_quest_points', -1)
    elif item_id[0] == 'h':
        await increment_player_x(state, 'hard_quest_points', -1)
    await state.ctx.response.send_message(f"You have purchased {get_item_name(item_id)}.")

