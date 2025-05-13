import csv
from itertools import combinations
from datetime import date, timedelta
import random

MODEL_CSV = "models.csv"
SCHEDULE_CSV = "schedule(day).csv"
START_DATE = date(2025, 5, 10)

def read_model_list():
    with open(MODEL_CSV, newline='') as f:
        reader = csv.DictReader(f)
        return [row["user_id"].strip() for row in reader if row["user_id"].strip()]

def generate_schedule(models, shuffle=True):
    pairs = list(combinations(models, 2))  # 10C2 = 45
    if shuffle:
        random.shuffle(pairs)
    schedule = []
    for i, (a, b) in enumerate(pairs):
        scheduled_date = START_DATE + timedelta(days=i)
        schedule.append((scheduled_date.strftime("%Y-%m-%d"), a, b))
    return schedule

def write_schedule_csv(schedule):
    with open(SCHEDULE_CSV, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["date", "user1", "user2"])
        for row in schedule:
            writer.writerow(row)

if __name__ == "__main__":
    models = read_model_list()
    if len(models) != 10:
        print(f"모델 수가 {len(models)}개입니다. 정확히 10개여야 합니다.")
    else:
        schedule = generate_schedule(models, shuffle=True)
        write_schedule_csv(schedule)
        print(f"무작위 조합 {len(schedule)}개를 {SCHEDULE_CSV}에 저장했습니다.")
