import os
from openai import OpenAI
import json
from typing import List
import bot.lang2.prompts2 as prompts
is_local = os.path.exists('.env')

if is_local:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env

class LLM():
    def __init__(self):
        super().__init__()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.prompts = {
            "default": prompts.def_prompt,
            "user_boss": prompts.user_boss,
            "user_other": prompts.user_other,
            "gen_response_base": prompts.gen_response_base,
            "extract_info_base": prompts.extract_info_base
            }
        
    # LLM (OpenAI)        
    def gen_response(self, messages: List, is_boss: bool, meetings_str: str = None, email: str = None):
        context = [{"role": "system", "content": prompts.def_prompt},
                   {"role": "system", "content": prompts.gen_response_base}
                  ]
        if is_boss:
            context.append({"role": "system", "content": prompts.user_boss})
        else:
            context.append({"role": "system", "content": prompts.user_other})
            if email and email != "":
                context.append({"role": "assistant", "content": f"INFO: The user email address is: {email}"})
        if meetings_str:
            context.append({"role": "assistant", "content": meetings_str})
        context.extend(messages)
        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=context,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
        
    def extract_data(self, conversation: str, meetings_str: str = None) -> dict:
        context = [{"role": "system", "content": prompts.extract_info_base},
                   {"role": "system", "content": prompts.time_handle_for_extract}]
        if meetings_str:
            conversation += meetings_str
        context.append({"role": "user", "content": conversation})
        response = self.client.chat.completions.create(
            model="gpt-4.1",
            messages=context,
            temperature=0.7
        )
        content = response.choices[0].message.content
        print(content)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            print("Invalid JSON. Raw content:", content)
            parsed = {}
        return parsed