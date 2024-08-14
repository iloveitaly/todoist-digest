import os
import datetime

from apscheduler.schedulers.background import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from todoist_digest import cli

last_synced = None


def handle_click_exit(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except SystemExit as e:
            if e.code != 0:
                raise

    return wrapper


def get_initial_start_date():
    return (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def job():
    global last_synced

    print(f"Running job with last_synced: {last_synced}")

    # TODO this is terrible, but I couldn't figure out how to pass JUST the last_synced param
    # https://stackoverflow.com/questions/48619517/call-a-click-command-from-code
    os.environ["TODOIST_DIGEST_LAST_SYNCED"] = last_synced

    handle_click_exit(cli)()

    last_synced = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def cron():
    global last_synced

    last_synced = get_initial_start_date()

    schedule = os.environ.get("SCHEDULE", "0 6 * * *")

    print(f"Running on schedule: {schedule}")

    scheduler = BlockingScheduler()
    scheduler.add_job(job, CronTrigger.from_crontab(schedule))
    scheduler.start()


if __name__ == "__main__":
    cron()
