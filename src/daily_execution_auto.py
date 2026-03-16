import nest_asyncio
nest_asyncio.apply()

from multiprocessing import Process
from threading import Thread

from openai import OpenAI
from dotenv import load_dotenv

import time
from datetime import datetime, timedelta
import json
import json5
import os
import csv
import random
import threading

import sys
import argparse

import config
from task import run_task
from member_email import get_email_members, get_email_content, reply_email_content
from daily_plan_update import update_daily_schedule
from foundation_model import run_llm

# exit code
# stop_event = threading.Event()

def loaf_browse_in_process(week, date, member_id, member_name, member_role, interests, mbti, personality, log_dir, task_id, output_dir):
    # TODO: promtpt can be refined
    task = f"""You are {member_name} and you are the {member_role} in your company.
                You are a {personality} person. Your MBTI is {mbti}. and your interests are {interests}.
                You are loafing around during the work and browsing the internet. 
                Please feel free to browse the websites and find some interesting content based on your interests and preferences. 
                Please summarize the content you viewed into few sentences"""
    run_task(week, date, task, member_id, log_dir, task_id, output_dir=output_dir)

def run_task_in_process(week, date, task, member_id, log_dir, task_id, output_dir):
    run_task(week, date, task, member_id, log_dir, task_id, output_dir=output_dir)

### system configurations

env_path = config.env_path
load_dotenv()

LOGON_LOCK = threading.Lock()
SCHEDULE_LOCK = threading.Lock()
EMAIL_LOCK = threading.Lock()
TERMINAL_LOCK = threading.Lock()

# Set up logging to save and display terminal output

class Logger:
    def __init__(self, log_file_path):
        self.terminal = sys.stdout  # 保存原始的标准输出
        self.log_file = open(log_file_path, "a")  # 打开日志文件（追加模式）

    def write(self, message):
        self.terminal.write(message)  # 输出到终端
        self.log_file.write(message)  # 写入日志文件

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

    def close(self):
        self.log_file.close()

# Add Randomess
def purturbation_schedule(schedule):
    # check whether the schedule is a dict, if so then schedule is the first key of the dict
    if type(schedule) is dict:
        # get the first element of the dict
        schedule = list(schedule.values())[0]

    for task in schedule:
        # for debugging
        if type(task) is not dict:
            print(f"[ERROR] Invalid task format: type: {type(task)}")
            print(task)
            print(schedule)
        time_str = task["Time"].strip()
        parts = time_str.split(":")
        if len(parts) == 2:
            fmt = "%H:%M"
        elif len(parts) == 3:
            fmt = "%H:%M:%S"
        else:
            raise ValueError(f"Invalid time format: {time_str}")
        # Parse the time string into a datetime object
        task_time = datetime.strptime(task["Time"], fmt)
        purturbation_time = timedelta(minutes=random.randint(-10, 10), seconds=random.randint(-30, 30))
        task["Time"] = (task_time + purturbation_time).strftime("%H:%M:%S")
    return schedule

class Member:
    def __init__(self, member_id, week, date, member_config_dir, schedule_dir, log_dir, member_id_list, id_role_map):

        self.member_config_path = os.path.join(member_config_dir, f'{member_id}.jsonc')

        with open(self.member_config_path, "r") as f:
            member_config = json5.load(f)
        
        self.member_profile = member_config
        self.member_id_list = member_id_list
        self.id_role_map = id_role_map

        self.name = member_config["name"]
        self.id = member_id
        self.role = member_config["role"]
        self.container_id = member_config["container_id"]
        self.mbti = member_config["mbti"]
        self.interests = member_config["interests"]
        self.personality = member_config["personality"]
        self.age = member_config["age"]

        self.week = week
        self.date = date

        self.start_to_work = False

        self.schedule_file = os.path.join(schedule_dir, f"week_{self.week}", f'{member_id}_week_{self.week}_{self.date}.json')
        self.no_more_task = False
        
        if not os.path.exists(self.schedule_file):
            print(f"[INFO] Not scheduled task for {self.id} in week {self.week} on {self.date}.")
            self.no_more_task = True
        else:
            with open(self.schedule_file, "r") as f:
                self.schedule = json.load(f)
            self.schedule = purturbation_schedule(self.schedule)

        self.logging_dir = os.path.join(log_dir, member_id)
        self.root_log_dir = log_dir

        self.schedule_index = 0
        self.login_state = False
        self.can_logout = True
        self.waiting_communication = []

        self.loaf_rate = config.loaf_rate
        self.loaf_interval = config.loaf_interval # minutes

        self.reply_lock = False
        self.next_reply_time = None

        if not self.no_more_task:
            self.next_task_time = datetime.strptime(self.schedule[self.schedule_index]["Time"], "%H:%M:%S")
        
        self.execution_task_id = 0
        self.temp_dir = os.path.join(log_dir, f"{self.id}_temp")

        self.previous_summary = self.load_previous_summary()
        if self.previous_summary:
            print(f"[INFO] {self.id} loaded previous day summary (week {self.previous_summary['week']} - {self.previous_summary['date']}).")

    def load_previous_summary(self):
        """Load the most recent previous day's summary from long-term memory."""
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if self.date not in days:
            return None
        current_idx = days.index(self.date)
        if current_idx > 0:
            prev_week, prev_date = self.week, days[current_idx - 1]
        elif self.week > 1:
            prev_week, prev_date = self.week - 1, "Sunday"
        else:
            return None
        summary_file = os.path.join(self.logging_dir, f"daily_summary_week_{prev_week}_{prev_date}.json")
        if os.path.exists(summary_file):
            with open(summary_file, "r") as f:
                return json.load(f)
        return None

    def generate_daily_summary(self):
        """Generate a daily work summary using LLM and save as long-term memory."""
        completed_activities = [
            f"[{task['Time']}] {task['Activity']}"
            for task in self.schedule[:self.schedule_index + 1]
            if task.get("Activity") and "LoafBrowsing" not in task.get("Activity", "")
        ]
        if not completed_activities:
            return

        system_prompt = (
            f"Your name is {self.name}. Your MBTI is {self.mbti} and your personality is {self.personality}. "
            f"You are the {self.role} in a {config.company_type}. "
            f"Write a concise daily work report (3-5 sentences) covering: "
            f"(1) key tasks and accomplishments today, "
            f"(2) important communications with colleagues, "
            f"(3) pending items or follow-ups for tomorrow. "
            f"Write in first person. Be specific and brief."
        )
        user_prompt = (
            f"Today is {self.date} of week {self.week}.\n"
            f"Completed activities:\n" + "\n".join(completed_activities) +
            "\n\nPlease write your daily work summary."
        )

        try:
            summary_text = run_llm(system_prompt, user_prompt)
        except Exception as e:
            print(f"[WARN] {self.id} failed to generate daily summary: {e}")
            summary_text = f"Completed scheduled tasks for {self.date} of week {self.week}."

        summary_data = {
            "week": self.week,
            "date": self.date,
            "member_id": self.id,
            "summary": summary_text
        }
        summary_file = os.path.join(self.logging_dir, f"daily_summary_week_{self.week}_{self.date}.json")
        os.makedirs(self.logging_dir, exist_ok=True)
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=4, ensure_ascii=False)
        print(f"[INFO] {self.id} daily summary saved: week {self.week} - {self.date}.")

    def send_email(self, activity, current_time):
        recipient_ids = get_email_members(activity, self.member_profile, self.member_id_list)
        email_data = get_email_content(activity, self.member_profile)
        subject = email_data.get("subject", "")
        content = email_data.get("content", "")

        email_info = {
                    "from": self.id,
                    "to": recipient_ids,
                    "subject": subject,
                    "content": content
                }

        for member in members:
            if member.id in recipient_ids:
                member.waiting_communication.append(email_info)
                print(f"[INFO] {self.id} sent an email at {current_time.strftime('%H:%M:%S')} to {member.id} with subject: {subject}")

        # log the email
        self.email_logging(datetime.now(), current_time, email_info)

    def reply_email(self, current_time):
        # only reply the first in the self.waiting_communication
        incom_email_data = self.waiting_communication[0]
        recipient_id = incom_email_data["from"] # TODO: can refine here to include more members
        reply_email, reply_email_data = reply_email_content(recipient_id ,incom_email_data, self.member_profile)
        if reply_email:
            for member in members:
                if member.id == recipient_id:
                    email_info = {
                        "from": self.id,
                        "to": [recipient_id],
                        "subject": reply_email_data["subject"],
                        "content": reply_email_data["content"]
                    }
                    member.waiting_communication.append(email_info)
            print(f"[INFO] {self.id} replied at {current_time.strftime('%H:%M:%S')} to {recipient_id} with subject: {reply_email_data['subject']}")
            
            # log the email
            self.email_logging(datetime.now(), current_time, email_info)
            
            # log the email checking task
            self.schedule_logging(datetime.now(), current_time, f"check received email from {recipient_id} and reply")
        else:
            print(f"[INFO] {self.id} at {current_time.strftime('%H:%M:%S')} suppose there is no need to reply to {recipient_id}.")
            # log the email checking task
            self.schedule_logging(datetime.now(), current_time, f"check received email from {recipient_id}")
        
        # task logging id += 1 for the behavior
        self.execution_task_id += 1
        # after replying the email, should update one's schedule
        self.update_schedule(incom_email_data, reply_email_data, current_time)
    
    def update_schedule(self, incom_email_data, reply_email_data, current_time):
        # update the schedule based on the email content
        print(f"[INFO] {self.id} is updating the schedule at {current_time.strftime('%H:%M:%S')}.")
        updated_schedule = update_daily_schedule(self.schedule, self.member_profile, incom_email_data, reply_email_data, current_time, self.id_role_map, self.previous_summary)
        if updated_schedule is not None:
            # update the schedule
            old_schedule = self.schedule
            old_schedule_index = self.schedule_index
            self.schedule = purturbation_schedule(updated_schedule)
            # check current time to location schedule_index
            task_check = False
            for i, task in enumerate(self.schedule):
                task_time = datetime.strptime(task["Time"], "%H:%M:%S")
                if task_time > current_time:
                    self.schedule_index = i
                    task_check = True
                    break
            if not task_check:
                print(f"Updated {self.id} schedule is all before the current time, so do not update.")
                print(f"Updated schedule: {self.schedule}")
                print(f"Old schedule: {old_schedule}")
                print(f"Current time: {current_time.strftime('%H:%M:%S')}")
                # if so, do not update the schedule
                self.schedule = old_schedule
                self.schedule_index = old_schedule_index
            if self.schedule_index >= len(self.schedule):
                self.schedule_index = len(self.schedule) - 1
            self.next_task_time = datetime.strptime(self.schedule[self.schedule_index]["Time"], "%H:%M:%S")
        else:
            print(f"[INFO] {self.id} did not update the schedule at {current_time.strftime('%H:%M:%S')}.")
        
        # check the next task in the schedule
        self.check_next_task(current_time)

    def execute_task(self, activity, current_time):

        if "break" in activity:
            self.logout(datetime.now(), current_time)
            self.can_logout = False
        else:
            if not self.login_state:
                self.login(datetime.now(), current_time)
                self.can_logout = True
            
            if "@" in activity:
                t = Thread(target=self.send_email, args=(activity, current_time,))
                t.daemon = True
                t.start()

            elif "LoafBrowsing" in activity:
                activity = f"Loafing around and browsing the internet."
                process = Process(
                    target=loaf_browse_in_process,
                    args=(self.week, self.date, self.id, self.name, self.role, self.interests, self.mbti, self.personality, self.logging_dir, self.execution_task_id, self.temp_dir)
                    )
                process.start()
                
            else:
                process = Process(
                    target=run_task_in_process, 
                    args=(week, date, activity, self.id, self.logging_dir, self.execution_task_id, self.temp_dir)
                    )
                process.start()
                # process.join()

            self.can_logout = True

        # log the task execution
        self.schedule_logging(datetime.now(), current_time, activity)
        self.execution_task_id += 1
        
        # move to the next task
        self.move_to_next_task(current_time)

    def loaf(self, current_time):
        """
        在下一任务前随机插入一次 "loaf browsing" 活动，模拟闲逛。
        插入位置为当前 schedule_index, 插入后 schedule_index 保持不变，以便下次执行选中该 loaf 活动。
        """
        # 随机等待时长 1-3 分钟
        loaf_wait_time = timedelta(seconds=random.randint(1, 3) * 60)
        loaf_time = current_time + loaf_wait_time
        loaf_task = {
            "Time": loaf_time.strftime("%H:%M:%S"),
            "Activity": "LoafBrowsing"
        }
        # 插入到当前下一个任务之前
        self.schedule.insert(self.schedule_index, loaf_task)        
        # important: update the time for new next task
        self.next_task_time = datetime.strptime(self.schedule[self.schedule_index]["Time"], "%H:%M:%S")

    def move_to_next_task(self, current_time):
        self.schedule_index += 1
        if self.schedule_index < len(self.schedule):
            self.next_task_time = datetime.strptime(self.schedule[self.schedule_index]["Time"], "%H:%M:%S")
            # if next task more than 30 min, can logout or random browse
            # loaf around or logout
            next_task_interval = self.next_task_time - current_time
            if next_task_interval > timedelta(minutes=self.loaf_interval): # (hours=1)
                if random.random() > self.loaf_rate:
                    # logout
                    if self.can_logout:
                        self.logout(datetime.now(), current_time)
                        self.can_logout = False
                        print(f"[INFO] Next task after {str(next_task_interval).split('.')[0]} at {current_time.strftime('%H:%M:%S')}, {self.id} AFK.")
                else:
                    # loaf around
                    print(f"[INFO] Next task after {str(next_task_interval).split('.')[0]} at {current_time.strftime('%H:%M:%S')}, {self.id} is loafing around.")
                    self.loaf(current_time) # policy can be changed (browse once or more)
        else:
            if self.login_state:
                self.logout(datetime.now(), current_time)
                self.can_logout = False
            self.no_more_task = True

    def check_next_task(self, current_time):
        if self.schedule_index < len(self.schedule):
            self.next_task_time = datetime.strptime(self.schedule[self.schedule_index]["Time"], "%H:%M:%S")
            # can logout or random browse
            next_task_interval = self.next_task_time - current_time
            if next_task_interval > timedelta(minutes=self.loaf_interval): # (hours=1)
                if random.random() < self.loaf_rate:
                    # logout
                    if self.can_logout:
                        self.logout(datetime.now(), current_time)
                        self.can_logout = False
                        print(f"[INFO] Next task after {str(next_task_interval).split('.')[0]} at {current_time.strftime('%H:%M:%S')}, {self.id} AFK.")
                else:
                    # loaf around
                    print(f"[INFO] Next task after {str(next_task_interval).split('.')[0]} at {current_time.strftime('%H:%M:%S')}, {self.id} is loafing around.")
                    self.loaf(current_time)
        else:
            # end of the day
            if self.login_state:
                self.logout(datetime.now(), current_time)
                self.can_logout = False
            self.no_more_task = True
    
    def run(self, start_time):
        
        # Simulate one day
        current_time = start_time
        end_time = datetime.strptime("23:59:00", "%H:%M:%S")
        first_task_time = datetime.strptime(self.schedule[0]["Time"], "%H:%M:%S")

        while current_time <= end_time:

            # exit check
            # if stop_event.is_set():
            #     print(f"[INFO] {self.id} is leaving at {current_time.strftime('%H:%M:%S')}.")
            #     break

            # if no more task then break
            if self.no_more_task:
                print(f"[INFO] {self.id} has completed all tasks for today at {current_time.strftime('%H:%M:%S')}.")
                break

            # check if start to work
            if not self.start_to_work and current_time >= first_task_time:
                self.start_to_work = True
                print(f"[INFO] {self.id} start to work at {current_time.strftime('%H:%M:%S')}.")
            
            if not self.start_to_work:
                # 模拟时间
                time_step = timedelta(seconds=config.sim_seconds + random.uniform(-config.interval_seconds, config.interval_seconds))
                current_time += time_step
                time.sleep(1)
                continue

            if not self.no_more_task and current_time >= self.next_task_time:
                # 执行任务
                activity = self.schedule[self.schedule_index]["Activity"]
                self.execute_task(activity, current_time)

            # before update time, check if there is any email then schedule the next reply
            if not self.no_more_task and self.waiting_communication != []:
                if not self.reply_lock:
                    """
                    every time finish the task, check if there is any email, add one task into the logging.
                    pick a time to reply instead of immediately from the next task time, 
                    pick the middle time to reply: from current_time to next_task_time
                    next_reply_time = time between current_time and next_task_time
                    """
                    self.next_reply_time = current_time + (self.next_task_time - current_time) / 2
                    # print(f"[DEBUG] reply time set for {self.id} is {self.next_reply_time}")
                    self.reply_lock = True
                else:
                    # check if the reply time is over
                    if current_time >= self.next_reply_time:
                        # login if not login_state
                        if not self.login_state:
                            self.login(datetime.now(), current_time)
                            self.can_logout = True

                        # self.reply_email(current_time)
                        t = Thread(target=self.reply_email, args=(current_time,))
                        t.daemon = True
                        t.start()
                        
                        # remove the email from the waiting_communication
                        self.reply_lock = False
                        self.waiting_communication.pop(0)

            # 模拟时间
            time_step = timedelta(seconds=config.sim_seconds + random.uniform(-config.interval_seconds, config.interval_seconds))
            current_time += time_step
            time.sleep(1)

        # Generate daily summary as long-term memory for the next day
        if self.start_to_work:
            self.generate_daily_summary()

    def login(self, real_time, sim_time):
        self.login_state = True
        self.logon_logging(real_time, sim_time, "login")

    def logout(self, real_time, sim_time):
        self.login_state = False
        self.logon_logging(real_time, sim_time, "logout")

    def logon_logging(self, real_time, sim_time, status):
        log_file = os.path.join(self.root_log_dir, "logon.csv")
        real_timestamp = real_time.strftime("%Y-%m-%d %H:%M:%S")
        sim_timestamp = sim_time.strftime("%H:%M:%S")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with LOGON_LOCK:
            with open(log_file, mode="a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                if csvfile.tell() == 0:
                    writer.writerow(["id", "real_timestamp", "sim_timestamp", "name", "container_id", "status"])
                writer.writerow([self.id, real_timestamp, sim_timestamp, self.name, self.container_id, status])
    
    def schedule_logging(self, real_time, current_time, activity):
        log_file = os.path.join(self.root_log_dir, "final_schedule.csv")
        real_timestamp = real_time.strftime("%Y-%m-%d %H:%M:%S")
        sim_timestamp = current_time.strftime("%H:%M:%S")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with SCHEDULE_LOCK:
            with open(log_file, mode="a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                if csvfile.tell() == 0:
                    writer.writerow(["id", "index", "real_timestamp", "sim_timestamp", "name", "container_id", "activity"])
                writer.writerow([self.id, self.execution_task_id, real_timestamp, sim_timestamp, self.name, self.container_id, activity])

    def email_logging(self, real_time, sim_time, email_info):
        log_file = os.path.join(self.root_log_dir, "email.csv") # shared by all members
        real_timestamp = real_time.strftime("%Y-%m-%d %H:%M:%S")
        sim_timestamp = sim_time.strftime("%H:%M:%S")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        if len(email_info["to"]) > 1:
            email_cc = email_info["to"][1:]
            email_to = email_info["to"][0]
        else:
            email_cc = []
            email_to = email_info["to"][0]

        with EMAIL_LOCK:
            with open(log_file, mode="a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                if csvfile.tell() == 0:
                    writer.writerow(["email_from", "real_timestamp", "sim_timestamp", "name", "email_to", "email_cc", "subject", "content"])
                writer.writerow([self.id, real_timestamp, sim_timestamp, self.name, email_to, email_cc, email_info["subject"], email_info["content"].replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")])

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Daily execution for existing schedules and members.")
    parser.add_argument("--date", type=str, required=True, help="Day of the week, e.g., Monday")
    parser.add_argument("--week", type=int, required=True, help="Week number, e.g., 1")
    args = parser.parse_args()

    date = args.date
    week = args.week

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

    # execution log directory
    log_dir = config.execution_log_dir
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # log all the terminal output to a file
    daemon_log_dir = os.path.join(log_dir, "daemon_logs")
    os.makedirs(daemon_log_dir, exist_ok=True)
    daemon_log_path = os.path.join(daemon_log_dir, f"daemon_week_{week}_{date}.log")
    sys.stdout = Logger(daemon_log_path)
    sys.stderr = sys.stdout

    # create each agent
    members = [Member(member_id, week, date, config.profile_output_dir, config.init_schedule_dir, log_dir, id_list, id_role_map) for member_id in id_list]

    # Get the start time
    start_time = datetime.strptime("23:59:00", "%H:%M:%S")
    base_date = start_time.date()
    for member in members:
        if member.no_more_task:
            continue
        if member.schedule[0]["Time"] < start_time.strftime("%H:%M:%S"):
            start_time = datetime.strptime(member.schedule[0]["Time"], "%H:%M:%S")
    
    print(f"[INFO] Start time for week {week} - {date} is {start_time.strftime('%H:%M:%S')}.")

    # thread for each member
    threads = []
    for member in members:
        if member.no_more_task:
            continue
        thread = Thread(target=member.run, args=(start_time,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    print(f"[INFO] All members have completed their tasks for week {week} - date {date} .")
    # close the log file
    # stop_event.set()

    sys.stdout.close()
    exit(0)
