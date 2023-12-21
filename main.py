import os
import time
from datetime import datetime, timedelta

from todoist_digest import main


def get_past_date():
    return (datetime.utcnow() - timedelta(weeks=2)).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_next_run_timestamp(schedule):
    tomorrow = datetime.utcnow().date() + timedelta(days=1)

    return int(
        datetime.combine(tomorrow, datetime.strptime(schedule, "%H").time()).timestamp()
    )


def is_weekday():
    return datetime.utcnow().isoweekday() < 6


if __name__ == "__main__":
    schedule = os.environ.get("SCHEDULE", "6")
    last_synced = get_past_date()

    while True:
        now = int(time.time())
        next_run = get_next_run_timestamp(schedule)
        sleep_seconds = next_run - now

        print(f"Sleeping for {sleep_seconds} seconds")

        time.sleep(max(sleep_seconds, 0))

        if is_weekday():
            main(
                last_synced,
                os.environ.get("TARGET_USER"),
                os.environ.get("TARGET_PROJECT"),
                os.environ.get("EMAIL_AUTH"),
                os.environ.get("EMAIL_TO"),
            )
            last_synced = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
