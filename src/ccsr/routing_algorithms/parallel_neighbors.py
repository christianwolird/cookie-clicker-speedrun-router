"""Speculate on queued states while committing in serial search order."""

from concurrent.futures import ProcessPoolExecutor

from ..errands.generator import generate_neighbors


class NeighborExecutor:
    def __init__(self, workers, target, options):
        self.workers = workers
        self.target = target
        self.options = options
        self.pending = {}
        self.pool = None
        self.hits = self.misses = 0

    def __enter__(self):
        if self.workers > 1:
            self.pool = ProcessPoolExecutor(max_workers=self.workers)
        return self

    def prefetch(self, queue, is_live, bound):
        if self.pool is None:
            return
        # Inspect a small heap prefix, not the entire (potentially huge) queue.
        candidates = {
            entry[2] for entry in queue[:2 * self.workers]
            if entry[0] < bound and is_live(entry[2])
        }
        for state, future in tuple(self.pending.items()):
            if state not in candidates and (future.done() or future.cancel()):
                del self.pending[state]
        for _, _, state in queue[:2 * self.workers]:
            if len(self.pending) >= 2 * self.workers:
                break
            if state in candidates and state not in self.pending:
                self.pending[state] = self.pool.submit(
                    generate_neighbors, state, self.target, **self.options,
                )

    def neighbors(self, state):
        if self.pool is None:
            return generate_neighbors(state, self.target, **self.options)
        future = self.pending.pop(state, None)
        if future is None:
            self.misses += 1
            future = self.pool.submit(generate_neighbors, state, self.target, **self.options)
        else:
            self.hits += 1
        neighbors = future.result()
        # Pickling copies the immutable catalogs. Share the coordinator's
        # originals again so retained states don't keep one catalog per batch.
        for neighbor in neighbors:
            neighbor.gamestate.building_catalog = state.building_catalog
            neighbor.gamestate.upgrade_catalog = state.upgrade_catalog
            neighbor.gamestate.achievement_curve = state.achievement_curve
        return neighbors

    def __exit__(self, *exc):
        if self.pool is not None:
            self.pool.shutdown(wait=True, cancel_futures=True)
