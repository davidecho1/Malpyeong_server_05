#!/usr/bin/env python3
import csv
import datetime
from datetime import timedelta
import os
import sys
import argparse
from typing import List, Optional

# ──────────────────────────────────────────────────
# 1) 이 파일 위치 기준으로 schedule CSV 경로 계산
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
SCHEDULE_CSV = os.path.join(BASE_DIR, "..", "schedule", "schedule(day).csv")
# ──────────────────────────────────────────────────

def get_models_for(target_date: datetime.date, csv_path: str) -> Optional[List[str]]:
    """
    주어진 날짜(target_date)에 해당하는 [user1, user2] 모델을 반환.
    없으면 None.
    """
    target_str = target_date.strftime("%Y-%m-%d")
    try:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("date", "").strip() == target_str:
                    return [
                        row.get("user1", "").strip(),
                        row.get("user2", "").strip()
                    ]
    except FileNotFoundError:
        sys.stderr.write(f"Error: 스케줄 CSV를 찾을 수 없습니다: {csv_path}\n")
    except Exception as e:
        sys.stderr.write(f"Error reading {csv_path}: {e}\n")
    return None

def get_today_models(csv_path: str) -> Optional[List[str]]:
    return get_models_for(datetime.date.today(), csv_path)

def get_tomorrow_models(csv_path: str) -> Optional[List[str]]:
    return get_models_for(datetime.date.today() + timedelta(days=1), csv_path)

def main():
    parser = argparse.ArgumentParser(
        description="스케줄 CSV에서 오늘 또는 내일 모델 페어(user1, user2)만 한 줄씩 출력합니다."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--today",    action="store_true", help="오늘 모델 출력")
    group.add_argument("--tomorrow", action="store_true", help="내일 모델 출력")
    parser.add_argument(
        "--csv", "-c",
        default=SCHEDULE_CSV,
        help="스케줄 CSV 파일 경로 (기본: schedule/schedule(day).csv)"
    )
    args = parser.parse_args()

    # 오늘/내일 중 하나 선택
    if args.today:
        models = get_today_models(args.csv)
    else:
        models = get_tomorrow_models(args.csv)

    # 모델이 없거나 2개가 아니면 에러 종료
    if not models or len(models) != 2:
        sys.exit(1)

    # 한 줄에 하나씩 출력
    for m in models:
        print(m)

if __name__ == "__main__":
    main()

