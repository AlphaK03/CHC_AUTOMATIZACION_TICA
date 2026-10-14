"""Tiempo restante por ritmo real de confirmaciones, sin importar motores."""
from collections import deque
import math
import time


class RemainingTime:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.samples = deque()
        self.last_success = None
        self.initial_count = 0

    def reset(self, summary):
        now = self.clock()
        self.samples.clear()
        self.samples.append((now, summary.get('succeeded', 0) + summary.get('empty', 0)))
        self.initial_count = summary.get('succeeded', 0) + summary.get('empty', 0)
        self.last_success = now

    def observe(self, summary):
        now = self.clock()
        count = summary.get('succeeded', 0) + summary.get('empty', 0)
        if not self.samples or count < self.samples[-1][1]:
            self.reset(summary)
            return
        if count > self.samples[-1][1]:
            self.last_success = now
        # Keep one anchor preceding the window for a correct denominator.
        if now == self.samples[-1][0]:
            self.samples[-1] = (now, count)
        else:
            self.samples.append((now, count))
        while len(self.samples) > 2 and self.samples[1][0] <= now - 90:
            self.samples.popleft()

    def seconds(self, summary, workers=1):
        remaining = sum(summary.get(key, 0) for key in ('pending', 'running', 'retry'))
        if not remaining:
            return 0
        self.observe(summary)
        now, count = self.samples[-1]
        start, initial = self.samples[0]
        elapsed = now - start
        completed = count - initial
        if elapsed < 15 or count - self.initial_count < max(4, min(12, workers * 2)):
            return None
        if now - self.last_success >= 60:
            return None
        rate = completed / elapsed
        # Adapt to slowdowns and concurrency changes; smooth clustered finishes.
        recent = next((item for item in self.samples if item[0] >= now - 30), self.samples[0])
        recent_elapsed = now - recent[0]
        if recent_elapsed >= 15:
            recent_rate = (count - recent[1]) / recent_elapsed
            rate = 0.7 * recent_rate + 0.3 * rate
        return remaining / rate if rate > 0 else None

    def label(self, summary, workers=1):
        seconds = self.seconds(summary, workers)
        if seconds is None:
            return 'Restante: calculando…'
        if seconds == 0:
            return 'Finalizando…'
        if seconds < 60:
            return f'Restante: ≈ {max(10, math.ceil(seconds / 10) * 10)} s'
        minutes = math.ceil(seconds / 60)
        hours, minutes = divmod(minutes, 60)
        duration = f'{hours} h {minutes} min' if hours and minutes else f'{hours} h' if hours else f'{minutes} min'
        return f'Restante: ≈ {duration}'
