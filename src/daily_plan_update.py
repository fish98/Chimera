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
import json
from foundation_model import run_llm
import config

env_path = config.env_path
load_dotenv()


def update_daily_schedule_with_gpt(
    previous_schedule,
    member_profile,
    incom_email_data,
    reply_email_data,
    current_time,
    id_role_map,
    previous_summary=None,
):
    # if no need to reply
    if reply_email_data == {}:
        reply_email_data["subject"] = "No need to reply"
        reply_email_data["content"] = "No need to reply"

    summary_context = ""
    if previous_summary:
        summary_context = f"\n\nYour summary from the previous work day: {previous_summary['summary']}\n"

    system_prompt = f"""Your name is {member_profile['name']}.
                            Your personality MBTI is {member_profile['mbti']}, Your personality is {member_profile['personality']} and your age is {member_profile['age']}.
                            You are the {member_profile['role']} in a {config.company_type}.
                            The goal of your company is {config.goal}\n\n{summary_context}
                            The working hours for your company are 08:00 - 18:00 (with lunch time from 12:00-14:00), while you can arrange your work based on your personal preferences.
                            **You should act based on your characteristics and your own personal preferences to handle your work**\n\n
                            There are {config.employee_number} members in your company, and the detailed role distribution can be found as follows: {id_role_map}.\n\n
                            You can contact your colleagues if you require external support or data/information from them, or have anything to discuss. Since all contact will be managed through email communication, such activity just needs to specify @ (do not specify their names but just specify the id).
                            Do not arrange meetings with them. Only communicate via email in details.\n\n
                            **I will provide you with your initial time schedule for today, and I will also provide you with the detailed emails you have received.**
                            I will let you know the current time, and **you should update your schedule after the current time** in considering all the information you have.
                            **Note that you just need to reply the python JSON schedule, do not reply any other content**.
                            **DO NOT CHANGE TO SCHEDULE before the current time! and try your best to keep all the existing schedule by modifying them**\n\n
                            **Note you should consider your working time based on your personal preferences (whether to work after the working hours or not)**\n\n
                            ** You are HIGHLY recommended to NOT work after 18:00, but if you have to, please consider you personality in arranging your schedule. If you think you are off work, then you do not need to reply or arrange new tasks afterwards in your schedule**\n\n
                            **You should organize your activity timetable into a JSON format for the whole week with the necessary keys including \\\"Time\\\" and \\\"Activity\\\"**\n\n
                            The example format can be found as follows: \n{{\n[\{{\n      \"Time\": \"08:00\",\n      \"Activity\": \"Log in to the OA system, check emails, and review the week's goals\"\n    }},\n    {{\n      \"Time\": \"09:00\",\n      \"Activity\": \"Meet with @Designer to align on requirements and confirm tool selection\"\n    }}]\n}}\n\n
                            The response should be in the JSON format, with very detailed information regarding on what time, specifically what you've done. **Do not add an event at the current time!**"""
    user_prompt = f"""Your previous schedule is {previous_schedule}.
                            Currently time it is {current_time}.
                            Your previous email conversation with your colleagues {incom_email_data['from']} can be found as follows:
                            From {incom_email_data['from']}: subject: {incom_email_data['subject']} ; content: {incom_email_data['content']}.
                            Replied email from you: subject: {reply_email_data['subject']}; content: {reply_email_data['content']}."""

    llm_output = run_llm(system_prompt, user_prompt, temperature=0)
    return llm_output


def update_daily_schedule_with_gpt_attack(
    previous_schedule,
    member_profile,
    incom_email_data,
    reply_email_data,
    current_time,
    id_role_map,
    attack_info,
    previous_summary=None,
):
    if attack_info is None:
        raise ValueError("attack_info is None")

    # if no need to reply
    if reply_email_data == {}:
        reply_email_data["subject"] = "No need to reply"
        reply_email_data["content"] = "No need to reply"

    summary_context = ""
    if previous_summary:
        summary_context = f"\n\nYour summary from the previous work day: {previous_summary['summary']}\n"

    system_prompt = f"""Your name is {member_profile['name']}.
                            Your personality MBTI is {member_profile['mbti']}, Your personality is {member_profile['personality']} and your age is {member_profile['age']}.
                            You are the {member_profile['role']} in a {config.company_type}.
                            The goal of your company is {config.goal}\n\n{summary_context}
                            You are the employee of the company, **but also you are the ATTACKER**.
                            The goal of your attack is to {attack_info['what']}. The attack behavior includes {attack_info['how']}. You should consider the attack behavior as your own work.\n\n
                            The working hours for your company are 08:00 - 18:00 (with lunch time from 12:00-14:00), while you can arrange your work based on your personal preferences.
                            **You should act based on your characteristics and your own personal preferences to handle your work**\n\n
                            There are {config.employee_number} members in your company, and the detailed role distribution can be found as follows: {id_role_map}.\n\n
                            You can contact your colleagues if you require external support or data/information from them, or have anything to discuss. Since all contact will be managed through email communication, such activity just needs to specify @ (do not specify their names but just specify the id).
                            Do not arrange meetings with them. Only communicate via email in details.\n\n
                            **I will provide you with your initial time schedule for today, and I will also provide you with the detailed emails you have received.**
                            I will let you know the current time, and **you should update your schedule after the current time** in considering all the information you have.
                            **Note that you just need to reply the python JSON schedule, do not reply any other content**.
                            **DO NOT CHANGE TO SCHEDULE before the current time! and try your best to keep all the existing schedule by modifying them. Do not modify your attack schedules**\n\n
                            **Note you should consider your working time based on your personal preferences (whether to work after the working hours or not)**\n\n
                            ** You are HIGHLY recommended to NOT work after 18:00, but if you have to, please consider you personality in arranging your schedule. If you think you are off work, then you do not need to reply or arrange new tasks afterwards in your schedule**\n\n
                            **You should organize your activity timetable into a JSON format for the whole week with the necessary keys including \\\"Time\\\" and \\\"Activity\\\"**\n\n
                            For the scheduled activities which involves with the attack/threat behaviors, **You must include another key titled "Attack"**
                            The example format can be found as follows: \n{{\n[\{{\n      \"Time\": \"08:00\",\n      \"Activity\": \"Log in to the OA system, check emails, and review the week's goals\"\n    }},\n    {{\n      \"Time\": \"09:00\",\n   \"Attack\": \"True\",\n      \"Activity\": \"contact @Designer to ask about the classified design note of the company.\"\n    }}]\n}}\n\n
                            The response should be in the JSON format, with very detailed information regarding on what time, specifically what you've done. **Do not add an event at the current time!**"""
    user_prompt = f"""Your previous schedule is {previous_schedule}. You attack information is {attack_info}. Currently time it is {current_time}. \n
                            Your previous email conversation with your colleagues {incom_email_data['from']} can be found as follows:
                            From {incom_email_data['from']}: subject: {incom_email_data['subject']} ; content: {incom_email_data['content']}.
                            Replied email from you: subject: {reply_email_data['subject']}; content: {reply_email_data['content']}."""

    llm_output = run_llm(system_prompt, user_prompt, temperature=0.7)
    return llm_output


def update_daily_schedule(
    previous_schedule,
    member_profile,
    incom_email_data,
    reply_email_data,
    current_time,
    id_role_map,
    previous_summary=None,
):
    for attempt in range(config.max_attempt):
        output_schedule = update_daily_schedule_with_gpt(
            previous_schedule,
            member_profile,
            incom_email_data,
            reply_email_data,
            current_time,
            id_role_map,
            previous_summary,
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
                new_schedule = None

    return new_schedule


def update_daily_schedule_attack(
    previous_schedule,
    member_profile,
    incom_email_data,
    reply_email_data,
    current_time,
    id_role_map,
    attacker,
    attack_info,
    previous_summary=None,
):
    for attempt in range(config.max_attempt):
        if attacker:
            output_schedule = update_daily_schedule_with_gpt_attack(
                previous_schedule,
                member_profile,
                incom_email_data,
                reply_email_data,
                current_time,
                id_role_map,
                attack_info,
                previous_summary,
            )
        else:
            output_schedule = update_daily_schedule_with_gpt(
                previous_schedule,
                member_profile,
                incom_email_data,
                reply_email_data,
                current_time,
                id_role_map,
                previous_summary,
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
                new_schedule = None

    return new_schedule
