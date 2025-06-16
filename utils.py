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

def get_item_name(item_id, skill_levels=None):
    """
    Returns the name of the item based on its ID, adjusting percentage values for Agility 15/35 and Tankard of Tenacity.
    """
    from text_storage import item_descriptions
    text = item_descriptions.get(item_id, "Unknown Item")
    percent_mod = 0
    if skill_levels:
        # Agility 15: +15%, Agility 35: double base percentage
        if skill_levels.get('agility', 0) >= 35:
            percent_mod += 100  # double (100% increase)
        elif skill_levels.get('agility', 0) >= 15:
            percent_mod += 15
        # Tankard of Tenacity: +2% per debauchery task (handled elsewhere if needed)
    import re
    def repl(match):
        base = int(match.group(1))
        mod = base
        if percent_mod:
            mod = base + (base * percent_mod // 100)
        return f"{mod}%"
    text = re.sub(r"(\d+)%", repl, text)
    return text

def get_skill_description(skill, level, skill_levels=None):
    """
    Returns the description of a skill at a given level, adjusting percentage values for Agility 15/35 and Tankard of Tenacity.
    """
    from text_storage import skill_level_descriptions
    text = skill_level_descriptions.get(skill, {}).get(level, "Unknown Skill Level")
    percent_mod = 0
    if skill_levels:
        if skill_levels.get('agility', 0) >= 35:
            percent_mod += 100
        elif skill_levels.get('agility', 0) >= 15:
            percent_mod += 15
    import re
    def repl(match):
        base = int(match.group(1))
        mod = base
        if percent_mod:
            mod = base + (base * percent_mod // 100)
        return f"{mod}%"
    text = re.sub(r"(\d+)%", repl, text)
    return text
    
async def ctx_print(state, text, ephemeral=False):
    try: #try a deferred context response 
        await state.ctx.followup.send(text, ephemeral=ephemeral)
    except Exception as e: #if the deferred response fails, send a regular interaction message instead
        await state.ctx.response.send_message(text, ephemeral=ephemeral)