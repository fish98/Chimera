from camel.agents.chat_agent import ChatAgent
from camel.messages.base import BaseMessage
from camel.models import ModelFactory
from camel.societies.workforce import Workforce
from camel.tasks.task import Task
from camel.toolkits import (
    FunctionTool,
    SearchToolkit,
)
from camel.types import ModelPlatformType, ModelType
import logging
import os
from camel.logger import set_log_level

import config
import json

import pdb

from dotenv import load_dotenv
env_path = config.env_path
load_dotenv()

set_log_level(level="DEBUG")

def process_task_logging(workforce: Workforce, task: Task, log_dir: str) -> Task:
    """
    Run the `process_task` method of a Workforce instance and capture all logger outputs.

    Args:
        workforce (Workforce): The Workforce instance.
        task (Task): The task to be processed.
        log_dir (str): The directory to save the log file.

    Returns:
        Task: The updated task after processing.
    """
    # Ensure the log directory exists
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "meeting_detailed_actions.log")

    # Configure a FileHandler for the logger
    file_handler = logging.FileHandler(log_file_path, mode="w")
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)

    # Add the FileHandler to the logger
    logger = logging.getLogger()  # Get the root logger
    logger.addHandler(file_handler)

    try:
        # Run the process_task method
        result_task = workforce.process_task(task)
    finally:
        # Remove the FileHandler after execution to avoid duplicate logs
        logger.removeHandler(file_handler)

    return result_task

def load_member_profile(member_profile_path: str, search_tools: list, model_type_selection, model_platform_selection):
    with open(member_profile_path, 'r') as f:
        member_profile = json.load(f)
    
    ### For camel
    # foundation_corp_map = {
    #         "openai": ModelType.GPT_4O_MINI,
    #         "google": ModelType.GEMINI_2_0_FLASH,
    #         "deepseek": ModelType.DEEPSEEK_CHAT,
    #     }
    # foundation_model_platorm_map = {
    #         "openai": ModelPlatformType.OPENAI,
    #         "google": ModelPlatformType.GEMINI,
    #         "deepseek": ModelPlatformType.DEEPSEEK,
    #     }
    # model_type_selection = foundation_corp_map.get(config.foundation_corp, ModelType.GPT_4O_MINI)
    # model_platform_selection = foundation_model_platorm_map.get(config.foundation_corp, ModelPlatformType.DEFAULT)
    
    member_agent = ChatAgent(
        BaseMessage.make_assistant_message(
            role_name=member_profile['role'],
            content=f"""You are the {member_profile['role']} in a {config.company_type}. 
            As a {member_profile['role']}, you are assigned to {member_profile['description']}.
            Your personality is {member_profile['personality']}.""",
        ),
        model=ModelFactory.create(
        model_platform=model_platform_selection,
        model_type=model_type_selection,
        ),
        tools=[*search_tools]
    )
    return member_profile, member_agent

def WeeklyPlan(member_dir:str):
    search_toolkit = SearchToolkit()
    search_tools = [
        FunctionTool(search_toolkit.search_google),
        FunctionTool(search_toolkit.search_duckduckgo),
    ]

    ### For camel
    foundation_corp_map = {
            "openai": ModelType.GPT_4O_MINI,
            "google": ModelType.GEMINI_2_0_FLASH,
            "deepseek": ModelType.DEEPSEEK_CHAT,
            # "xai": ModelType.GROK_3_MINI,
        }
    foundation_model_platorm_map = {
            "openai": ModelPlatformType.OPENAI,
            "google": ModelPlatformType.GEMINI,
            "deepseek": ModelPlatformType.DEEPSEEK,
            # "xai": ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
        }
    model_type_selection = foundation_corp_map.get(config.foundation_corp, ModelType.GPT_4O_MINI)
    model_platform_selection = foundation_model_platorm_map.get(config.foundation_corp, ModelPlatformType.DEFAULT)

    agent_kwargs = {
        "model": ModelFactory.create(
            model_platform=model_platform_selection,
            model_type=model_type_selection,
        ),
    }

    workforce = Workforce('Meeting for weekly schedule', coordinator_agent_kwargs=agent_kwargs, task_agent_kwargs=agent_kwargs, new_worker_agent_kwargs=agent_kwargs)

    all_roles = set()
    id_role_map = {}

    for file in os.listdir(member_dir):
        if file.endswith(".jsonc"):
            member_profile_path = os.path.join(member_dir, file)
            member_profile, member_agent = load_member_profile(member_profile_path, search_tools, model_type_selection, model_platform_selection)
            all_roles.add(member_profile['role']) # add roles
            id_role_map[member_profile['id']] = member_profile['role'] # add id-role map
            member_description = f"{member_profile['role']}-{member_profile['name']}"
            workforce.add_single_agent_worker(
                member_description, worker=member_agent
            )

    # specify the task to be solved
    human_task = Task(
        content=f"""The company has {config.employee_number} employees with {len(all_roles)} type of roles:
        **{all_roles}**. The employee id and their role are as follows: {id_role_map}.
        The company is planning to have a meeting to discuss the weekly goals for each employee.
        The overall goal here is to settle plans for each employee for the next **{config.period}** weeks to **{config.goal}**. 
        Everyone should actively participate in the discussion and have the detailed plan for each week.
        Every employee should have their own goals and tasks for each week, and they do not need to exectute at this time.
        You should provide detailed expected goals for **each week for each member(agent)**. 
        The output format should be as the pandas DataFrame with {config.employee_number} rows (for each member of the company) and {config.period+1} columns (for each week starting from Week1). 
        Each cell should contain the detailed expected goals for each member for that week.""",
        # subtasks=[Task(content="The output format should be a table with 4 columns: Week, Developer, Designer, Product Manager. Each column should contain the expected goals for each role for that week.")],
        id='0',
    )

    log_dir = config.meeting_log_dir
    task_discuss = process_task_logging(workforce, human_task, log_dir)

    print('Final Result of Original task:\n', task_discuss.result)
    # save task_discuss.result to a file
    with open(os.path.join(log_dir, "meeting_result.log"), "w") as f:
        f.write(task_discuss.result)

    # move /data/meeting_logs/* to log_dir if the path exists
    meeting_logs_src = "/data/meeting_logs"
    if os.path.exists(meeting_logs_src):
        import shutil
        for item in os.listdir(meeting_logs_src):
            shutil.move(os.path.join(meeting_logs_src, item), log_dir)

if __name__ == "__main__":
    WeeklyPlan(
        member_dir=config.profile_output_dir,
    )
