#!/usr/bin/env bash
# test_fast_schedule.sh
#  ↳ 3분(180초) 간격으로 4회 스위칭 테스트

# 실행 횟수, 인터벌(초) 설정
ITERATIONS=4
INTERVAL=180            # 3분

for i in $(seq 1 $ITERATIONS); do
  echo "======================================"
  echo "▶ Test run: $i / $ITERATIONS  ($(date '+%Y-%m-%d %H:%M:%S'))"
  echo "--------------------------------------"

  # 1) Active pair
  echo "- Active pair:"
  cat state/active_pair.txt || echo "(no state file)"

  # 2) 오늘/내일 모델
  echo "- Schedule models:"
  python3 scripts/get_schedule_models.py || echo "(schedule parse error)"

  echo "--------------------------------------"
  echo "- Running switch_models_and_ports.sh..."
  # 3) 실제 스위치 스크립트 호출 (idle→serve→standby → iptables)
  bash -x scripts/switch_models_and_ports.sh

  echo
  if [ $i -lt $ITERATIONS ]; then
    echo "Sleeping for $INTERVAL seconds..."
    sleep $INTERVAL
    echo
  fi
done

echo "▶ All tests done."

