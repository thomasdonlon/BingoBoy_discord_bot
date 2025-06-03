#storage of large tables, skill and item text, etc. so it doesn't gunk up the other files
#also has some functions for converting item codes into actual text descriptions

'''
The Gauntlet of Grog,
Hail, hero! The Kingdom of Brewgard - a noble land forged on hops, honor, and hangovers - has fallen under a terrible spell. Across the realm, honest folks are finding their mugs and goblets magically drained before they have a chance to take a sip. Rumors abound of a Drunken Dragon settling in the nearby wilderness, which must be responsible for this calamity. 

Your goal: Become a party of strong heroes, locate this Drunken Dragon, and slay it. Be celebrated as the heroes who saved Brewgard! 

--------------------------------------------,
Overview:
Your team begins at level 1 with no XP. Completing quests will give you XP to level up, as well as beneficial items with powerful bonuses. As you level up, you may improve your skills, which provide helpful boons. At level 10, you may choose to fight the Drunken Dragon. The first team to defeat the Drunken Dragon and save Brewgard wins!

Your progress in your mission will be tracked by the BingoBoy bot, which you interact with in your team-specific bot channel. The progress of each team will be shown in the <<to be determined channel>>. 

Rules:

Tasks:
The Task List returns in this game of tankards & trials! This time, the task list is split into 5 categories: Exploration, Combat, Puzzle-Solving, Dialogue, and Debauchery. Once you complete a task, you can add it to your "Completed Task Pool", which can then be spent to progress quests and sidequests. Tasks may be completed multiple times, but no more than 5 times per task (except for Debauchery Tasks, which may be completed as many times as you like).

XP and Levels:
You begin at level 1 with 0 XP. You level up by gaining XP. The amount of XP required to level up increases per level; level 2 requires 100 XP, level 3 requires 200 more XP (a total of 300 XP), level 4 requires 300 more XP (a total of 600 XP), etc. The maximum level is 10. 

Skills:
Your party has 3 skills: Strength, Dexterity, and Wisdom. Each skill can be leveled up by allocating skill points; at certain levels, you gain access to powerful bonuses that will help you complete quests, gain XP, and defeat the Drunken Dragon more quickly. 

When you level up, you gain skill points. The number of skill points you gain is equal to your new level: for example, when you become level 2, you gain 2 skill points; at level 6, you gain 6 skill points. You begin with 1 skill point -- allocate it as soon as you can. (You will have a total of 45 skill points at level 10.)

Quests:
Quests are a sequential collection of tasks that provide your hero with a substantial amount of XP and a Magical Item upon completion. Each step of a quest will call for a radomly generated number and type of task in order to progress. 

There are three tiers of quests: 
 
Easy Quest (worth 100 XP): 
2-3 steps; each step requires [2-3] non-Debauchery Tasks and [1-2] Debauchery Tasks,

Medium Quest (worth 200 XP):
3-4 steps; each step requires [2-4] non-Debauchery Tasks and [2-3] Debauchery Tasks,

Hard Quest (worth 400 XP): 
3-5 steps; each step requires [3-5] non-Debauchery Tasks and [2-5] Debauchery Tasks,


Completing a quest also allows you to also obtain an item from the Quest Item Table. These items are grouped according to the difficulty of the quest -- for example, completing a Medium Quest will let you pick one item from the "Medium Quest Item" group on the Quest Item Table. (You can, for example, spend a medium quest item point on an easy quest item; if you have multiple quest item points when buying an item, you will automatically spend the lowest tier possible).

Quests are randomly generated upon selecting a tier. Each team may only have 1 active quest at a given time (although you can abandon your current quest whenever you choose). Sidequests can be completed at any time. 

There is an additional special quest: "The Drunken Dragon". If you are the first to complete this quest, you win the game. This quest consists of 5 steps, each requiring [3] of each type of task. 

Sidequests:
Sidequests allow you to spend completed tasks without the category restrictions of quests. To complete a sidequest, you may spend [3] tasks of the same category plus [1] Debauchery Task.

Sidequests provide telescoping XP: The first sidequest you complete is worth 10 XP. The second sidequest you complete will be worth 20 XP, the third is worth 30 XP, and so on.
'''

#hard coding because I'm lazy
xp_level_thresholds = (100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500) 
skill_level_thresholds = (1, 3, 5, 10, 15, 20, 28, 35)

skill_level_descriptions = {
    'strength': {
        1: 'Liguid Courage: Completing a Debauchery Task also provides +2 XP.',
        3: r"Tavern Brawler: You have a 25% chance to complete 2 Combat Tasks instead of 1.",
        5: r"Booze Boost: Each completed quest step has a 30% chance to award 10 XP.",
        10: "Intimidation: Quests will never require the maximum amount of steps (does not apply to Drunken Dragon).",
        15: "Take the Edge Off: When you complete a quest, you automatically complete 2 debauchery tasks.",
        20: "Monk of the Drunken Fist: Debauchery tasks will be used to cover any missing non-Debauchery Tasks when completing a quest step.",
        28: "Dragon Slayer: Skip the first two steps of the Drunken Dragon quest. ",
        35: "Strength Mastery: Double the number of items you get from quest rewards."
    },
    'agility': {
        1: r'Nature Spirit: Completing a sidequest has a 10% chance of yielding an Easy Quest Item Point.',
        3: r"Ranger: You have a 25% chance to complete 2 Exploration Tasks instead of 1.",
        5: "Farsighted: Sidequest XP now increases by +20 XP rather than +10 XP.",
        10: "Quick Feet: Sidequests now only require [2] non-Debauchery Tasks.",
        15: r"Sleight of Hand: Increase the percentage in all your item and skill descriptions by 15%.",
        20: r"Multitasker: Completing a sidequest has a 20% chance to also complete the current quest step.",
        28: r"Sticky Fingers: Completing a sidequest has a 20% chance of rewarding an item point of random rarity.",
        35: "Agility Mastery: Double the base percentage in all your item and skill descriptions."
    },
    'wisdom': {
        1: r"Bardic Inspiration: You have a 25% chance to complete 2 Dialogue Tasks instead of 1",
        3: r"Arcane Initiate: You have a 25% chance to complete 2 Puzzle-Solving Tasks instead of 1.",
        5: "Scrying Eye: Recieve 5 XP whenever another party completes a sidequest.",
        10: "Gifted: Gain an additional 50 XP when you level up.",
        15: r"Chronomancy: Completing a quest step has a 20% chance to also complete the next quest step. ",
        20: "Oracle: Gain 20 XP whenever another hero completes a quest. ",
        28: "Epiphany: Immediately gain 500 XP. This XP cannot be boosted by other skills or items.",
        35: "Wisdom Mastery: Double all sources of XP except completing quests and sidequests. "
    }
}

item_descriptions = {
    'e1': r"Elven Compass: 25% chance to skip an Exploration quest step",
    'e2': r"Invisibility Cloak: 25% chance to skip a Combat quest step",
    'e3': r"Lockpick Set: 25% chance to skip a Puzzle-solving quest step",
    'e4': r"Magic Mirror: 25% chance to skip a Dialoque quest step",
    'e5': r"Strength Potion: 10% chance to complete a Combat Task whenever you complete a non-Debauchery Task",
    'e6': r"Beer Belly: Immediately complete 10 Debauchery Tasks.",
    'e7': r"Lucky Coin: 10% chance to provide 10 XP when you complete a non-Debauchery Task",
    'e8': r"Replenishing Flask: Immediately complete a sidequest",
    'e9': r"Emergency Rations: Immediately complete [2] of each non-Debauchery Task.",
    'e10': r"Buckler Shield: Quests are worth an additional 50 XP.",
    'm1': r"Pathfinder Potion: Completing an Exploration task now awards 10 XP.",
    'm2': r"Mithril Sword: Completing a Combat task now awards 10 XP.",
    'm3': r"Arcane Eye: Completing a Puzzle-Solving task now awards 10 XP.",
    'm4': r"Golden Lip Balm: Completing a Dialogue task now awards 10 XP.",
    'm5': r"Cursed Keg: Quests give 50% more XP, but require twice as many Debauchery Tasks.",
    'm6': r"Skill Shard: Immediately gain XP equal to your current level x 50.",
    'm7': r"Game Genie Totem: Completing a sidequest completes 1 of each type of non-Debauchery Task.",
    'm8': r"Scroll of Misty Step: Start each quest on the 2nd step.",
    'm9': r"Robe of Stars: Gain 1 additional skill point when you level up.",
    'm10': r"Lucky Rabbit's Foot: You have a 15% chance to automatically skip each quest step.",
    'd1': r"Map of Many Sips: Debauchery Tasks will be used to cover any missing non-Debauchery Tasks when completing sidequests.",
    'd2': r"Dragon-Slaying Lance: The Drunken Dragon quest steps only require [2] of each type of task.",
    'd3': r"Runestone of Repetition: 50% chance to complete each Task twice.",
    'd4': r"Potion of Progress: Completing a sidequest has a 30% chance of producing an Easy Quest Item Point.",
    'd5': r"Magic Rune: 50% chance to complete an additional quest step when you complete a quest step.",
    'd6': r"Scrying Orb: Quest steps always require the smallest number of tasks possible.",
    'd7': r"Tankard of Tenacity: All skill and item percentages are increased by 2% (up to 100%) for each banked Debauchery Task.",
    'd8': r"Bejeweled Scepter: All XP drops are increased by 1 x the number of items you have.",
    'd9': r"Talking Wizard Hat: A sidequest of Puzzle-Solving Tasks is worth twice as much XP.",
    'd10': r"Mead of Madness: Non-debauchery tasks can now be completed as many times as you like."
}

base_ai_prompt = "You are providing a text-based RPG adventure game experience. " \
                 "The player is a hero in the medieval Kingdom of Brewgard, which has fallen under a terrible spell: sometimes, a mug of grog will magically go dry before anyone has a chance to take a sip. " \
                 "The kingdom's residents include all fantasy races, who go about stereotypical medieval fantasy business, but they invariably spend their time drinking grog and liquor, and smoking pipe-weed. " \
                 "Always maintain a comical and engaging tone. " 

#---------------------------------
# FUNCTIONS
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
    
quest_name_prompt =  f"You are currently generating the name of a quest for the player to complete. " \
                     f"Example quests include finding and slaying a monster, fetching a lost item for a wizard, or navigating an ancient temple to rescue a princess. " \
                     f"Example quest names include 'The Lost Treasure of Alespire', 'The Slaying of the Mead Monster', and 'The Rescue of Princess Alea'. " \
                     f"Come up with a short and catchy name for the quest. Provide only the name of the quest and no other content. " \
    
def quest_ai_prompt(name, current_step_number, total_step_number, type, context):
    prompt = base_ai_prompt + \
    f"You are currently generating a quest for the player to complete. " \
    f"Quests consist of a series of tasks that the player must complete in order to progress. " \
    f"Example quests include finding and slaying a monster, fetching a lost item for a wizard, or navigating an ancient temple to rescue a princess. " \
    f"The name of the quest is '{name}'. " \
    f"The content of your response should be roughly 2 sentences long. "

    if current_step_number < total_step_number:
        if current_step_number == 0:
            prompt += f"This is the first step of the quest. " \
                      f"Invent a yet unfinished new task or problem for the player to solve, requiring the player to engage in {type}."
        else:
            prompt += f"It should include the actions of the player to complete the previous step of the quest, " \
                      f"and a yet unfinished new task or problem for the player to solve, requiring the player to engage in {type}."
            prompt += f"This is step {current_step_number} of {total_step_number} steps in the quest. "
            prompt += f"The previous text in this quest is provided here: {context}. Pick up where the previous step left off. "
    else:
        prompt += f"This is the final step of the quest. Wrap up all content from previous steps. " \
                  f"The content of your response should be roughly 3 sentences long. " \
                  f"The player does not need to complete any additional tasks to finish the quest. " \
                  f"Provide a reason why the player obtains a magical item as a reward for completing the quest. " \
    
    return prompt

def sidequest_ai_prompt(type):
    prompt = base_ai_prompt + \
    f"You are currently generating a sidequest for the player to complete. " \
    f"A sidequest consist of a single task that the player have completed in order to progress. They are self-contained and do not leave cliffhangers. " \
    f"The content of your response should be roughly 3 sentences long. " \
    f"It should begin with the name of the sidequest, followed by a description of the task that the player has completed. " \
    f"This sidequest is focused on {type}. " \
    
    return prompt

def drunken_dragon_ai_prompt(current_step_number, total_step_number, context):
    prompt = base_ai_prompt + \
    f"You are currently generating a quest for the player to complete. " \
    f"This is the Drunken Dragon quest, which is a special quest that is only available to players who have reached max level. " \
    f"The players are trying to defeat the Drunken Dragon, which has been terrorizing the Kingdom of Brewgard. " \
    f"They have to hunt it down in the wilderness, and then defeat it in a final battle. " \

    if current_step_number < total_step_number:
        prompt += f"The content of your response should be roughly 2 sentences long. " \
                  f"It should include the actions of the player to complete the last step of the quest, " \
                  f"and a yet unfinished new task or problem for the player to solve in order to progress to the next step. "
        if current_step_number == 0:
            prompt += f"This is the first step of the quest. "
        else:
            prompt += f"This is step {current_step_number} of {total_step_number} steps in the quest. "
            prompt += f"The previous text in this quest is provided here: {context}. Pick up where the previous step left off. "
    else:
        prompt += f"This is the final step of the quest. Wrap up all content from previous steps. " \
                  f"The content of your response should be roughly 2 sentences long. " \
                  f"The player does not need to complete any additional tasks to finish the quest. "

    return prompt

def sanitize_text(text):
    """
    Cleans the text to remove any naughty SQL characters. This also prevents the chatgpt output from breaking the SQL query.
    """

    #remove any naughty characters that could be used for SQL injection or other nefarious purposes
    naughty_strings = ["'", '"', ':', ';', '\\', '-', '(', ')', '[', ']', '{', '}', '<', '>', '=', '!', '@', '#', '$', '%', '^', '&', '*', '+', '/', '|']

    for naughty in naughty_strings:
        text = text.replace(naughty, '')
    
    return text.strip()
