#some functionality for quests, easier to separate out in its own file 

import conversation
import random
from text_storage import quest_name_prompt, quest_ai_prompt, drunken_dragon_ai_prompt
from utils import sanitize_text, replace_text_codes

#---------------------------------------
# Helpers
#---------------------------------------

def format_quest_status(quest):
	#format the quest status for display
	#this is used in the quest status command to show the current quest status to the player
	return f"{replace_text_codes(quest.name)}:\nDifficulty: {quest.difficulty}\n" \
		   f"Step {quest.current_step_num + 1}/{quest.total_step_number}\n" \
		   f"Need {quest.current_step_num_tasks} {quest.current_step_type} tasks " \
		   f"and {quest.current_step_num_deb_tasks} Debauchery task(s)."

#---------------------------------------
# Reading/Writing
#---------------------------------------
#the Quest class is used to make the python code simpler, but the state has to be saved in the DB any time that we make changes to be loaded in later. 
	#the format for a quest is (as a single large string):
	#	quest_name: (no new lines in actual string, that's just for formatting here -- separation by colon)
	#	quest_difficulty:
	#	current_step_number:
	#   total_number_of_steps:
	#	current_step_type:
	#	current_step_number_of_tasks:
	#	current_step_number_of_debauchery_tasks:
	#	previous_text_context (separated by semicolons)

#---------------------------------------
# Class Definition
#---------------------------------------

class Quest:
	@classmethod
	# Factory method to create a Quest instance (have to do it this way rather than __init__ because of the async nature of the code)
	async def create(cls, state, difficulty):
		self = cls()
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
		return self

	@classmethod
	# Factory method to create a Quest instance from a saved state
	async def from_state(cls, state):
		self = cls()
		async with state.bot.pool.acquire() as con:
			row = await con.fetchrow(f"SELECT current_quest FROM data WHERE name = '{state.player}'")
			if row is not None:
				quest_string = row['current_quest']
				if quest_string:  # Check if the quest string is not empty
					quest_data = quest_string.split(':')
					if len(quest_data) == 8:  # Ensure the correct number of fields
						self.name = quest_data[0]
						self.difficulty = quest_data[1]
						self.current_step_num = int(quest_data[2])
						self.total_step_number = int(quest_data[3])
						self.current_step_type = quest_data[4]
						self.current_step_num_tasks = int(quest_data[5])
						self.current_step_num_deb_tasks = int(quest_data[6])
						self.text_log = quest_data[7].split(';') if quest_data[7] else []
		return self

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
			await state.ctx.followup.send("Error: Cannot progress quest, already completed.")
			print("Error: Cannot progress quest, already at maximum step number.")
			return
		
		self.current_step_num += 1
		await state.ctx.followup.send(f"You have completed step {self.current_step_num} of {self.total_step_number} of the quest '{replace_text_codes(self.name)}'!")
		
		#we run these either way
		self.generate_new_tasks(state) #has to run before progress_quest_message
		await self.progress_quest_message(state)

		if self.current_step_num == self.total_step_number: #quest is finished
			tmp_difficulty = self.difficulty  # Store the current difficulty before resetting
			await self.reset_quest_in_db(state)
			if self.difficulty == 'drunken-dragon':
				await state.ctx.followup.send("You have defeated the Drunken Dragon! You win the Gauntlet of Grog, and have saved the Kingdom of Brewgard!")
			else:
				await state.ctx.followup.send(f"You have completed the quest '{replace_text_codes(self.name)}'! You may start a new quest at any time.")
			return tmp_difficulty
		else: #quest is not finished yet
			await self.write_quest_to_db(state)
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
			if self.current_step_num == 0:
				self.name = "The Drunken Dragon"

			#generate the quest message
			quest_message = await conversation.ai_get_response(
				drunken_dragon_ai_prompt(self.current_step_num, self.total_step_number, self.text_log)
			)
		else:
			if self.current_step_num == 0:  # Only get a name for the quest at the start
				self.name = sanitize_text(await conversation.ai_get_response(quest_name_prompt)) #chatgpt loves to toss in problematic characters, so we remove them here

			#generate the quest message
			quest_message = await conversation.ai_get_response(
				quest_ai_prompt(self.name, self.current_step_num, self.total_step_number, self.current_step_type, self.text_log)
			)

		quest_message = sanitize_text(quest_message)  # Clean the text to remove any naughty SQL characters
		
		#send the quest message to the player
		out_text = replace_text_codes(self.name)
		if self.current_step_num == self.total_step_number:
			out_text += f': Quest completed!\n\n'
		else:
			out_text += f': Step {self.current_step_num + 1} of {self.total_step_number}\n\n'
		out_text += replace_text_codes(quest_message)
		if self.current_step_num < self.total_step_number:
			out_text += f'\n\nRequires {self.current_step_num_tasks} {self.current_step_type} tasks and {self.current_step_num_deb_tasks} debauchery task(s).'

		await state.ctx.followup.send(out_text)

		#add the quest message to the text log for context
		self.text_log.append(quest_message)

	