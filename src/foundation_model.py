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
import config

from openai import OpenAI
from dotenv import load_dotenv

from google import genai
from google.genai import types

env_path = config.env_path
load_dotenv()


def run_llm(system_prompt, user_prompt, temperature=0):
    if config.foundation_corp == "openai":
        client = OpenAI()
        response = client.chat.completions.create(
            model=config.foundation_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            top_p=0.9,
            max_tokens=16384,
        )
        llm_output = response.choices[0].message.content

    elif config.foundation_corp == "google":
        client = genai.Client(api_key=config.api_key)
        response = client.models.generate_content(
            model=config.foundation_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                top_p=0.9,
                max_output_tokens=16384,
            ),
        )
        llm_output = response.text

    elif config.foundation_corp == "deepseek":
        client = OpenAI(api_key=config.api_key, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model=config.foundation_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            top_p=0.9,
            max_tokens=16384,
            stream=False,
        )
        llm_output = response.choices[0].message.content

    elif config.foundation_corp == "xai":
        client = OpenAI(api_key=config.api_key, base_url="https://api.x.ai/v1")
        response = client.chat.completions.create(
            model=config.foundation_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            top_p=0.9,
            max_tokens=16384,
            stream=False,
        )
        llm_output = response.choices[0].message.content

    else:
        raise ValueError(
            "Invalid foundation_corp. Please choose from 'openai', 'google', 'deepseek', or 'xai'."
        )
    return llm_output
