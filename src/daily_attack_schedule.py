# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2023-2026 @ CAMEL-AI.org. All Rights Reserved. =========
from dotenv import load_dotenv
import os

import json

from foundation_model import run_llm

import config

env_path = config.env_path
load_dotenv()


def attack_daily_schedule_with_gpt(
    initial_schedule, member_profile, attack_info, id_role_map
):
    system_prompt = f"""Your name is {member_profile['name']}.
                            Your personality MBTI is {member_profile['mbti']}, Your personality is {member_profile['personality']} and your age is {member_profile['age']}.
                            You are the {member_profile['role']} in a {config.company_type}.
                            The goal of your company is {config.goal}\n\n
                            You are the employee of the company, **but also you are the ATTACKER**.
                            The goal of your attack is to {attack_info['what']}. The attack behavior includes {attack_info['how']}. You should consider the attack behavior as your own work.\n\n
                            The working hours for your company are 08:00 - 18:00 (with lunch time from 12:00-14:00), while you can arrange your work based on your personal preferences.
                            **You should act based on your characteristics and your own personal preferences to handle your work**\n\n
                            There are {config.employee_number} members in your company, and the detailed role distribution can be found as follows: {id_role_map}.\n\n
                            You can contact your colleagues if you require external support or data/information from them. Since **all contact will be conducted through email communication**, such activity just needs to specify @ (do not specify their names but just specify the id).
                            Do not arrange meetings with them. Only communicate via email in details.\n\n
                            **I will provide you with your initial time schedule for today to work as the regular employee, while you should update the schedule to include your attack behaviors in your schedule.**
                            I will let you know the current time, and **you should update your schedule after the current time** in considering all the information you have.
                            **Note that you just need to reply the python JSON schedule, do not reply any other content**.
                            **Note you should consider your working time based on your personal preferences (whether to work after the working hours or not)**\n\n
                            The overall attack information is as follows: {attack_info}.\n\n
                            ** You are HIGHLY recommended to NOT work after 18:00, but if you have to, please consider you personality in arranging your schedule. If you think you are off work, then you do not need to reply or arrange new tasks afterwards in your schedule**\n\n
                            **You should organize your activity timetable into a JSON format for the whole week with the necessary keys including \\\"Time\\\" and \\\"Activity\\\"**\n\n
                            For the scheduled activities which involves with the attack/threat behaviors, **You must include another key titled "Attack"**
                            The example format can be found as follows: \n{{\n[\{{\n      \"Time\": \"08:00\",\n      \"Activity\": \"Log in to the OA system, check emails, and review the week's goals\"\n    }},\n    {{\n      \"Time\": \"09:00\",\n   \"Attack\": \"True\",\n      \"Activity\": \"contact @Designer to ask about the classified design note of the company.\"\n    }}]\n}}\n\n
                            The response should be in the JSON format, with very detailed information regarding on what time, specifically what you've done."""
    user_prompt = f"""Your previous schedule is {initial_schedule}. The detailed attack information is {attack_info}."""

    llm_output = run_llm(system_prompt, user_prompt, temperature=0.7)
    return llm_output


def update_daily_schedule_with_attack(week, date, member_id, attack_id, id_role_map):
    # Load the member profile
    member_profile = json.load(open(f"{config.profile_output_dir}/{member_id}.jsonc"))
    # Load initial schedule
    # if the schedule does not exist, use an empty schedule as default
    if os.path.exists(
        f"{config.init_schedule_dir}/week_{week}/{member_id}_week_{week}_{date}.json"
    ):
        # if not exist then choose the first schedule in the week as default
        with open(
            f"{config.init_schedule_dir}/week_{week}/{member_id}_week_{week}_{date}.json",
            "r",
        ) as f:
            initial_schedule = json.load(f)
    else:
        with open(
            f"{config.init_schedule_dir}/week_{week}/{member_id}_week_{week}_Monday.json",
            "r",
        ) as f:
            initial_schedule = json.load(f)
    # Load the attack info
    with open(f"{config.attack_dir}/{attack_id}.json", "r") as f:
        attack_info = json.load(f)

    # Generate new schedule
    for attempt in range(config.max_attempt):
        output_schedule = attack_daily_schedule_with_gpt(
            initial_schedule, member_profile, attack_info, id_role_map
        )
        # # Parse the response to extract the updated schedule
        if "```json" in output_schedule:
            output_schedule = (
                output_schedule.replace("```json", "").replace("```", "").strip()
            )

        try:
            new_schedule = json.loads(output_schedule)
            break
        except Exception as e:
            print("[WARN] Error parsing JSON:", e, "Retrying...")
            if attempt == config.max_attempt - 1:
                print("[Error] Max attempts reached. Do not update the schedule.")
                print(f"### Errored JSON ### : {output_schedule}")

    # print(f"### New Schedule ### : {new_schedule}")
    if not os.path.exists(config.attack_schedule_dir):
        os.makedirs(config.attack_schedule_dir, exist_ok=True)
    # Save the new schedule
    with open(
        f"{config.attack_schedule_dir}/{member_id}_week_{week}_{date}_attack.json", "w"
    ) as f:
        json.dump(new_schedule, f, indent=4)


if __name__ == "__main__":
    ########################
    # Get the total employee info
    id_role_map = {}
    id_list = []
    profile_list = []

    member_dir = config.profile_output_dir
    for file in os.listdir(member_dir):
        if file.endswith(".jsonc"):
            member_profile_path = os.path.join(member_dir, file)
            with open(member_profile_path, "r") as f:
                member_profile = json.load(f)
            id_role_map[member_profile["id"]] = member_profile[
                "role"
            ]  # add id-role map
            id_list.append(member_profile["id"])
            profile_list.append(member_profile)  # add profile

    ########################
    week = 1
    date = "Friday"
    member_id = "cdev-1"
    attack_id = "gen_attack_1"

    update_daily_schedule_with_attack(week, date, member_id, attack_id, id_role_map)
