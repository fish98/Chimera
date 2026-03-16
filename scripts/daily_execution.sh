CONTAINER_PID=$(docker inspect -f '{{.State.Pid}}' chimera)
CONTAINER_ID=$(docker ps -a | grep chimera | awk '{print $1}')
OUTPUT_DIR="/data/Logs"

env_command=""

tmux new-session -d -s scap
tmux new-session -d -s pcap

# if not exist Logs directory, create it
if [ ! -d "$OUTPUT_DIR" ]; then
    mkdir -p $OUTPUT_DIR
fi

# weeks=(1 2 3 4
weeks=(1)
# dates=("Monday" "Tuesday" "Wednesday" "Thursday" "Friday" "Saturday" "Sunday")
dates=("Friday" "Saturday" "Sunday")

for week in ${weeks[@]}; do
    for date in ${dates[@]}; do
        echo "======= Running for week $week and date $date ========="
        FILE_NAME="week_${week}_${date}"

        # collect sysdig data
        # scap_record_detail_cmd="sudo sysdig -v -b -p \"%evt.rawtime %user.uid %proc.pid %proc.name %thread.tid %syscall.type %evt.dir %evt.args\" -w $OUTPUT_DIR/$FILE_NAME.scap container.id=$CONTAINER_ID"
        scap_record_cmd="sudo sysdig -v -b -p \"%evt.rawtime %user.uid %proc.pid %proc.name %syscall.type %evt.dir\" -w $OUTPUT_DIR/$FILE_NAME.scap container.id=$CONTAINER_ID"
        tmux send -t "scap" "$scap_record_cmd" ENTER
        # collect pcap data
        pcap_record_cmd="sudo nsenter -t $CONTAINER_PID -n tcpdump -i any -w $OUTPUT_DIR/$FILE_NAME.pcap"
        tmux send -t "pcap" "$pcap_record_cmd" ENTER

        # exit checker
        tmux new-session -d -s monitor-$week-$date
        tmux send -t "monitor-$week-$date" "sleep 60 && bash /data/Chimera/exit_checker.sh $week $date" ENTER

        # run the simulation
        docker exec chimera bash -c "source /data/Chimera/.venv/bin/activate && python /data/Chimera/demo/daily_execution_auto.py --date $date --week $week"

        # wait for the simulation to finish
        sleep 1

        # stop the data collection
        # tmux send -t record 'C-c' ENTER
        tmux send -t "scap" "C-c" ENTER
        tmux send -t "pcap" "C-c" ENTER

        # wait for the data collection to finish
        sleep 5
        
    done
done

tmux kill-session -t scap
tmux kill-session -t pcap
