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
mapfile -t TODAY_MODELS    < <(python3 "$GET_MODELS" --today)
mapfile -t TOMORROW_MODELS < <(python3 "$GET_MODELS" --tomorrow)

SERVE1=${TODAY_MODELS[0]:-}
SERVE2=${TODAY_MODELS[1]:-}
STANDBY1=${TOMORROW_MODELS[0]:-}
STANDBY2=${TOMORROW_MODELS[1]:-}

# -------------------------------
#  오늘 줄 없으면 중단
# -------------------------------
if [[ -z "$SERVE1" || -z "$SERVE2" ]]; then
  echo "오늘 날짜에 해당하는 모델이 없습니다."
  exit 1
fi

# -------------------------------
# 3) A,B → standby & C,D → serving
#    (FastAPI /models/switch 한 번 호출)
# -------------------------------
echo "→ A,B → standby & C,D → serving 스위칭 중..."
curl -s -X POST "$API_BASE/models/switch"
echo "✔ 스위칭 완료"

# -------------------------------
# 4) 내일 모델(STANDBY1,2) → standby
# -------------------------------
if [[ -n "$STANDBY1" && -n "$STANDBY2" ]]; then
  echo "→ 내일 모델 → standby 전환 중..."
  curl -s -X POST "$API_BASE/models/standby" \
       -H "Content-Type: application/json" \
       -d "{\"user_id\":\"$STANDBY1\",\"gpu_id\":${OLD_GPUS[0]},\"port\":${OLD_PORTS[0]}}"
  curl -s -X POST "$API_BASE/models/standby" \
       -H "Content-Type: application/json" \
       -d "{\"user_id\":\"$STANDBY2\",\"gpu_id\":${OLD_GPUS[1]},\"port\":${OLD_PORTS[1]}}"
  echo "✔ standby 완료"
else
  echo "→ 내일 모델이 없습니다. standby 단계 건너뜀."
fi

# -------------------------------
# 5) IPTABLES NAT 룰 업데이트
# -------------------------------
echo "→ 포트 매핑 갱신: 외부(1111→${NEW_PORTS[0]}, 2222→${NEW_PORTS[1]})"
EXT1=1111; INT1=${NEW_PORTS[0]}
EXT2=2222; INT2=${NEW_PORTS[1]}
/usr/local/bin/update_iptables.sh "$EXT1" "$INT1" "$EXT2" "$INT2"
echo "✔ NAT 룰 업데이트 완료"

# -------------------------------
# 6) 상태 저장
# -------------------------------
echo "$NEW_PAIR" > "$STATE_PAIR_FILE"
printf "%s\n%s\n" "$SERVE1" "$SERVE2" > "$STATE_MODEL_FILE"
echo "▶ 완료: 새로운 active pair = $NEW_PAIR (서빙: $SERVE1, $SERVE2)"
