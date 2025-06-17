#!/bin/bash

# -------------------------------
# 사전 경로 설정
# -------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STATE_FILE="$PROJECT_ROOT/state/active_pair.txt"
GET_MODELS="$SCRIPT_DIR/get_schedule_models.py"
API_BASE="http://localhost:5020"

# -------------------------------
#  현재 상태 읽기
# -------------------------------
if [ ! -f "$STATE_FILE" ]; then
  echo "A" > "$STATE_FILE"
fi

ACTIVE=$(cat "$STATE_FILE")
if [ "$ACTIVE" = "A" ]; then
  OLD_PAIR="A"
  NEW_PAIR="B"
  OLD_PORTS=(5021 5022)
  NEW_PORTS=(5023 5024)
  OLD_GPUS=(0 1)
  NEW_GPUS=(2 3)
else
  OLD_PAIR="B"
  NEW_PAIR="A"
  OLD_PORTS=(5023 5024)
  NEW_PORTS=(5021 5022)
  OLD_GPUS=(2 3)
  NEW_GPUS=(0 1)
fi

echo "현재 활성 쌍: $OLD_PAIR → $NEW_PAIR 전환 시작"

# 이전에 서빙 중이던 모델 목록 파일
STATE_MODEL_FILE="$PROJECT_ROOT/state/active_models.txt"
# 없으면 오늘 모델로 초기화
if [ ! -f "$STATE_MODEL_FILE" ]; then
  printf "%s\n%s\n" "$SERVE1" "$SERVE2" > "$STATE_MODEL_FILE"
fi
# OLD1, OLD2 변수에 어제 서빙 모델 이름 로드
mapfile -t OLD_MODELS < "$STATE_MODEL_FILE"
OLD1=${OLD_MODELS[0]}
OLD2=${OLD_MODELS[1]}

# -------------------------------
#  오늘/내일 모델 가져오기
# -------------------------------
TODAY_MODELS=($(python3 "$GET_MODELS" --today))
TOMORROW_MODELS=($(python3 "$GET_MODELS" --tomorrow))

SERVE1=${TODAY_MODELS[0]}
SERVE2=${TODAY_MODELS[1]}
STANDBY1=${TOMORROW_MODELS[0]}
STANDBY2=${TOMORROW_MODELS[1]}

# -------------------------------
#  오늘 줄 없으면 중단
# -------------------------------
if [[ -z "$SERVE1" || -z "$SERVE2" ]]; then
  echo "오늘 날짜에 해당하는 모델이 없습니다."
  exit 1
fi

# -------------------------------
#  기존 serving 모델 → idle
# -------------------------------
echo "serving → idle 전환 중..."
curl -s -X POST $API_BASE/models/idle \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$OLD1\"}"
curl -s -X POST $API_BASE/models/idle \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$OLD2\"}"
# -------------------------------
#  standby → serving
# -------------------------------
echo "old 모델 → new 모델 스위칭 중..."
curl -s -X POST $API_BASE/models/switch \
  -H "Content-Type: application/json" \
  -d "{\"old\":\"$OLD1\",\"new\":\"$SERVE1\",\"gpu_id\":${NEW_GPUS[0]},\"port\":${NEW_PORTS[0]}}"
curl -s -X POST $API_BASE/models/switch \
  -H "Content-Type: application/json" \
  -d "{\"old\":\"$OLD2\",\"new\":\"$SERVE2\",\"gpu_id\":${NEW_GPUS[1]},\"port\":${NEW_PORTS[1]}}"
# -------------------------------
#  idle → standby (내일 모델)
# -------------------------------
if [[ -z "$STANDBY1" || -z "$STANDBY2" ]]; then
  echo "내일 스케줄 없음. standby는 건너뜁니다."
  echo "오늘이 마지막 평가일입니다."
else
  echo "idle → standby 전환 중..."
  curl -s -X POST $API_BASE/models/standby \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"$STANDBY1\",\"gpu_id\":${OLD_GPUS[0]},\"port\":${OLD_PORTS[0]}}"
  curl -s -X POST $API_BASE/models/standby \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"$STANDBY2\",\"gpu_id\":${OLD_GPUS[1]},\"port\":${OLD_PORTS[1]}}"
fi
# -------------------------------
#  포트 스위칭 (iptables)
# -------------------------------
echo "포트 전환 중 (호스트 스크립트 호출)..."
sudo /usr/local/bin/update_iptables.sh \
  1111 ${NEW_PORTS[0]} \
  2222 ${NEW_PORTS[1]}


# -------------------------------
#  상태 저장
# -------------------------------
echo "$NEW_PAIR" > "$STATE_FILE"
echo "스위칭 완료: $NEW_PAIR 쌍이 now serving (포트 1111, 2222)"
