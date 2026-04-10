import asyncio
import logging
import os
import shutil

from fastapi import HTTPException

from src.config import settings

logger = logging.getLogger(__name__)


async def watch_incoming() -> None:
    """Background task: poll incoming_cvs/ and auto-process any new files."""
    from src.routers.upload import _process_cv_bytes  # late import to avoid circular

    incoming = settings.incoming_cvs_path
    processed = settings.processed_cvs_path
    failed = settings.failed_cvs_path

    os.makedirs(incoming, exist_ok=True)
    os.makedirs(processed, exist_ok=True)
    os.makedirs(failed, exist_ok=True)

    logger.info(
        "File watcher started — polling %s every %ds", incoming, settings.watcher_interval
    )

    while True:
        try:
            files = [
                f for f in os.listdir(incoming)
                if os.path.isfile(os.path.join(incoming, f))
            ]
            for filename in files:
                src = os.path.join(incoming, filename)
                logger.info("Watcher: detected %s", filename)
                try:
                    with open(src, "rb") as f:
                        file_bytes = f.read()
                    await _process_cv_bytes(file_bytes, filename)
                    shutil.move(src, os.path.join(processed, filename))
                    logger.info("Watcher: %s → processed/", filename)
                except HTTPException as e:
                    if e.status_code == 409:
                        shutil.move(src, os.path.join(processed, filename))
                        logger.info("Watcher: duplicate %s → processed/", filename)
                    else:
                        shutil.move(src, os.path.join(failed, filename))
                        logger.warning("Watcher: %s → failed/ (%s)", filename, e.detail)
                except Exception as e:
                    shutil.move(src, os.path.join(failed, filename))
                    logger.error("Watcher: %s → failed/ (unexpected: %s)", filename, e)
        except asyncio.CancelledError:
            logger.info("File watcher stopped")
            return
        except Exception as e:
            logger.error("Watcher loop error: %s", e)

        await asyncio.sleep(settings.watcher_interval)
