#!/bin/bash

week="$1"
date="$2"

root_dir="/data/Chimera"
# log_dir="demo/execution_logs/daemon_logs"
log_dir="$root_dir/demo/execution_logs/daemon_logs"
days=("Monday" "Tuesday" "Wednesday" "Thursday" "Friday" "Saturday" "Sunday")

# Fetch the next date
for i in "${!days[@]}"; do
    if [[ "${days[$i]}" == "$date" ]]; then
        next_idx=$(( (i+1) % 7 ))
        next_date="${days[$next_idx]}"
        break
    fi
done

# if next_date in Monday, week +1
if [[ "$next_date" == "Monday" ]]; then
    week=$((week + 1))
fi

log_file="$log_dir/daemon_week_${week}_${date}.log"
next_log_file="$log_dir/daemon_week_${week}_${next_date}.log"

echo "Waiting for completion in $log_file..."

while true; do
    if grep -q "\[INFO\] All members have completed their tasks" "$log_file" 2>/dev/null; then
        echo "Detected completion in $log_file, checking $next_log_file..."
        sleep 3
        # check if the next log file is created, if not, send Ctrl+C to tmux window 'chimera'
        if [ ! -f "$next_log_file" ]; then
            echo "$next_log_file not found, sending Ctrl+C to tmux window 'chimera'"
            tmux send-keys -t chimera C-c ENTER
        else
            echo "$next_log_file already exists, nothing to do."
        fi
        break
    fi
    sleep 2
done
