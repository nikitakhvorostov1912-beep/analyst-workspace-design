#!/bin/bash
# Benchmark NIM throughput: 5 конфигураций на 50 carts ut115 mock.
# Без --apply-immediately — БД не меняется, только response files.
#
# Output: caption + ok/fail/time для каждой конфигурации, выводим табличкой.

set -u
export NVIDIA_NIM_KEY="${NVIDIA_NIM_KEY:?Set NVIDIA_NIM_KEY env var}"
export PYTHONIOENCODING=utf-8

CHANNEL="_ut115_17_226"
LIMIT=50
MODEL="qwen/qwen3.5-122b-a10b"

run_test() {
    local name="$1"; local conc="$2"; local mt="$3"
    local t0=$(date +%s)
    local out=$(python -X utf8 -m scripts.nvidia_nim_rebuild \
        --channel-id "$CHANNEL" --limit "$LIMIT" \
        --model "$MODEL" \
        --concurrency "$conc" --chunk-size "$LIMIT" \
        --max-tokens "$mt" 2>&1)
    local t1=$(date +%s)
    local elapsed=$((t1-t0))
    # Парсим "ok=X fail=Y" из последней строки chunk
    local ok=$(echo "$out" | grep -oE "ok=[0-9]+" | tail -1 | grep -oE "[0-9]+")
    local fail=$(echo "$out" | grep -oE "fail=[0-9]+" | tail -1 | grep -oE "[0-9]+")
    local code429=$(echo "$out" | grep -c "429")
    local code500=$(echo "$out" | grep -c "500")
    echo "$name|conc=$conc|max_tok=$mt|time=${elapsed}s|ok=${ok:-0}|fail=${fail:-0}|429=$code429|500=$code500"
}

echo "=== BENCHMARK START $(date +%H:%M:%S) ==="
echo "Каждый тест: $LIMIT carts ut115, без apply, последовательно"
echo

run_test "T1" 10 1100
run_test "T2" 20 1100
run_test "T3" 30 1100
run_test "T4" 20 700
run_test "T5" 40 700

echo
echo "=== BENCHMARK END $(date +%H:%M:%S) ==="
