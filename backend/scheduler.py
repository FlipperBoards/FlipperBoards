import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger


_scheduler = AsyncIOScheduler()
_current_job = None


def start_scheduler():
    _scheduler.start()


def stop_scheduler():
    _scheduler.shutdown(wait=False)


def schedule_rotation(interval_seconds: int, callback):
    global _current_job
    if _current_job:
        _current_job.remove()

    _current_job = _scheduler.add_job(
        callback,
        trigger=IntervalTrigger(seconds=interval_seconds),
        id="rotation",
        replace_existing=True,
    )


def cancel_rotation():
    global _current_job
    if _current_job:
        _current_job.remove()
        _current_job = None
