import io
import os
import traceback
from contextlib import redirect_stdout, redirect_stderr

from django.core.management import call_command
from django.db import close_old_connections
from django.utils import timezone

from api.models import ScanPacksRun


def scan_packs_task(run_id: int) -> None:
    """
    Runs the existing management command in a django-q worker.
    Captures output and enforces single-concurrency with a lock file.
    """
    close_old_connections()
    run = ScanPacksRun.objects.get(pk=run_id)

    run.status = ScanPacksRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])

    buf = io.StringIO()

    # IMPORTANT: your scan_packs.py uses a shared OUTFOX_WORKING_PATH/working dir.
    # Prevent concurrent runs across workers/processes.
    working_path = os.getenv("OUTFOX_WORKING_PATH", "./working")
    lock_path = os.path.join(working_path, ".scan_packs.lock")
    os.makedirs(working_path, exist_ok=True)

    try:
        # Linux/Unix file lock
        import fcntl
        with open(lock_path, "w") as lockf:
            fcntl.flock(lockf, fcntl.LOCK_EX)

            with redirect_stdout(buf), redirect_stderr(buf):
                # Capture BaseCommand output too
                call_command("scan_packs", run.packdir, stdout=buf, stderr=buf)

        run.status = ScanPacksRun.Status.SUCCESS
        run.output = buf.getvalue()
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "output", "finished_at"])

    except Exception:
        run.status = ScanPacksRun.Status.FAILED
        run.output = buf.getvalue()
        run.error = traceback.format_exc()
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "output", "error", "finished_at"])

    finally:
        close_old_connections()

