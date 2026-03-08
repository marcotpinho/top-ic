#!/bin/bash
#
# Run Chao TOP benchmark using main.py directly
#

source ~/miniconda3/etc/profile.d/conda.sh
conda activate argus

BENCHMARK_DIR="benchmarks/chao"
OUTPUT_DIR="benchmark_results_mainpy"
RESULTS_FILE="${OUTPUT_DIR}/results.csv"
MAX_TIME=300
MAX_ITERATIONS=100
SEED=42
LIMIT=10

mkdir -p "${OUTPUT_DIR}"

# Initialize CSV
echo "instance,problem_set,num_agents,num_waypoints,method,total_reward,mean_rssi,num_solutions,elapsed_time,success" > "${RESULTS_FILE}"

PROBLEM_SETS=("p1" "p2" "p3" "p4" "p5")

total_runs=0
for pset in "${PROBLEM_SETS[@]}"; do
    count=$(ls -1 "${BENCHMARK_DIR}/${pset}"/*.txt 2>/dev/null | head -${LIMIT} | wc -l)
    total_runs=$((total_runs + count * 2))
done

echo "Running ${total_runs} experiments"
echo ""

current_run=0

for pset in "${PROBLEM_SETS[@]}"; do
    echo "=== Problem set: ${pset} ==="

    mapfiles=($(ls -1 "${BENCHMARK_DIR}/${pset}"/*.txt 2>/dev/null | head -${LIMIT}))

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

        echo "${instance},${pset},${num_agents},${num_waypoints},surrogate,${total_reward},${mean_rssi},${num_solutions},${elapsed},${success}" >> "${RESULTS_FILE}"
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

        echo "${instance},${pset},${num_agents},${num_waypoints},exact,${total_reward},${mean_rssi},${num_solutions},${elapsed},${success}" >> "${RESULTS_FILE}"
        echo "  Completed in ${elapsed}s, ${num_solutions} solutions, Reward=${total_reward}, RSSI=${mean_rssi}"

    done
done

echo ""
echo "Results saved to: ${RESULTS_FILE}"
