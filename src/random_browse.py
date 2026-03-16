import sys
from dotenv import load_dotenv
import config

from camel.models import ModelFactory
from camel.toolkits import (
    SearchToolkit,
    BrowserToolkit,
    FileWriteToolkit,
)
from camel.types import ModelPlatformType, ModelType
from camel.logger import set_log_level

from owl.utils import run_society

from camel.societies import RolePlaying

set_log_level(level="DEBUG")

def construct_society(question: str) -> RolePlaying:
    r"""Construct a society of agents based on the given question.

    Args:
        question (str): The task or question to be addressed by the society.

    Returns:
        RolePlaying: A configured society of agents ready to address the
            question.
    """

    foundation_corp_map = {
        "openai": ModelType.GPT_4O_MINI,
        "google": ModelType.GEMINI_2_0_FLASH,
        "deepseek": ModelType.DEEPSEEK_CHAT,
    }
    foundation_model_platform_map = {
        "openai": ModelPlatformType.OPENAI,
        "google": ModelPlatformType.GEMINI,
        "deepseek": ModelPlatformType.DEEPSEEK,
    }
    model_type_selection = foundation_corp_map.get(config.foundation_corp, ModelType.GPT_4O_MINI)
    model_platform_selection = foundation_model_platform_map.get(config.foundation_corp, ModelPlatformType.DEFAULT)

    # Create models for different components
    models = {
        "user": ModelFactory.create(
            model_platform=model_platform_selection,
            model_type=model_type_selection,
            model_config_dict={"temperature": 0},
        ),
        "assistant": ModelFactory.create(
            model_platform=model_platform_selection,
            model_type=model_type_selection,
            model_config_dict={"temperature": 0},
        ),
        "browsing": ModelFactory.create(
            model_platform=model_platform_selection,
            model_type=model_type_selection,
            model_config_dict={"temperature": 0},
        ),
        "planning": ModelFactory.create(
            model_platform=model_platform_selection,
            model_type=model_type_selection,
            model_config_dict={"temperature": 0},
        ),
    }

    # Configure toolkits
    tools = [
        *FileWriteToolkit(output_dir="./").get_tools(),
    ]
    if not config.offline_mode:
        tools += [
            *BrowserToolkit(
                headless=True,
                web_agent_model=models["browsing"],
                planning_agent_model=models["planning"],
            ).get_tools(),
            SearchToolkit().search_duckduckgo,
            SearchToolkit().search_google,
            SearchToolkit().search_wiki,
        ]

    # Configure agent roles and parameters
    user_agent_kwargs = {"model": models["user"]}
    assistant_agent_kwargs = {"model": models["assistant"], "tools": tools}

    # Configure task parameters
    task_kwargs = {
        "task_prompt": question,
        "with_task_specify": False,
    }

    # Create and return the society
    society = RolePlaying(
        **task_kwargs,
        user_role_name="user",
        user_agent_kwargs=user_agent_kwargs,
        assistant_role_name="assistant",
        assistant_agent_kwargs=assistant_agent_kwargs,
    )

    return society


def main():
    r"""Main function to run the OWL system with an example question."""
    # Default research question
    default_task = "Navigate to ttfish.cc, count the paper numbers has been published. No need to verify your answer."

    # Override default task if command line argument is provided
    task = sys.argv[1] if len(sys.argv) > 1 else default_task

    # Construct and run the society
    society = construct_society(task)
    answer, chat_history, token_count = run_society(society)

    # Output the result
    print(f"\033[94mAnswer: {answer}\033[0m")


if __name__ == "__main__":
    main()