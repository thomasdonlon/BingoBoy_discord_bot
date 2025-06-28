#manages the AI conversation with the player (handles system prompts, etc)

import openai

def ai_error_message(): #TODO: Add this if I feel like it
	#get the AI to generate a silly, themed error message when the player attempts to do something impossible 
	#    (like spend more skill points than they have)
	pass

async def ai_get_response(prompt, model="o4-mini", max_tokens=1000): #gpt-4 was original
    try:
        response = openai.OpenAI().chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in ai_get_response: {e}")
        return "An error occurred while processing your request."
