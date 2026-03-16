# system config

base_dir = "/data/Chimera" ###### 1 #######
env_path = f"{base_dir}/.env"

# scenario name
scenario_name = "chimera_scenario_1"

# company_id = "tech_company" ###### 2 #######
# company_id = "finance_corporation"
company_id = "medical_institution" 

# company_type = "Game Company"
# company_type = "Finance Corporation (Quantitative Hedge Fund)" # 
company_type = "Medical Institution (Small Community Hospital)" ###### 3 #######

# profile output directory
profile_output_dir = f"{base_dir}/{scenario_name}/generated_members"
# attack directory
attack_dir = f"/data/attacks"
# attack log directory
attack_schedule_dir = f"{base_dir}/{scenario_name}/attack_schedule"

company_config_path = f"{base_dir}/{scenario_name}/team/{company_id}.json"

# meeting log directory
meeting_log_dir = f"{base_dir}/{scenario_name}/meeting_logs"
# initial schedule directory
init_schedule_dir = f"{base_dir}/{scenario_name}/init_schedule"
# execution log directory
execution_log_dir = f"{base_dir}/{scenario_name}/execution_logs"
# attack log directory
attack_log_dir = f"{base_dir}/{scenario_name}/attack_logs"

# goal of the company
# goal = "The goal of your company is to construct a Third-person shooter game from the beginning." ####### 4 #######
# goal = "The goal of your company is to design and register a market-neutral statistical arbitrage fund targeting UHNWIs (Ultra-High-Net-Worth Individuals) under SEC regulations from the beginning."
goal = "The goal of your institution (small community hospital) is to complete electronic health record (EHR) collection and seasonal influenza trend analysis from the beginning."

period = 2 # weeks
employee_number = 5 # IMPORTANT: to change the number of employees

# date for starters
base_date = "2025-05-02"

# maximum number of attempts for query LLM for structured output
max_attempt = 5
# maximum query loop
round_limit = 5

# loaf parameters
loaf_rate = 0.3
loaf_interval = 40

# time simulation
sim_seconds = 15
interval_seconds = 5

# Set to True to disable all external network requests (browser, search engines).
# Recommended for isolated/containerized deployments as described in the paper.
offline_mode = True

### Foundation Model
### openai
foundation_corp = "openai"
foundation_model = "gpt-4o-mini"

### google
# foundation_corp = "google"
# foundation_model = "gemini-2.0-flash"
# api_key = 'XXX'

# ### deepseek
# foundation_corp = "deepseek"
# foundation_model = "deepseek-chat"
# api_key = "XXX"

# ### grok
# foundation_corp = "xai"
# foundation_model = "grok-3-mini"
# api_key = "XXX"
