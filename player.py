#the main machinery of the game, back-end for actions a player can take

from quest import Quest
import conversation

def xp_level_thresholds = [100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500] #hard coding because I'm lazy

class Player:

	def __init__(self,):

		#leveling, xp, etc
		self.level = 1
		self.xp = 0
		self.skill_points = 1
		self.skill_levels = {'strength':0, 'agility':0, 'wisdom':0}
		
		#questing and inventory
		self.task_pool = {'exploration':0, 'combat':0, 'puzzle':0, 'dialogue':0, 'debauchery':0}
		self.quest = None #current quest
		self.item_points = {'easy':0, 'medium':0, 'hard':0}
		self.inventory = []

		#some additional tracking we care about
		self.num_quests_completed = 0
		self.num_sidequests_completed = 0

	#leveling
	def award_xp(self):
		pass

	def level_up(self):
		self.level += 1
		self.skill_points += self.level
		pass

	#skills
	def allocate_skill_point(self, type):
		#type = 'strength', 'agility', or 'wisdom'
		pass

	#questing
	def start_quest(self, difficulty):
		self.quest = Quest(difficulty) #quests automatically start when they are initialized

	def progress_quest(self):
		pass

	def complete_quest(self):
		pass

	def complete_sidequest(self, type):
		#type = 'exploration', 'combat, 'puzzle', 'dialogue'
		pass

	#items
	def buy_item(self, item_id):
		pass

