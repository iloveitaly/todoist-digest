import os
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BlockingScheduler

from todoist_digest import main

last_synced = None


def get_initial_start_date():
    return (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_weekday():
    return datetime.utcnow().isoweekday() < 6


def job():
    if not is_weekday():
        return

    global last_synced

    main(
        last_synced,
        os.environ.get("TARGET_USER"),
        os.environ.get("TARGET_PROJECT"),
        os.environ.get("EMAIL_AUTH"),
        os.environ.get("EMAIL_TO"),
    )

    last_synced = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def cron():
    global last_synced
    last_synced = get_initial_start_date()

    schedule = os.environ.get("SCHEDULE", "0 6 * * *")

    scheduler = BlockingScheduler()
    scheduler.add_job(job, "cron", hour=schedule)
    scheduler.start()


if __name__ == "__main__":
    cron()
