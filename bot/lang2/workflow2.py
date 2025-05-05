from datetime import datetime
import os
import bot.lang2.database as database
from bot.lang2.mytypes import State, ExtractedData
import bot.lang2.actions as actions
from bot.lang2.llm import LLM
is_local = os.path.exists('.env')

if is_local:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env

BOSS_NAME = os.getenv("BOSS_NAME")
BOSS_ID = os.getenv("BOSS_ID")
BOSS_ID_TG = os.getenv("BOSS_ID_TG")
BOSS_EMAIL = os.getenv("BOSS_EMAIL")

class Bot2():
    def handle_intent(self, intent_data, email, username):
        kind = intent_data.get("kind")
        data = intent_data.get("data", {})
        
        if kind == "schedule":
            result = actions.schedule_meeting(data, email, username)
        elif kind == "cancel":
            result = actions.cancel_meeting(data)
        elif kind == "update":
            result = actions.update_meeting(data, email)
        else:
            result = actions.handle_unknown(data)

        return result
    
    def process_webhook_message(self, user_id: str, username: str, user_input: str) -> str:
        # Loading from database, if it exists
        state = database.load_state_tg(user_id)
        new_needed = False
        if state:
            if database.is_context_expired(state["updated_at_utc"]):
                new_needed = True
        else:
            new_needed = True
        # if it needs to be created or renewed
        if new_needed:
            state: State = {
                "user_id": user_id,
                "username": username,
                "email": "",
                "conversation": "",
                "messages": [],
                "updated_at_utc": datetime.utcnow().isoformat()
            }
        # Initialization
        messages = state["messages"]
        conversation = state["conversation"]
        email = state["email"]
        is_boss = (user_id == BOSS_ID_TG)
        if is_boss:
            state["email"] = BOSS_EMAIL
            state["username"] = BOSS_NAME
        # Loads meetings scheduled for the user
        meetings = actions.list_meetings(email, is_boss)
        messages.append({"role": "assistant", "content": meetings["info"]})
        conversation += meetings["info"] # Putting existing meetings into conversation
        # Creates LLM instace
        llm = LLM()
        # Adds user input to messages and to conversation
        messages.append({"role": "user", "content": user_input})
        conversation += f"User: {user_input}\n"
        # Extracts new data
        extracted_data = llm.extract_data(conversation)
        # Updates username and email:
        if extracted_data["username"] != "":
            state["username"] = extracted_data["username"]
        state["email"] = extracted_data["email"]
        # Results of each action
        result_list = []
        for intent in extracted_data.get("intents", []):
            result = self.handle_intent(intent, state["email"], state["username"])
            messages.append({"role": "assistant", "content": result["info"]})
            result_list.append(result)
        # Generates bot response and saves to messages and conversation
        bot_output = llm.gen_response(messages, is_boss=True)
        messages.append({"role": "assistant", "content": bot_output})
        conversation += f"Secretary: {bot_output}\n"
        # Saving in database
        state["updated_at_utc"] = datetime.utcnow().isoformat()
        state["conversation"] = conversation
        state["messages"] = messages
        database.save_state_tg(user_id, state)
        return bot_output

    # Method for local test with the terminal
    def run(self):
        user_id = BOSS_ID
        state: ExtractedData = {
            "username": "",
            "email": "",
            "intents": []
        }
        messages = []
        conversation = ""
        meetings = actions.list_meetings(BOSS_EMAIL, True)
        messages.append({"role": "assistant", "content": meetings["info"]})
        conversation = meetings["info"] # Putting existing meetings into conversation
        llm = LLM()
        while True:
            user_input = input("You: ")
            if user_input.lower() in {"exit", "quit"}:
                break
            messages.append({"role": "user", "content": user_input})
            conversation += f"User: {user_input}\n"
            extracted_data = llm.extract_data(conversation)
            print("Extracted data: ", extracted_data)
            result_list = []
            for intent in extracted_data.get("intents", []):
                result = self.handle_intent(intent, state["email"], state["username"])
                print("Result", result)
                messages.append({"role": "assistant", "content": result["info"]})
                result_list.append(result)
            bot_output = llm.gen_response(messages, is_boss=True)
            messages.append({"role": "assistant", "content": bot_output})
            conversation += f"Secretary: {bot_output}\n"
            print(f"Bot: {bot_output}")

if __name__ == "__main__":
    bot = Bot2()
    bot.run()



