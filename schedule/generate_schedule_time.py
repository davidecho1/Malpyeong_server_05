import csv
from itertools import combinations
from datetime import date, timedelta
import random
from datetime import datetime, timedelta

MODEL_CSV = "models.csv"
SCHEDULE_CSV = "schedule(day).csv"


START_TIME = datetime(2025, 5, 10, 9, 0)  # 2025-05-10 오전 9시 시작
TIME_INTERVAL = timedelta(minutes=30)     # 30분 단위로 실행


def read_model_list():
    with open(MODEL_CSV, newline='') as f:
        reader = csv.DictReader(f)
        return [row["user_id"].strip() for row in reader if row["user_id"].strip()]

def generate_schedule_by_time(models, start_time, interval):
    pairs = list(combinations(models, 2))
    random.shuffle(pairs)
    
    schedule = []
    for i, (a, b) in enumerate(pairs):
        scheduled_time = start_time + i * interval
        schedule.append((scheduled_time.strftime("%Y-%m-%d %H:%M"), a, b))
    return schedule

def write_schedule_csv(schedule):
    with open(SCHEDULE_CSV, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["datetime", "user1", "user2"])
        for row in schedule:
            writer.writerow(row)

if __name__ == "__main__":
    models = read_model_list()
    if len(models) != 10:
        print(f"모델 수가 {len(models)}개입니다. 정확히 10개여야 합니다.")
    else:
        schedule = generate_schedule_by_time(models, START_TIME, TIME_INTERVAL)
        write_schedule_csv(schedule)
        print(f"무작위 시간 조합 {len(schedule)}개를 {SCHEDULE_CSV}에 저장했습니다.")
