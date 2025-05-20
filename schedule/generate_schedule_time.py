import csv
from itertools import combinations
from datetime import date, timedelta
import random
from datetime import datetime, timedelta

MODEL_CSV = "models.csv"
SCHEDULE_CSV = "schedule(day).csv"



def read_model_list():
    with open(MODEL_CSV, newline='') as f:
        reader = csv.DictReader(f)
        return [row["user_id"].strip() for row in reader if row["user_id"].strip()]

def generate_schedule_with_index(models, shuffle=True):
    pairs = list(combinations(models, 2))
    if shuffle:
        random.shuffle(pairs)
    schedule = []
    for i, (a, b) in enumerate(pairs):
        schedule.append((i, a, b))  # i: 순번
    return schedule


def write_schedule_csv(schedule):
    with open(SCHEDULE_CSV, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["index", "user1", "user2"])
        for row in schedule:
            writer.writerow(row)


if __name__ == "__main__":
    models = read_model_list()
    if len(models) != 10:
        print(f"모델 수가 {len(models)}개입니다. 정확히 10개여야 합니다.")
    else:
        schedule = generate_schedule_by_time(models, START_TIME, TIME_INTERVAL)
        write_schedule_csv(schedule)

