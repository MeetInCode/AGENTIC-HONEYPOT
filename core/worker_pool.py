"""
Worker Pool — manages N logical async workers for session processing.

Each worker is a slot that can handle one session's background intel pipeline.
Features:
  - Session tracking: know which worker handles which session
  - Abort on duplicate: cancel existing work if same session arrives again
  - Bounded concurrency: max N concurrent background tasks
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, Coroutine, Any

logger = logging.getLogger(__name__)


@dataclass
class WorkerSlot:
    """Represents a single logical worker slot."""
    worker_id: int
    session_id: Optional[str] = None
    task: Optional[asyncio.Task] = None
    cancel_event: Optional[asyncio.Event] = None
    busy: bool = False

    def reset(self):
        """Free this worker slot."""
        self.session_id = None
        self.task = None
        self.cancel_event = None
        self.busy = False


class WorkerPool:
    """
    Manages a fixed pool of async worker slots.

    Usage:
        pool = WorkerPool(num_workers=4)

        # Assign work — returns immediately, work runs in background
        await pool.assign(session_id, cancel_event, coro)

        # Abort existing work for a session
        cancel_event = pool.abort_session(session_id)
    """

    def __init__(self, num_workers: int = 4):
        self.num_workers = num_workers
        self._slots: list[WorkerSlot] = [
            WorkerSlot(worker_id=i) for i in range(num_workers)
        ]
        self._semaphore = asyncio.Semaphore(num_workers)
        self._lock = asyncio.Lock()
        # Track session → worker mapping for fast lookup
        self._session_map: Dict[str, int] = {}
        logger.info(f"WorkerPool initialized with {num_workers} workers")

    async def assign(
        self,
        session_id: str,
        coro: Coroutine,
        cancel_event: asyncio.Event,
    ) -> int:
        """
        Assign a coroutine to a worker slot.

        Acquires a semaphore slot, finds a free worker, and runs the coroutine
        as a background task. Returns the worker_id assigned.

        Args:
            session_id: The session this work belongs to
            coro: The coroutine to run
            cancel_event: Event that signals cancellation
        """
        # Wait for a free slot (queues if all workers busy)
        if self.busy_count >= self.num_workers:
            logger.warning(
                f"⏳ All {self.num_workers} workers busy — "
                f"session {session_id} QUEUED, waiting for a free slot..."
            )
        await self._semaphore.acquire()
        if self.busy_count >= self.num_workers:
            logger.info(f"✅ Slot freed — session {session_id} proceeding")

        async with self._lock:
            # Find a free worker slot
            slot = self._find_free_slot()
            if slot is None:
                # Should not happen due to semaphore, but be safe
                self._semaphore.release()
                logger.error("No free worker slots despite semaphore — this is a bug")
                raise RuntimeError("No free worker slots available")

            slot.session_id = session_id
            slot.cancel_event = cancel_event
            slot.busy = True
            self._session_map[session_id] = slot.worker_id

            # Wrap the coroutine to auto-release the slot on completion
            slot.task = asyncio.create_task(
                self._run_and_release(slot, coro, session_id)
            )

            logger.info(
                f"🔧 Worker {slot.worker_id} assigned to session {session_id} "
                f"[{self.busy_count}/{self.num_workers} busy]"
            )
            return slot.worker_id

    async def _run_and_release(
        self, slot: WorkerSlot, coro: Coroutine, session_id: str
    ):
        """Run the coroutine and release the worker slot when done."""
        try:
            await coro
        except asyncio.CancelledError:
            logger.info(f"🚫 Worker {slot.worker_id} cancelled (session {session_id})")
        except Exception as e:
            logger.error(
                f"Worker {slot.worker_id} error (session {session_id}): {e}",
                exc_info=True,
            )
        finally:
            async with self._lock:
                # Only clear if this slot still belongs to the same session
                # (could have been reassigned already by abort_session)
                if slot.session_id == session_id:
                    self._session_map.pop(session_id, None)
                    slot.reset()
            self._semaphore.release()
            logger.info(
                f"🔓 Worker {slot.worker_id} freed (session {session_id}) "
                f"[{self.busy_count}/{self.num_workers} busy]"
            )

    def abort_session(self, session_id: str) -> Optional[asyncio.Event]:
        """
        Abort the worker currently handling a session.

        Sets the cancel_event (cooperative cancellation) AND cancels the
        asyncio.Task (hard cancellation). Returns the old cancel_event
        if a worker was found, else None.
        """
        worker_id = self._session_map.get(session_id)
        if worker_id is None:
            return None

        slot = self._slots[worker_id]
        if slot.session_id != session_id:
            # Stale mapping
            self._session_map.pop(session_id, None)
            return None

        old_event = slot.cancel_event

        logger.warning(
            f"⚠️ Aborting Worker {worker_id} for session {session_id}"
        )

        # Signal cooperative cancellation
        if old_event:
            old_event.set()

        # Hard cancel the task
        if slot.task and not slot.task.done():
            slot.task.cancel()

        return old_event

    def get_worker_for_session(self, session_id: str) -> Optional[int]:
        """Return the worker_id handling a session, or None."""
        return self._session_map.get(session_id)

    def _find_free_slot(self) -> Optional[WorkerSlot]:
        """Find the first free worker slot."""
        for slot in self._slots:
            if not slot.busy:
                return slot
        return None

    @property
    def busy_count(self) -> int:
        """Number of currently busy workers."""
        return sum(1 for s in self._slots if s.busy)

    def status(self) -> dict:
        """Return current worker pool status for debugging."""
        return {
            "total_workers": self.num_workers,
            "busy_workers": self.busy_count,
            "assignments": {
                s.worker_id: s.session_id
                for s in self._slots
                if s.busy
            },
        }
