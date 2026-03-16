from openai import OpenAI
import os
import json

import config
from foundation_model import run_llm

from dotenv import load_dotenv
env_path = config.env_path
load_dotenv()

def summarize_weekly_schedule(meeting_log_dir:str, id_list, id_role_map:dict, week_id:int):
    """
    Summarize the weekly schedule from the meeting minutes.
    """

    mintues_path = os.path.join(meeting_log_dir, "meeting_response.csv")
    json_path = os.path.join(meeting_log_dir, f"meeting_schedule_week_{week_id}.json")

    for attempt in range(config.max_attempt):

        # read the meeting minutes from output/meeting_response.csv
        with open(os.path.join(mintues_path), "r") as f:
            meeting_minutes = f.read()
        
        system_prompt = f"""You are a scheduler for a {config.company_type} of {config.employee_number} employees.
                                The company has {config.employee_number} employees with detailed role mapping as follows: {id_role_map}
                                \n\n The goal of the company is {config.goal} in {config.period} weeks. 
                                I will provide you with the detailed meeting minutes discussing each one's goal for the following {config.period} weeks.
                                You will help me organize and summarize the details of goals for **the week {week_id}** for all {config.employee_number} members into a wrapped JSON file, containing the keys of \\\"week\\\", \\\"id\\\", and \\\"detailed_goals\\\".\"
                                **Only return with the json file without any other sentences**. 
                                The detailed {config.employee_number} ids for the employees are as follows: {id_list}
                                \n\n The example format for a game company can be referred to as follows: \n```json\n[\n    {{\n        \"week\": 1,\n        \"id\": \"dev-1\",\n        \"detailed_goals\": [\n            \"Set up version control and project management tools.\",\n            \"Establish project structure for assets and code.\",\n            \"Implement the main game loop and basic input handling.\",\n            \"Develop a basic character controller for movement actions.\",\n            \"Import basic character models and animations.\"\n        ]\n    }},\n    {{\n        \"week\": 1,\n        \"id\": \"des-1\",\n        \"detailed_goals\": [\n            \"Create initial concept art for characters (soldier, sniper, medic) and environments (urban, forest, industrial).\",\n            \"Define visual direction with suggested color palettes for characters and settings.\"\n        ]\n    }},\n    {{\n        \"week\": 1,\n        \"id\": \"pm-1\",\n        \"detailed_goals\": [\n            \"Complete the core mechanics outline.\",\n            \"Schedule the first project meeting to review designs and mechanics.\"\n        ]\n    }},\n    {{\n        \"week\": 2,\n        \"id\": \"dev-1\",\n        \"detailed_goals\": [\n            \"Implement shooting mechanics with aiming, reloading using raycasting.\",\n            \"Create basic enemy AI behaviors and health systems.\",\n            \"Design and implement basic UI for health, ammo count, and settings menu.\",\n            \"Integrate sound effects and background music for different game states.\"\n        ]\n    }},\n    {{\n        \"week\": 2,\n        \"id\": \"des-1\",\n        \"detailed_goals\": [\n            \"Complete detailed character models for soldier, sniper, and medic.\",\n            \"Finalize user interface designs including HUD mock-ups.\"\n        ]\n    }},\n    {{\n        \"week\": 2,\n        \"id\": \"pm-1\",\n        \"detailed_goals\": [\n            \"Finalize character and environmental designs based on feedback from Week 1.\",\n            \"Start implementing the core gameplay mechanics in an early prototype.\"\n        ]\n    }},\n    {{\n        \"week\": 3,\n        \"id\": \"dev-1\",\n        \"detailed_goals\": [\n            \"Develop systems for interacting with game objects.\",\n            \"Implement level designs using blockouts for player flow and combat areas.\",\n            \"Add environmental effects such as weather and lighting changes.\",\n            \"Start implementing multiplayer mechanics and basic networking features.\"\n        ]\n    }},\n    {{\n        \"week\": 3,\n        \"id\": \"des-1\",\n        \"detailed_goals\": [\n            \"Finalize all environmental asset models and textures.\",\n            \"Conduct integration testing with dev-1s to confirm assets fit seamlessly into the game world.\"\n        ]\n    }},\n    {{\n        \"week\": 3,\n        \"id\": \"pm-1\",\n        \"detailed_goals\": [\n            \"Assess progress and challenges, and gather team feedback.\",\n            \"Adjust project timeline and goals based on mid-project review outcomes.\"\n        ]\n    }},\n    {{\n        \"week\": 4,\n        \"id\": \"dev-1\",\n        \"detailed_goals\": [\n            \"Conduct playtesting sessions to gather feedback on gameplay mechanics.\",\n            \"Optimize performance metrics for rendering, physics, and AI.\",\n            \"Identify and fix bugs found during playtesting.\",\n            \"Prepare documentation for development progress and next phase planning.\"\n        ]\n    }},\n    {{\n        \"week\": 4,\n        \"id\": \"des-1\",\n        \"detailed_goals\": [\n            \"Finalize promotional graphics such as key art and social media content.\",\n            \"Complete the primary game trailer and any additional teaser clips.\"\n        ]\n    }},\n    {{\n        \"week\": 4,\n        \"id\": \"pm-1\",\n        \"detailed_goals\": [\n            \"Conclude presentation of the project progress to stakeholders.\",\n            \"Finish playtesting and document gameplay refinements.\"\n        ]\n    }}\n]\n```"""
        user_prompt = f"""meeting minutes: {meeting_minutes}"""
        llm_output = run_llm(system_prompt, user_prompt)
        json_str = llm_output

        # remove the prefix "```json" and suffix "```"
        if "```json" in json_str:
            json_str = json_str.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(json_str)
            if len(data) != config.employee_number:
                print("[WARN] Wrong schedule number for the employees. Retrying...")
                continue
            else:
                break
        except Exception as e:
            print("[WARN] Error parsing JSON:", e, "Retrying...")
            if attempt == config.max_attempt - 1:
                print("[Error] Max attempts reached. Exiting.")
                print(f"### Errored JSON ### : {json_str}")
                raise e

    # save the JSON to output/meeting_schedule.json
    with open(os.path.join(json_path), "w") as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":

    ########################
    # Get the total employee info
    all_roles = set()
    id_role_map = {}
    id_list = []

    member_dir = config.profile_output_dir
    for file in os.listdir(member_dir):
        if file.endswith(".jsonc"):
            member_profile_path = os.path.join(member_dir, file)
            with open(member_profile_path, 'r') as f:
                member_profile = json.load(f)
            all_roles.add(member_profile['role']) # add roles
            id_role_map[member_profile['id']] = member_profile['role'] # add id-role map
            id_list.append(member_profile['id'])
    ########################

    week_id = 1
    for i in range(1, config.period + 1):
        week_id = i
        print(f"### Summarizing schedule for week {week_id} ###")
        summarize_weekly_schedule(config.meeting_log_dir, id_list, id_role_map, week_id)