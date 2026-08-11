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
import nest_asyncio
from multiprocessing import Process
from threading import Thread
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
import json
import json5
import os
import csv
import itertools
import random
import threading
import sys
import argparse
import config
from task import run_task
from member_email import get_email_members, get_email_content, reply_email_content
from daily_plan_update import update_daily_schedule_attack
from attack_schedule import select_attack_date
from foundation_model import run_llm

nest_asyncio.apply()

# exit code
# stop_event = threading.Event()


def loaf_browse_in_process(
    week,
    date,
    member_id,
    member_name,
    member_role,
    interests,
    mbti,
    personality,
    log_dir,
    task_id,
    output_dir,
):
    # TODO: promtpt can be refined
    task = f"""You are {member_name} and you are the {member_role} in your company.
                You are a {personality} person. Your MBTI is {mbti}. and your interests are {interests}.
                You are loafing around during the work and browsing the internet.
                Please feel free to browse the websites and find some interesting content based on your interests and preferences.
                Please summarize the content you viewed into few sentences"""
    run_task(week, date, task, member_id, log_dir, task_id, output_dir=output_dir)


def run_task_in_process(
    week, date, task, member_id, log_dir, task_id, output_dir, temperature=0
):
    run_task(
        week,
        date,
        task,
        member_id,
        log_dir,
        task_id,
        output_dir=output_dir,
        temperature=temperature,
    )


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
        self.terminal = sys.stdout
        self.log_file = open(log_file_path, "a")

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)

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
        purturbation_time = timedelta(
            minutes=random.randint(-10, 10), seconds=random.randint(-30, 30)
        )
        task["Time"] = (task_time + purturbation_time).strftime("%H:%M:%S")
    # keep the timeline monotonic: times are zero-padded %H:%M:%S, so a plain
    # string sort is chronological
    schedule.sort(key=lambda task: task["Time"])
    return schedule


class Member:
    def __init__(
        self,
        member_id,
        week,
        date,
        member_config_dir,
        schedule_dir,
        log_dir,
        member_id_list,
        id_role_map,
        attack_id,
        attacker,
    ):
        self.member_config_path = os.path.join(member_config_dir, f"{member_id}.jsonc")

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

        self.schedule_file = os.path.join(
            schedule_dir,
            f"week_{self.week}",
            f"{member_id}_week_{self.week}_{self.date}.json",
        )
        if attacker:
            self.schedule_file = os.path.join(
                config.attack_schedule_dir,
                f"{member_id}_week_{self.week}_{self.date}_attack.json",
            )
        self.no_more_task = False

        if not os.path.exists(self.schedule_file):
            print(
                f"[INFO] Not scheduled task for {self.id} in week {self.week} on {self.date}."
            )
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
        self.loaf_interval = config.loaf_interval  # minutes

        self.reply_lock = False
        self.next_reply_time = None

        # replan proposals produced by reply threads, committed by the main loop
        self.pending_proposals = []
        # at most one reply/replan worker in flight per member
        self.replan_in_flight = False

        if not self.no_more_task:
            self.next_task_time = datetime.strptime(
                self.schedule[self.schedule_index]["Time"], "%H:%M:%S"
            )

        # allocated by next_task_id(); a plain `+= 1` is a read-modify-write and
        # the main loop and the reply thread would hand out colliding ids, which
        # makes run_task() overwrite the previous detailed log of that id
        self._task_id_seq = itertools.count()
        self.temp_dir = os.path.join(log_dir, f"{self.id}_temp")

        self.previous_summary = self.load_previous_summary()
        if self.previous_summary:
            print(
                f"[INFO] {self.id} loaded previous day summary (week {self.previous_summary['week']} - {self.previous_summary['date']})."
            )

        self.attacker = attacker
        if self.attacker:
            # cdev-1_week_1_Friday_attack.json
            with open(
                os.path.join(config.attack_dir, f"{attack_id}.json"), "r"
            ) as fattack:
                self.attack_info = json.load(fattack)

    def load_previous_summary(self):
        """Load the most recent previous day's summary from long-term memory."""
        days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        if self.date not in days:
            return None
        current_idx = days.index(self.date)
        if current_idx > 0:
            prev_week, prev_date = self.week, days[current_idx - 1]
        elif self.week > 1:
            prev_week, prev_date = self.week - 1, "Sunday"
        else:
            return None
        summary_file = os.path.join(
            self.logging_dir, f"daily_summary_week_{prev_week}_{prev_date}.json"
        )
        if os.path.exists(summary_file):
            with open(summary_file, "r") as f:
                return json.load(f)
        return None

    def generate_daily_summary(self):
        """Generate a daily work summary using LLM and save as long-term memory."""
        completed_activities = [
            f"[{task['Time']}] {task['Activity']}"
            for task in self.schedule[: self.schedule_index + 1]
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
            f"Completed activities:\n"
            + "\n".join(completed_activities)
            + "\n\nPlease write your daily work summary."
        )

        try:
            summary_text = run_llm(system_prompt, user_prompt)
        except Exception as e:
            print(f"[WARN] {self.id} failed to generate daily summary: {e}")
            summary_text = (
                f"Completed scheduled tasks for {self.date} of week {self.week}."
            )

        summary_data = {
            "week": self.week,
            "date": self.date,
            "member_id": self.id,
            "summary": summary_text,
        }
        summary_file = os.path.join(
            self.logging_dir, f"daily_summary_week_{self.week}_{self.date}.json"
        )
        os.makedirs(self.logging_dir, exist_ok=True)
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=4, ensure_ascii=False)
        print(f"[INFO] {self.id} daily summary saved: week {self.week} - {self.date}.")

    def send_email(self, activity, current_time, attack_activity):
        recipient_ids = get_email_members(
            activity, self.member_profile, self.member_id_list
        )
        email_data = get_email_content(activity, self.member_profile)
        subject = email_data.get("subject", "")
        content = email_data.get("content", "")

        email_info = {
            "from": self.id,
            "to": recipient_ids,
            "subject": subject,
            "content": content,
        }

        for member in members:
            if member.id in recipient_ids:
                member.waiting_communication.append(email_info)
                print(
                    f"[INFO] {self.id} sent an email at {current_time.strftime('%H:%M:%S')} to {member.id} with subject: {subject}"
                )

        # log the email
        self.email_logging(datetime.now(), current_time, email_info, attack_activity)

    def reply_email_worker(self, incom_email_data, current_time):
        # thin wrapper so a failed reply can never strand the in-flight flag
        try:
            self.reply_email(incom_email_data, current_time)
        finally:
            self.replan_in_flight = False

    def reply_email(self, incom_email_data, current_time):
        recipient_id = incom_email_data[
            "from"
        ]  # TODO: can refine here to include more members
        reply_email, reply_email_data = reply_email_content(
            recipient_id, incom_email_data, self.member_profile
        )
        task_id = self.next_task_id()
        if reply_email:
            # built once, outside the delivery loop: an unknown recipient must
            # not leave it unbound and kill this thread before the replan runs
            email_info = {
                "from": self.id,
                "to": [recipient_id],
                "subject": reply_email_data["subject"],
                "content": reply_email_data["content"],
            }
            delivered = False
            for member in members:
                if member.id == recipient_id:
                    member.waiting_communication.append(email_info)
                    delivered = True
            if not delivered:
                print(
                    f"[WARN] {self.id} could not deliver its reply: unknown recipient {recipient_id}."
                )
            print(
                f"[INFO] {self.id} replied at {current_time.strftime('%H:%M:%S')} to {recipient_id} with subject: {reply_email_data['subject']}"
            )

            # log the email
            self.email_logging(
                datetime.now(), current_time, email_info, attack_activity=False
            )

            # log the email checking task
            self.schedule_logging(
                datetime.now(),
                current_time,
                f"check received email from {recipient_id} and reply",
                task_id,
            )
        else:
            print(
                f"[INFO] {self.id} at {current_time.strftime('%H:%M:%S')} suppose there is no need to reply to {recipient_id}."
            )
            # log the email checking task
            self.schedule_logging(
                datetime.now(),
                current_time,
                f"check received email from {recipient_id}",
                task_id,
            )

        # after replying the email, should update one's schedule
        self.update_schedule(incom_email_data, reply_email_data, current_time)

    def update_schedule(self, incom_email_data, reply_email_data, current_time):
        # update the schedule based on the email content
        print(
            f"[INFO] {self.id} is updating the schedule at {current_time.strftime('%H:%M:%S')}."
        )

        if self.attacker:
            attack_info = self.attack_info
        else:
            attack_info = None

        updated_schedule = update_daily_schedule_attack(
            list(self.schedule),
            self.member_profile,
            incom_email_data,
            reply_email_data,
            current_time,
            self.id_role_map,
            self.attacker,
            attack_info,
            self.previous_summary,
        )

        if updated_schedule is not None:
            # Deliberately do NOT touch the live scheduling state here. This runs
            # in a daemon thread and `current_time` is a snapshot taken before a
            # multi-minute LLM call, by which time the main loop has advanced.
            # Hand the proposal over instead; the main loop commits it against
            # its own up-to-date simulation time. Appending is the only shared
            # write, and the main loop is the only reader/consumer.
            self.pending_proposals.append(updated_schedule)
        else:
            print(
                f"[INFO] {self.id} did not update the schedule at {current_time.strftime('%H:%M:%S')}."
            )

    def commit_proposal(self, proposal, current_time):
        """Merge a replan proposal into the live schedule.

        Only ever called from this member's own main loop, which is the single
        writer of the scheduling state, so no locking is required. Entries that
        have already been dispatched are kept as immutable history and
        `schedule_index` never moves backwards, so nothing can be dispatched
        twice.
        """
        proposal = purturbation_schedule(proposal)
        executed = self.schedule[: self.schedule_index]
        pending = [
            task
            for task in proposal
            if datetime.strptime(task["Time"], "%H:%M:%S") > current_time
        ]
        if not pending:
            print(
                f"[INFO] {self.id} rejected a replan at {current_time.strftime('%H:%M:%S')}: "
                f"nothing proposed after the current execution point."
            )
            return

        self.schedule = executed + pending
        # the execution boundary is unchanged by construction
        self.schedule_index = len(executed)
        print(
            f"[INFO] {self.id} committed a replan at {current_time.strftime('%H:%M:%S')}: "
            f"{len(executed)} dispatched, {len(pending)} pending."
        )

        # re-evaluate the next task against the *current* simulation time
        self.check_next_task(current_time)

    def next_task_id(self):
        # next() on an itertools.count is a single atomic C call, so the main
        # loop and the reply thread can allocate concurrently without a lock
        return next(self._task_id_seq)

    def execute_task(self, activity, current_time, attack_activity):
        task_id = self.next_task_id()
        if "break" in activity:
            self.logout(datetime.now(), current_time, attack_activity)
            self.can_logout = False
        else:
            if not self.login_state:
                self.login(datetime.now(), current_time, attack_activity)
                self.can_logout = True

            if "@" in activity:
                t = Thread(
                    target=self.send_email,
                    args=(
                        activity,
                        current_time,
                        attack_activity,
                    ),
                )
                t.daemon = True
                t.start()

            elif "LoafBrowsing" in activity:
                activity = "loafing around and browsing the internet."
                process = Process(
                    target=loaf_browse_in_process,
                    args=(
                        self.week,
                        self.date,
                        self.id,
                        self.name,
                        self.role,
                        self.interests,
                        self.mbti,
                        self.personality,
                        self.logging_dir,
                        task_id,
                        self.temp_dir,
                    ),
                )
                process.start()

            else:
                task_temperature = 0.7 if attack_activity else 0
                process = Process(
                    target=run_task_in_process,
                    args=(
                        self.week,
                        self.date,
                        activity,
                        self.id,
                        self.logging_dir,
                        task_id,
                        self.temp_dir,
                        task_temperature,
                    ),
                )
                process.start()
                # process.join()

            self.can_logout = True

        # log the task execution
        self.schedule_logging(
            datetime.now(), current_time, activity, task_id, attack_activity
        )

        # move to the next task
        self.move_to_next_task(current_time)

    def loaf(self, current_time):
        loaf_wait_time = timedelta(seconds=random.randint(1, 3) * 60)
        loaf_time = current_time + loaf_wait_time
        loaf_task = {"Time": loaf_time.strftime("%H:%M:%S"), "Activity": "LoafBrowsing"}
        self.schedule.insert(self.schedule_index, loaf_task)
        # important: update the time for new next task
        self.next_task_time = datetime.strptime(
            self.schedule[self.schedule_index]["Time"], "%H:%M:%S"
        )

    def move_to_next_task(self, current_time):
        self.schedule_index += 1
        if self.schedule_index < len(self.schedule):
            self.next_task_time = datetime.strptime(
                self.schedule[self.schedule_index]["Time"], "%H:%M:%S"
            )
            # if next task more than 30 min, can logout or random browse
            # loaf around or logout
            next_task_interval = self.next_task_time - current_time
            if next_task_interval > timedelta(minutes=self.loaf_interval):  # (hours=1)
                if random.random() > self.loaf_rate:
                    # logout
                    if self.can_logout:
                        self.logout(datetime.now(), current_time)
                        self.can_logout = False
                        print(
                            f"[INFO] Next task after {str(next_task_interval).split('.')[0]} at {current_time.strftime('%H:%M:%S')}, {self.id} AFK."
                        )
                else:
                    # loaf around
                    print(
                        f"[INFO] Next task after {str(next_task_interval).split('.')[0]} at {current_time.strftime('%H:%M:%S')}, {self.id} is loafing around."
                    )
                    self.loaf(
                        current_time
                    )  # policy can be changed (browse once or more)
        else:
            if self.login_state:
                self.logout(datetime.now(), current_time)
                self.can_logout = False
            self.no_more_task = True

    def check_next_task(self, current_time):
        if self.schedule_index < len(self.schedule):
            self.next_task_time = datetime.strptime(
                self.schedule[self.schedule_index]["Time"], "%H:%M:%S"
            )
            # can logout or random browse
            next_task_interval = self.next_task_time - current_time
            if next_task_interval > timedelta(minutes=self.loaf_interval):  # (hours=1)
                # NOTE: same orientation as move_to_next_task(): loaf_rate is the
                # probability of loafing, so AFK is the `>` branch
                if random.random() > self.loaf_rate:
                    # logout
                    if self.can_logout:
                        self.logout(datetime.now(), current_time)
                        self.can_logout = False
                        print(
                            f"[INFO] Next task after {str(next_task_interval).split('.')[0]} at {current_time.strftime('%H:%M:%S')}, {self.id} AFK."
                        )
                else:
                    # loaf around
                    print(
                        f"[INFO] Next task after {str(next_task_interval).split('.')[0]} at {current_time.strftime('%H:%M:%S')}, {self.id} is loafing around."
                    )
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
                print(
                    f"[INFO] {self.id} has completed all tasks for today at {current_time.strftime('%H:%M:%S')}."
                )
                break

            # check if start to work
            if not self.start_to_work and current_time >= first_task_time:
                self.start_to_work = True
                print(
                    f"[INFO] {self.id} start to work at {current_time.strftime('%H:%M:%S')}."
                )

            if not self.start_to_work:
                time_step = timedelta(
                    seconds=config.sim_seconds
                    + random.uniform(-config.interval_seconds, config.interval_seconds)
                )
                current_time += time_step
                time.sleep(1)
                continue

            # commit replans handed over by reply threads, using this loop's own
            # up-to-date simulation time rather than the thread's stale snapshot
            while self.pending_proposals:
                self.commit_proposal(self.pending_proposals.pop(0), current_time)

            if not self.no_more_task and current_time >= self.next_task_time:
                activity = self.schedule[self.schedule_index]["Activity"]
                attack_activity = False
                if self.schedule[self.schedule_index].get("Attack", False):
                    attack_activity = True
                self.execute_task(activity, current_time, attack_activity)

            # before update time, check if there is any email then schedule the next reply
            if not self.no_more_task and self.waiting_communication != []:
                if not self.reply_lock:
                    """
                    every time finish the task, check if there is any email, add one task into the logging.
                    pick a time to reply instead of immediately from the next task time,
                    pick the middle time to reply: from current_time to next_task_time
                    next_reply_time = time between current_time and next_task_time
                    """
                    # clamp to a non-negative offset: a next task that is already
                    # overdue must not schedule the reply in the past, which
                    # would spawn a reply worker on every single iteration
                    self.next_reply_time = (
                        current_time
                        + max(self.next_task_time - current_time, timedelta(0)) / 2
                    )
                    # print(f"[DEBUG] reply time set for {self.id} is {self.next_reply_time}")
                    self.reply_lock = True
                else:
                    # check if the reply time is over; hold off while a previous
                    # replan is still running so proposals cannot pile up
                    if (
                        current_time >= self.next_reply_time
                        and not self.replan_in_flight
                    ):
                        # login if not login_state
                        if not self.login_state:
                            self.login(datetime.now(), current_time)
                            self.can_logout = True

                        # dequeue *before* handing the email over, so the worker
                        # cannot race with this pop and reply to the wrong email
                        incom_email_data = self.waiting_communication.pop(0)
                        self.replan_in_flight = True
                        t = Thread(
                            target=self.reply_email_worker,
                            args=(
                                incom_email_data,
                                current_time,
                            ),
                        )
                        t.daemon = True
                        t.start()

                        self.reply_lock = False
            time_step = timedelta(
                seconds=config.sim_seconds
                + random.uniform(-config.interval_seconds, config.interval_seconds)
            )
            current_time += time_step
            time.sleep(1)

        # Generate daily summary as long-term memory for the next day
        if self.start_to_work:
            self.generate_daily_summary()

    def login(self, real_time, sim_time, attack_activity=False):
        self.login_state = True
        self.logon_logging(real_time, sim_time, "login", attack_activity)

    def logout(self, real_time, sim_time, attack_activity=False):
        self.login_state = False
        self.logon_logging(real_time, sim_time, "logout", attack_activity)

    def logon_logging(self, real_time, sim_time, status, attack_activity):
        log_file = os.path.join(self.root_log_dir, "logon.csv")
        real_timestamp = real_time.strftime("%Y-%m-%d %H:%M:%S")
        sim_timestamp = sim_time.strftime("%H:%M:%S")
        if attack_activity:
            write_id = f"(Attack){self.id}"
        else:
            write_id = self.id
        # check if the log file exists, if not create it
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with LOGON_LOCK:
            with open(log_file, mode="a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                if csvfile.tell() == 0:
                    writer.writerow(
                        [
                            "id",
                            "real_timestamp",
                            "sim_timestamp",
                            "name",
                            "container_id",
                            "status",
                        ]
                    )
                writer.writerow(
                    [
                        write_id,
                        real_timestamp,
                        sim_timestamp,
                        self.name,
                        self.container_id,
                        status,
                    ]
                )

    def schedule_logging(
        self, real_time, current_time, activity, task_id, attack_activity=False
    ):
        log_file = os.path.join(self.root_log_dir, "final_schedule.csv")
        real_timestamp = real_time.strftime("%Y-%m-%d %H:%M:%S")
        sim_timestamp = current_time.strftime("%H:%M:%S")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        if attack_activity:
            write_id = f"(Attack){self.id}"
        else:
            write_id = self.id
        with SCHEDULE_LOCK:
            with open(log_file, mode="a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                if csvfile.tell() == 0:
                    writer.writerow(
                        [
                            "id",
                            "index",
                            "real_timestamp",
                            "sim_timestamp",
                            "name",
                            "container_id",
                            "activity",
                        ]
                    )
                writer.writerow(
                    [
                        write_id,
                        task_id,
                        real_timestamp,
                        sim_timestamp,
                        self.name,
                        self.container_id,
                        activity,
                    ]
                )

    def email_logging(self, real_time, sim_time, email_info, attack_activity):
        log_file = os.path.join(self.root_log_dir, "email.csv")  # shared by all members
        real_timestamp = real_time.strftime("%Y-%m-%d %H:%M:%S")
        sim_timestamp = sim_time.strftime("%H:%M:%S")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        if len(email_info["to"]) > 1:
            email_cc = email_info["to"][1:]
            email_to = email_info["to"][0]
        else:
            email_cc = []
            email_to = email_info["to"][0]

        if attack_activity:
            write_id = f"(Attack){self.id}"
        else:
            write_id = self.id

        with EMAIL_LOCK:
            with open(log_file, mode="a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                if csvfile.tell() == 0:
                    writer.writerow(
                        [
                            "email_from",
                            "real_timestamp",
                            "sim_timestamp",
                            "name",
                            "email_to",
                            "email_cc",
                            "subject",
                            "content",
                        ]
                    )
                writer.writerow(
                    [
                        write_id,
                        real_timestamp,
                        sim_timestamp,
                        self.name,
                        email_to,
                        email_cc,
                        email_info["subject"],
                        email_info["content"]
                        .replace("\\", "\\\\")
                        .replace("\n", "\\n")
                        .replace("\r", "\\r"),
                    ]
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Attack execution for existing schedules and members."
    )
    parser.add_argument(
        "--attacker", type=str, required=True, help="Attacker id, e.g., cdev-1"
    )
    parser.add_argument(
        "--attid", type=str, required=True, help="Attack id, e.g., gen_attack_1"
    )
    args = parser.parse_args()

    # Attack setting
    attacker_id = args.attacker
    attacker_ids = [attacker_id]
    attack_id = args.attid
    print(attacker_ids)

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

    attacker_id = attacker_ids[0]
    attack_week, attack_date = select_attack_date(attacker_id, attack_id, id_role_map)

    # attack execution log directory
    log_dir = os.path.join(config.attack_log_dir, f"{attack_id}_{config.company_id}")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # log all the terminal output to a file
    daemon_log_dir = os.path.join(log_dir, "daemon_logs")
    os.makedirs(daemon_log_dir, exist_ok=True)
    daemon_log_path = os.path.join(
        daemon_log_dir, f"daemon_week_{attack_week}_{attack_date}_attack.log"
    )
    sys.stdout = Logger(daemon_log_path)
    sys.stderr = sys.stdout

    # create each agentx
    members = [
        Member(
            member_id,
            attack_week,
            attack_date,
            config.profile_output_dir,
            config.init_schedule_dir,
            log_dir,
            id_list,
            id_role_map,
            attack_id=attack_id,
            attacker=True if member_id in attacker_ids else False,
        )
        for member_id in id_list
    ]

    # Get the start time
    start_time = datetime.strptime("23:59:00", "%H:%M:%S")
    base_date = start_time.date()
    for member in members:
        if member.no_more_task:
            continue
        if member.schedule[0]["Time"] < start_time.strftime("%H:%M:%S"):
            start_time = datetime.strptime(member.schedule[0]["Time"], "%H:%M:%S")

    print(
        f"[INFO][Attack] Start time for week {attack_week} - {attack_date} is {start_time.strftime('%H:%M:%S')}."
    )

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

    print(
        f"[INFO][Attack] All members have completed their tasks for week {attack_week} - date {attack_date}."
    )

    # remove the attack schedule file
    attack_schedule_file = os.path.join(
        config.attack_schedule_dir,
        f"{attacker_id}_week_{attack_week}_{attack_date}_attack.json",
    )
    if os.path.exists(attack_schedule_file):
        os.remove(attack_schedule_file)
        print(f"[INFO] Removed the attack schedule file: {attack_schedule_file}")

    sys.stdout.close()
    exit(0)
