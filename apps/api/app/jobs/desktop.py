"""Bounded desktop executor; PostgreSQL remains the durable queue and job lease."""

import logging
import signal
import threading
from concurrent.futures import ThreadPoolExecutor

from app.db import SessionLocal
from app.jobs.service import transition
from app.jobs.worker import dispatch_pending, process
from app.models import Job
from sqlalchemy import select


def run():
    stopped = threading.Event()
    for value in (signal.SIGTERM, signal.SIGINT):
        signal.signal(value, lambda *_: stopped.set())
    with ThreadPoolExecutor(max_workers=2) as pool:
        active = {}
        while not stopped.is_set():
            completed = {future for future in active if future.done()}
            for future in completed:
                try:
                    future.result()
                except Exception:
                    logging.getLogger("lumvia.worker").warning("desktop_job_deferred")
            for future in completed:
                del active[future]
            available = 2 - len(active)
            if available:
                try:
                    dispatch_pending.run(
                        deliver=lambda identifier: active.update(
                            {pool.submit(process.run, identifier): identifier}
                        ),
                        limit=available,
                    )
                except Exception:
                    logging.getLogger("lumvia.worker").warning("desktop_dispatch_deferred")
            stopped.wait(2)
        # Cancel only this executor's active leases. Processing cooperatively stops its
        # FFmpeg subprocess groups before the database and application shut down.
        if active:
            with SessionLocal() as db:
                rows = db.scalars(select(Job).where(Job.id.in_(active.values())).with_for_update())
                for job in rows:
                    if job.state == "RUNNING":
                        transition(job, "CANCEL_REQUESTED")
                db.commit()


if __name__ == "__main__":
    run()
