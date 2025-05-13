import csv
import datetime
import os
from typing import List, Optional

# 현재 이 파일 기준으로 schedule(day).csv 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 프로젝트 루트
SCHEDULE_CSV = os.path.join(BASE_DIR, "schedule", "schedule(day).csv")

def get_models_for(target_date: datetime.date) -> Optional[List[str]]:
    """
    주어진 날짜에 해당하는 모델 쌍을 반환합니다.
    예: ['TeamA/model1', 'TeamB/model2']
    """
    target_str = target_date.strftime("%Y-%m-%d")
    with open(SCHEDULE_CSV, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["date"] == target_str:
                return [row["user1"].strip(), row["user2"].strip()]
    return None

def get_today_models() -> Optional[List[str]]:
    return get_models_for(datetime.date.today())

def get_tomorrow_models() -> Optional[List[str]]:
    return get_models_for(datetime.date.today() + datetime.timedelta(days=1))

# 테스트 실행
if __name__ == "__main__":
    print("📅 오늘 모델:", get_today_models())
    print("📅 내일 모델:", get_tomorrow_models())
