#!/bin/bash
END=$PORT+$WORKERS-1

declare -a PIDS=();

polone() {
    echo Terminating all workers
    kill -INT ${PIDS[@]}
}

trap polone INT TERM

for ((i=$PORT;i<=$END;i++)); do
    $PY lets.py -q -p $i -s $((PROMETHEUS_START_PORT + i - PORT)) &
    PID="$!"
    echo "Spawned worker [pid:$PID, port:$i]"
    IDX=$((i - PORT))
    PIDS[$IDX]=$PID
done

wait ${PIDS[@]}
wait ${PIDS[@]}
echo Goodbye
