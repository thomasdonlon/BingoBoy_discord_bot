#some functionality for quests, easier to separate out in its own file 

import conversation
import random
from text_storage import quest_name_prompt, quest_ai_prompt, drunken_dragon_ai_prompt

#---------------------------------------
# Helpers
#---------------------------------------

def format_quest_status(quest):
	#format the quest status for display
	#this is used in the quest status command to show the current quest status to the player
	return f"{quest.name}: Difficulty: {quest.difficulty}, " \
		   f"Step {quest.current_step_num + 1}/{quest.total_step_number}, " \
		   f"Need {quest.current_step_num_tasks} {quest.current_step_type} tasks " \
		   f"and {quest.current_step_num_deb_tasks} Debauchery tasks."

#---------------------------------------
# Reading/Writing
#---------------------------------------
#the Quest class is used to make the python code simpler, but the state has to be saved in the DB any time that we make changes. 
	#the format for a quest is (as a single large string):
	#	quest_name: (no new lines in actual string, that's just for formatting here -- separation by colon)
	#	quest_difficulty:
	#	current_step_number:
	#   total_number_of_steps:
	#	current_step_type:
	#	current_step_number_of_tasks:
	#	current_step_number_of_debauchery_tasks:
	#	previous_text_context (separated by semicolons)

async def read_quest_from_db(state): #load in quest from db after saving it
	quest = Quest(state.difficulty)  # Create a new Quest instance with the given difficulty
	async with state.bot.pool.acquire() as con:
		row = await con.fetchrow(f"SELECT current_quest FROM data WHERE name = '{state.player}'")
		if row is not None:
			quest_string = row['current_quest']
			if quest_string:  # Check if the quest string is not empty
				quest_data = quest_string.split(':')
				if len(quest_data) == 8:  # Ensure the correct number of fields
					quest.name = quest_data[0]
					quest.difficulty = quest_data[1]
					quest.current_step_num = int(quest_data[2])
					quest.total_step_number = int(quest_data[3])
					quest.current_step_type = quest_data[4]
					quest.current_step_num_tasks = int(quest_data[5])
					quest.current_step_num_deb_tasks = int(quest_data[6])
					quest.text_log = quest_data[7].split(';') if quest_data[7] else []
	return quest

#---------------------------------------
# Class Definition
#---------------------------------------

class Quest:
	async def __init__(self, state, difficulty):
		self.name = None
		self.difficulty = difficulty #str, 'easy', 'medium' or 'hard'
		self.current_step_num = 0
		self.total_step_number = None
		self.current_step_type = None
		self.current_step_num_tasks = None
		self.current_step_num_deb_tasks = None
		self.text_log = [] #holds previous AI text for context

		await self.start_quest(state)
		await self.write_quest_to_db(state)

	@classmethod
	# Factory method to create a Quest instance from a saved state
	async def from_state(cls, state):
		quest = Quest(state.difficulty)  # Create a new Quest instance with the given difficulty
		async with state.bot.pool.acquire() as con:
			row = await con.fetchrow(f"SELECT current_quest FROM data WHERE name = '{state.player}'")
			if row is not None:
				quest_string = row['current_quest']
				if quest_string:  # Check if the quest string is not empty
					quest_data = quest_string.split(':')
					if len(quest_data) == 8:  # Ensure the correct number of fields
						quest.name = quest_data[0]
						quest.difficulty = quest_data[1]
						quest.current_step_num = int(quest_data[2])
						quest.total_step_number = int(quest_data[3])
						quest.current_step_type = quest_data[4]
						quest.current_step_num_tasks = int(quest_data[5])
						quest.current_step_num_deb_tasks = int(quest_data[6])
						quest.text_log = quest_data[7].split(';') if quest_data[7] else []
		return quest

	#---------------------------------------
	# Reading/Writing
	#---------------------------------------

	async def write_quest_to_db(self, state): 
		quest_string = f"{self.name}:{self.difficulty}:{self.current_step_num}:{self.total_step_number}:{self.current_step_type}:{self.current_step_num_tasks}:{self.current_step_num_deb_tasks}:{';'.join(self.text_log)}"
		async with state.bot.pool.acquire() as con:
			await con.execute(f"UPDATE data SET current_quest = '{quest_string}' WHERE name = '{state.player}'")

	async def reset_quest_in_db(self, state):
		async with state.bot.pool.acquire() as con:
			await con.execute(f"UPDATE data SET current_quest = NULL WHERE name = '{state.player}'")

	#---------------------------------------
	# Progression
	#---------------------------------------

	def generate_new_tasks(self, state):
		if self.difficulty == 'easy':
			self.current_step_num_tasks = random.randint(2,3)
			self.current_step_num_deb_tasks = random.randint(1,2)
		elif self.difficulty == 'medium':
			self.current_step_num_tasks = random.randint(2,4)
			self.current_step_num_deb_tasks = random.randint(2,3)
		elif self.difficulty == 'hard':
			self.current_step_num_tasks = random.randint(3,5)
			self.current_step_num_deb_tasks = random.randint(2,5)
		
		self.current_step_type = random.choice(('exploration', 'combat', 'puzzle', 'dialogue'))

		if self.difficulty == 'drunken-dragon':
			self.current_step_num_tasks = 3
			self.current_step_num_deb_tasks = 3
			self.current_step_type = 'drunken-dragon'
			
	async def start_quest(self, state): #have it split up this way so that the AI messages can be more tailored to the current quest state

		#set total number of steps
		if self.difficulty == 'easy':
			self.total_step_number = random.randint(2,3)
		elif self.difficulty == 'medium':
			self.total_step_number = random.randint(3,4)
		elif self.difficulty == 'hard':
			self.total_step_number = random.randint(3,5)
		elif self.difficulty == 'drunken-dragon':
			self.total_step_number = 5

		#set current number and type of tasks
		self.generate_new_tasks(state)
		await self.progress_quest_message(state)
		await self.write_quest_to_db(state)

	async def progress_quest(self, state): #progress the quest, incrementing the step number and generating new tasks if needed
		                                   #xp and rewards will be handled in the main.py part of things
		if self.current_step_num >= self.total_step_number:
			await state.ctx.response.send_message("Error: Cannot progress quest, already completed.")
			print("Error: Cannot progress quest, already at maximum step number.")
			return
		
		self.current_step_num += 1
		await self.progress_quest_message(state)
		if self.current_step_num == self.total_step_number:
			tmp_difficulty = self.difficulty  # Store the current difficulty before resetting
			await self.reset_quest_in_db(state)
			if self.difficulty == 'drunken-dragon':
				await state.ctx.response.send_message("You have defeated the Drunken Dragon! You win the Gauntlet of Grog, and have saved the Kingdom of Brewgard!")
			else:
				await state.ctx.response.send_message(f"You have completed the quest '{self.name}'! You may start a new quest at any time.")
			return tmp_difficulty
		else:
			self.generate_new_tasks(state)
			await self.write_quest_to_db(state)
			await state.ctx.response.send_message(f"You have completed step {self.current_step_num} of {self.total_step_number} for the quest '{self.name}'.")
		return

	async def abandon_quest(self, state): #abandon the quest, resetting it in the database
		await self.reset_quest_in_db(state)
		await state.ctx.response.send_message("You have abandoned the quest. You may start a new one at any time.")

	#---------------------------------------
	# Wrapper for ChatGPT Interaction 
	#---------------------------------------

	async def progress_quest_message(self, state):
		#get a name for the quest
		if self.difficulty == 'drunken-dragon':
			self.name = "The Drunken Dragon"

			#generate the quest message
			quest_message = await conversation.ai_get_response(
				drunken_dragon_ai_prompt(self.current_step_number, self.total_step_number, self.text_log)
			)
		else:
			if self.current_step_num == 0:  # Only get a name for the quest at the start
				self.name = await conversation.ai_get_response(quest_name_prompt)

			#generate the quest message
			quest_message = await conversation.ai_get_response(
				quest_ai_prompt(self.name, self.current_step_number, self.total_step_number, self.current_step_type, self.text_log)
			)
		
		#send the quest message to the player
		await state.ctx.response.send_message(quest_message)

		#add the quest message to the text log for context
		self.text_log.append(quest_message)

	