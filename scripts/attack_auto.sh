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

attacker_id="his-1"

# attacks=("gen_attack_2" "gen_attack_3" "gen_attack_4" "gen_attack_5" "gen_attack_6" "gen_attack_7" "gen_attack_8" "gen_attack_9" "gen_attack_10" "gen_attack_11" "gen_attack_12" "multi_attack_1" "multi_attack_2" "multi_attack_3")

attacks=("multi_attack_2")

# attacks=("gen_attack_1" "gen_attack_2" "gen_attack_3" "gen_attack_4" "gen_attack_5" "gen_attack_6" "gen_attack_7" "gen_attack_8" "gen_attack_9" "gen_attack_10" "gen_attack_11" "gen_attack_12" "multi_attack_1" "multi_attack_2" "multi_attack_3")

for attack_id in ${attacks[@]}; do
    echo "======= Running for attack $attack_id ========="
    
    FILE_NAME="$attack_id"

    # collect sysdig data
    # scap_record_detail_cmd="sudo sysdig -v -b -p \"%evt.rawtime %user.uid %proc.pid %proc.name %thread.tid %syscall.type %evt.dir %evt.args\" -w $OUTPUT_DIR/$FILE_NAME.scap container.id=$CONTAINER_ID"
    scap_record_cmd="sudo sysdig -v -b -p \"%evt.rawtime %user.uid %proc.pid %proc.name %syscall.type %evt.dir\" -w $OUTPUT_DIR/$FILE_NAME.scap container.id=$CONTAINER_ID"
    tmux send -t "scap" "$scap_record_cmd" ENTER
    # collect pcap data
    pcap_record_cmd="sudo nsenter -t $CONTAINER_PID -n tcpdump -i any -w $OUTPUT_DIR/$FILE_NAME.pcap"
    tmux send -t "pcap" "$pcap_record_cmd" ENTER

        # run the simulation
        docker exec chimera bash -c "source /data/Chimera/.venv/bin/activate && python /data/Chimera/demo/daily_execution_auto_attack.py --attacker $attacker_id --attid $attack_id"

        # wait for the simulation to finish
        sleep 1

        # stop the data collection
        # tmux send -t record 'C-c' ENTER
        tmux send -t "scap" "C-c" ENTER
        tmux send -t "pcap" "C-c" ENTER

        # wait for the data collection to finish
        sleep 5
done

tmux kill-session -t scap
tmux kill-session -t pcap
