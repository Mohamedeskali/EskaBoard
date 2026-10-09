"""Live edits that queue up while the PC is busy are merged into one.

Run: python -m unittest discover -s tests
"""
import queue
import random
import threading
import unittest

from phonekb.server import inject_worker, merge_live


def apply(text, edit):
    count, insert = edit
    return text[:max(0, len(text) - count)] + insert


def diff(old, new):
    """The page's diff: delete after the common prefix, type the rest."""
    p = 0
    while p < min(len(old), len(new)) and old[p] == new[p]:
        p += 1
    return len(old) - p, new[p:]


class MergeLive(unittest.TestCase):
    def test_merged_edit_gives_the_same_text(self):
        rng = random.Random(1)
        for _ in range(2000):
            texts = ["".join(rng.choice("ab سلام\n") for _ in range(rng.randint(0, 30)))
                     for _ in range(rng.randint(2, 6))]
            edits = [diff(a, b) for a, b in zip(texts, texts[1:])]
            merged = edits[0]
            for edit in edits[1:]:
                merged = merge_live(merged, edit)
            self.assertEqual(apply(texts[0], merged), texts[-1])


class Recorder:
    def __init__(self, gate):
        self.gate = gate
        self.calls = []
        self.busy = threading.Event()
        self.done = threading.Event()

    def press_backspace(self, count):
        self.gate.wait()
        self.calls.append(("backspace", count))

    def type_text_live(self, text):
        self.busy.set()
        self.gate.wait()
        self.calls.append(("type", text))
        if text.endswith("!"):
            self.done.set()

    def press(self, key):
        self.calls.append(("key", key))


class Worker(unittest.TestCase):
    def test_edits_queued_while_busy_run_once(self):
        gate = threading.Event()
        injector, q = Recorder(gate), queue.Queue()
        inject_worker(injector, q)
        long_text = "x" * 1000
        q.put({"type": "live", "delete": 0, "insert": long_text})
        self.assertTrue(injector.busy.wait(2))
        mirror = long_text
        # Letters typed near the start while the first paste is still going
        for i in range(5):
            new = mirror[:10] + "abcde"[:i + 1] + long_text[10:]
            count, insert = diff(mirror, new)
            q.put({"type": "live", "delete": count, "insert": insert})
            mirror = new
        q.put({"type": "key", "key": "tab"})
        q.put({"type": "live", "delete": 0, "insert": "!"})
        gate.set()
        self.assertTrue(injector.done.wait(2))
        self.assertEqual(injector.calls, [
            ("type", long_text),
            ("backspace", 990), ("type", "abcde" + "x" * 990),
            ("key", "tab"),
            ("type", "!"),
        ])
        q.put(None)


if __name__ == "__main__":
    unittest.main()
