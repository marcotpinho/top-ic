#!/bin/bash
#
# Run Chao TOP benchmark using main.py directly
#

source ~/miniconda3/etc/profile.d/conda.sh
conda activate argus

BENCHMARK_DIR="maps/timing_experiments"
OUTPUT_DIR="timing_results_mainpy"
RESULTS_FILE="${OUTPUT_DIR}/results.csv"
MAX_TIME=3000000
MAX_ITERATIONS=10
SEED=42

mkdir -p "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}/logs"

# Initialize CSV
echo "instance,num_agents,num_waypoints,method,total_reward,mean_rssi,num_solutions,elapsed_time,success" > "${RESULTS_FILE}"

# Get all N100 maps
mapfiles=($(ls -1 "${BENCHMARK_DIR}"/*N100*.txt 2>/dev/null | sort))

total_runs=$((${#mapfiles[@]} * 2))

echo "Running ${total_runs} experiments (${#mapfiles[@]} maps x 2 methods)"
echo ""

current_run=0

for map_file in "${mapfiles[@]}"; do
    instance=$(basename "${map_file}")
    num_agents=$(sed -n '2p' "${map_file}" | awk '{print $2}' | xargs)
    num_waypoints=$(sed -n '1p' "${map_file}" | awk '{print $2}' | xargs)
    map_name="${instance%.txt}"

    # SURROGATE method
    current_run=$((current_run + 1))
    echo "[${current_run}/${total_runs}] ${instance} (SURROGATE)"

    start_time=$(date +%s)

    python3 main.py \
        --map "${map_file}" \
        --algorithm unique_vis \
        --num_iterations ${MAX_ITERATIONS} \
        --max_time ${MAX_TIME} \
        --seed ${SEED} \
        --predict_distances \
        --no_plot \
        > "${OUTPUT_DIR}/logs/${instance%.txt}_surrogate.log" 2>&1

    end_time=$(date +%s)
    elapsed=$((end_time - start_time))

    # Parse results from pickle files
    result=$(python3 parse_results.py "${map_name}" "surrogate" "1.0" "out")
    total_reward=$(echo "$result" | cut -d',' -f1)
    mean_rssi=$(echo "$result" | cut -d',' -f2)
    num_solutions=$(echo "$result" | cut -d',' -f3)

    if [ "$num_solutions" -gt 0 ]; then
        success="True"
    else
        success="False"
    fi

    echo "${instance},${num_agents},${num_waypoints},surrogate,${total_reward},${mean_rssi},${num_solutions},${elapsed},${success}" >> "${RESULTS_FILE}"
    echo "  Completed in ${elapsed}s, ${num_solutions} solutions, Reward=${total_reward}, RSSI=${mean_rssi}"

    # EXACT method
    current_run=$((current_run + 1))
    echo ""
    echo "[${current_run}/${total_runs}] ${instance} (EXACT)"

    start_time=$(date +%s)

    python3 main.py \
        --map "${map_file}" \
        --algorithm unique_vis \
        --num_iterations ${MAX_ITERATIONS} \
        --max_time ${MAX_TIME} \
        --seed ${SEED} \
        --no_plot \
        > "${OUTPUT_DIR}/logs/${instance%.txt}_exact.log" 2>&1

    end_time=$(date +%s)
    elapsed=$((end_time - start_time))

    # Parse results from pickle files
    result=$(python3 parse_results.py "${map_name}" "exact" "1.0" "out")
    total_reward=$(echo "$result" | cut -d',' -f1)
    mean_rssi=$(echo "$result" | cut -d',' -f2)
    num_solutions=$(echo "$result" | cut -d',' -f3)

    if [ "$num_solutions" -gt 0 ]; then
        success="True"
    else
        success="False"
    fi

    echo "${instance},${num_agents},${num_waypoints},exact,${total_reward},${mean_rssi},${num_solutions},${elapsed},${success}" >> "${RESULTS_FILE}"
    echo "  Completed in ${elapsed}s, ${num_solutions} solutions, Reward=${total_reward}, RSSI=${mean_rssi}"

done

echo ""
echo "Results saved to: ${RESULTS_FILE}"
