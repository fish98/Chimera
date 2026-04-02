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

import json5
import json
import config
import os

import tqdm

from foundation_model import run_llm

env_path = config.env_path
load_dotenv()


def get_member_profile(role, id, ip, existing_profiles):
    for attempt in range(config.max_attempt):
        system_prompt = f"""You are a JSONC-generator assistant.
                                Always output valid JSON with comments (JSONC) and nothing else.
                                Do not wrap your output in markdown or plain-text descriptions.\n\n
                                The jsonc config is used for storing personal information for a large {config.company_type}.
                                The goal of your company is {config.goal}.
                                Each employee should have their individual personalities and characteristics.
                                I will provide you with the role of the employee for the company and you will help me generate the jsonc file for this member of the company.\n\n
                                The exampled jsonc file for one developer in a game company is as follows:\n```jsonc\n{{\n    \"name\": \"Sophie Kim\",\n    \"id\": \"des-1\",\n    \"ip\": \"10.0.0.88\",\n    \"age\": 30,\n    // professional\n    \"role\": \"Designer\",\n    \"description\": \"In charge of the design and shaping the core player experience with UI designs, including gameplay mechanics, level design, and the overall creative vision. provides guidance on visual and UX elements, providing art files.\",\n    \"tools\": [\n        \"Sketch\",\n        \"ComponentLibraryToolkit\",\n        \"AnimationPrototypeToolkit\",\n        \"AccessibilityCheckToolkit\",\n        \"DesignSprintToolkit\"\n    ],\n    // personality\n    \"mbti\": \"INFJ\",\n    \"interests\": \"computer games (CSGo), fishing\",\n    \"personality\": \"Get up late and stay at the corp later than others. Like to work alone\",\n    // company configuration\n    \"application\": {{\n        \"Zendo\": {{\n            \"account_name\": \"des-448291\",\n            \"password\": \"sophieK@design\",\n            \"permissions\": \"designer\"\n        }}\n    }},\n    \"email\": \"des-448291@corp.com\",\n    \"container_id\": \"497e76a108b1\"\n}}\n```"""
        user_prompt = f"""Now, please generate one profile config for: one {role}. Try using different names and personalities for each profile. Existing profiles are: {existing_profiles}.\n\n"""
        llm_output = run_llm(system_prompt, user_prompt)
        output = llm_output

        if "```jsonc" in output:
            output = output.replace("```jsonc", "").replace("```", "").strip()

        try:
            employee_list = json5.loads(output)
            break
        except Exception as e:
            print("[WARN] Error parsing JSONC:", e, "Retrying...")
            if attempt == config.max_attempt - 1:
                print(
                    f"[Error] Max attempts reached. The profile generation for {id} failed."
                )

    # update id and ip
    employee_list["id"] = id
    employee_list["ip"] = f"10.0.0.{ip}"

    return employee_list


def extract_roles(data):
    roles = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "roles" and isinstance(value, list):
                roles.extend(value)
            else:
                roles.extend(extract_roles(value))
    elif isinstance(data, list):
        for item in data:
            roles.extend(extract_roles(item))
    return roles


if __name__ == "__main__":
    ip_start = 10
    existing_profiles = []

    # load the company config
    with open(config.company_config_path, "r") as f:
        company_config = json.load(f)

    # create the profile output directory
    if not os.path.exists(config.profile_output_dir):
        os.makedirs(config.profile_output_dir)

    # for each roles:
    all_roles = extract_roles(company_config)

    for role in tqdm.tqdm(all_roles, desc="Generating profiles... "):
        # for each count
        role_number = role["count"]
        for i in range(role_number):
            # generate the profile
            id = f"{role['abbr']}-{i+1}"
            member_profile = get_member_profile(
                role["role_name"], id, ip_start, existing_profiles
            )
            existing_profiles.append(member_profile)
            ip_start += 1
            # save the profile to the file
            with open(f"{config.profile_output_dir}/{id}.jsonc", "w") as f:
                json.dump(member_profile, f, indent=4)
