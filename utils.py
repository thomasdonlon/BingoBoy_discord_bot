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
    if item_id in item_descriptions.keys():
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
    except Exception as e: #if the deferred response fails, send a regular interaction message instead
        await state.ctx.response.send_message(text, ephemeral=ephemeral)