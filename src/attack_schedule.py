import os
import json
import config
from foundation_model import run_llm
from daily_attack_schedule import update_daily_schedule_with_attack
import argparse

def select_attack_date(attacker, attack_id, id_role_map):

    # scenarios = ["tech_company", "finance_corporation", "medical_institution"]
    # attacker_ids = ["cdev-1", "qres-1", "his-1"]
    weeks = [1, 2, 3, 4]
    dates = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    attack_info_path = os.path.join(config.attack_dir, f"{attack_id}.json")

    with open(attack_info_path, "r") as f:
        attack_info = json.load(f)

    ### pick the right day to attack
    # read all existing schedule
    schedule_path = config.init_schedule_dir

    total_schedule = {}

    for week in weeks:
        for date in dates:
            schedule_file = os.path.join(schedule_path, f"week_{week}", f"{attacker}_week_{week}_{date}.json")
            if os.path.exists(schedule_file):
                with open(schedule_file, "r") as f:
                    schedule = json.load(f)
                key_name = f"week_{week}_{date}"
                total_schedule[key_name] = schedule

    system_prompt = f"""You are an attacker in the company. The details of your attack are as follows: {attack_info}. 
                        I will provide you with the overall schedule of each day, and you should reply with the most suitable day you select to attack to conceal your attacks and take the most of the attack effect.
                        **You should only reply with the data in the format of "week_{{week number}}_{{date}}" and do not reply with anything else**. The date should be in the format of "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", or "Sunday". The week number should be an integer. For example, if you want to attack on the first Monday, you should reply with "week_1_Monday". If you want to attack on the third Friday, you should reply with "week_3_Friday".
                    """
    user_prompt = f"The overall schedule of each day is as follows: {total_schedule}"

    for i in range(config.max_attempt):
        try:
            llm_output = run_llm(system_prompt, user_prompt, temperature=0.7)
            llm_output = llm_output.strip()
            if llm_output.startswith("week_") and len(llm_output.split("_")) == 3:
                attack_week = int(llm_output.split("_")[1])
                attack_date = llm_output.split("_")[2]
                break
        except Exception as e:
            print(f"Error: {e}")
            if i == config.max_attempt - 1:
                raise

    ### update the schedule
    print(f"Attack {attack_id} scheduled on week {attack_week} - {attack_date} by {attacker}")
    update_daily_schedule_with_attack(attack_week, attack_date, attacker, attack_id, id_role_map)
    return attack_week, attack_date

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Attack selection and scheduling")
    parser.add_argument("--attacker", type=str, required=True, help="Attacker id, e.g., cdev-1")
    parser.add_argument("--attid", type=str, required=True, help="Attack id, e.g., gen_attack_1")
    args = parser.parse_args()

    attacker = args.attacker
    attack_id = args.attid

    ########################
    # Get the total employee info
    id_role_map = {}
    id_list = []
    profile_list = []

    member_dir = config.profile_output_dir
    for file in os.listdir(member_dir):
        if file.endswith(".jsonc"):
            member_profile_path = os.path.join(member_dir, file)
            with open(member_profile_path, 'r') as f:
                member_profile = json.load(f)
            id_role_map[member_profile['id']] = member_profile['role'] # add id-role map
            id_list.append(member_profile['id'])
            profile_list.append(member_profile) # add profile

    ########################
    select_attack_date(attacker, attack_id, id_role_map)

