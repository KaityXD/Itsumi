import asyncio
import datetime
import json
import traceback
import uuid
from typing import Any, Callable, Dict, Optional

import discord
from utils.database import db
from utils.logger import logger


class JobManager:
    """
    A persistent, database-backed job scheduling and worker system.
    Ensures scheduled tasks are run even across bot crashes or restarts.
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._lock = asyncio.Lock()

    def register_handler(self, job_name: str, handler: Callable):
        """Register a callback handler for a specific job type."""
        self._handlers[job_name] = handler
        logger.trace(f"Registered job handler for: {job_name}")

    async def schedule_job(
        self,
        job_name: str,
        payload: dict,
        run_at: datetime.datetime,
        max_attempts: int = 3,
    ) -> str:
        """Saves a new job to the database to be processed at the specified datetime."""
        job_id = f"job-{str(uuid.uuid4())[:8]}"
        
        # Store run_at in ISO format for easy sorting and comparison in SQLite
        run_at_str = run_at.isoformat()

        await db.execute(
            """
            INSERT INTO jobs (id, name, payload, run_at, status, max_attempts)
            VALUES (?, ?, ?, ?, 'PENDING', ?)
            """,
            (job_id, job_name, json.dumps(payload), run_at_str, max_attempts),
        )

        logger.trace(f"Scheduled job {job_id} ({job_name}) to run at {run_at_str}")
        return job_id

    async def cancel_job(self, job_id: str):
        """Removes a scheduled job from the database."""
        await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        logger.trace(f"Cancelled job: {job_id}")

    async def process_pending_jobs(self, bot: discord.Bot):
        """
        Polls the database for due pending jobs and processes them.
        Invoked periodically by a background loop.
        """
        # Ensure only one worker run processes jobs at a time
        if self._lock.locked():
            return

        async with self._lock:
            now_str = datetime.datetime.now().isoformat()
            
            due_jobs = await db.fetchall(
                """
                SELECT id, name, payload, run_at, attempts, max_attempts
                FROM jobs
                WHERE status = 'PENDING' AND run_at <= ?
                ORDER BY run_at ASC
                """,
                (now_str,),
            )

            if not due_jobs:
                return

            logger.info(f"Processing {len(due_jobs)} due job(s)...")

            for row in due_jobs:
                job_id = row["id"]
                job_name = row["name"]
                payload_str = row["payload"]
                attempts = row["attempts"]
                max_attempts = row["max_attempts"]

                # Mark job as RUNNING
                await db.execute(
                    "UPDATE jobs SET status = 'RUNNING' WHERE id = ?", (job_id,)
                )

                # Parse payload
                try:
                    payload = json.loads(payload_str)
                except Exception as e:
                    logger.error(f"Failed to parse payload for job {job_id}: {e}")
                    await db.execute(
                        "UPDATE jobs SET status = 'FAILED', error = ? WHERE id = ?",
                        (f"Invalid JSON payload: {e}", job_id),
                    )
                    continue

                handler = self._handlers.get(job_name)
                if not handler:
                    err_msg = f"No handler registered for job type: {job_name}"
                    logger.error(f"Job {job_id} failed: {err_msg}")
                    await db.execute(
                        "UPDATE jobs SET status = 'FAILED', error = ? WHERE id = ?",
                        (err_msg, job_id),
                    )
                    continue

                logger.debug(f"Executing job {job_id} ({job_name})...")
                try:
                    # Execute the job handler
                    await handler(bot, payload)

                    # Success! Mark as COMPLETED
                    await db.execute(
                        "UPDATE jobs SET status = 'COMPLETED' WHERE id = ?", (job_id,)
                    )
                    logger.success(f"Job {job_id} completed successfully.")

                except Exception as e:
                    new_attempts = attempts + 1
                    tb_text = "".join(
                        traceback.format_exception(type(e), e, e.__traceback__)
                    )

                    # Log the traceback to Itsumi's error forensic system
                    try:
                        from utils.error_handler import UniversalErrorHandler
                        handler_forensics = UniversalErrorHandler()
                        handler_forensics.save_error(e)
                    except Exception as fe:
                        logger.error(f"Failed to save job failure to forensics: {fe}")

                    if new_attempts >= max_attempts:
                        logger.error(
                            f"Job {job_id} failed permanently after {new_attempts} attempts: {e}"
                        )
                        await db.execute(
                            """
                            UPDATE jobs
                            SET status = 'FAILED', attempts = ?, error = ?
                            WHERE id = ?
                            """,
                            (new_attempts, tb_text, job_id),
                        )
                    else:
                        logger.warn(
                            f"Job {job_id} failed (attempt {new_attempts}/{max_attempts}). Retrying later. Error: {e}"
                        )
                        await db.execute(
                            """
                            UPDATE jobs
                            SET status = 'PENDING', attempts = ?, error = ?
                            WHERE id = ?
                            """,
                            (new_attempts, tb_text, job_id),
                        )


# Global singleton instance
job_manager = JobManager()
