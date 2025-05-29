#some functionality for quests, easier to separate out in its own file 

import conversation

class Quest:
	def __init__(self, difficulty):
		self.difficulty = difficulty #str, 'easy', 'medium' or 'hard'
		self.current_step_num = 0
		self.text_log = [] #holds previous AI text for context

		self.start_quest()

	def start_quest(self): #have it split up this way so that the AI messages can be more tailored to the current quest state
		pass
	
	def progress_quest(self):
		pass

	def complete_quest(self):
		pass