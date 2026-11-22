import time
import sys
import os
import random
import numpy as np

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

for name in ("islands"):
    if os.path.exists(os.path.join(script_dir, f"{name}.py")):
        import importlib
        gen = importlib.import_module(name)
        break
else:
    print("Помилка: файл islands.py не знайдено.")
    sys.exit(1)

RUNS    = 20
CONFIGS = [(i, j) for i in range(3, 6) for j in range(3, 6)]


class _AttemptCapture:
    def __init__(self):
        self.attempts = None
        self._orig = sys.stdout

    def write(self, s):
        if "OK за" in s and "спроб" in s:
            try:
                self.attempts = int(s.strip().split("за")[1].split("спроб")[0].strip())
            except Exception:
                pass
        self._orig.write(s)

    def flush(self):
        self._orig.flush()


def run_once(islands, clusters, seed):
    capture = _AttemptCapture()
    sys.stdout = capture
    t0 = time.perf_counter()
    try:
        regions, _ = gen.generate_map(islands, clusters, seed=seed)
    except TypeError:
        random.seed(seed)
        np.random.seed(seed)
        regions, _ = gen.generate_map(islands, clusters)
    finally:
        sys.stdout = capture._orig
    elapsed = time.perf_counter() - t0
    if regions is None:
        return None
    return capture.attempts, elapsed, regions


def compute_stats(values):
    arr = [v for v in values if v is not None]
    if not arr:
        return None
    n   = len(arr)
    avg = sum(arr) / n
    std = (sum((x - avg)**2 for x in arr) / n) ** 0.5
    return {"avg": avg, "std": std, "min": min(arr), "max": max(arr), "n": n}


print("=" * 72)
print(f"  БЕНЧМАРК ГЕНЕРАТОРА КАРТ   ({RUNS} запусків на конфігурацію)")
print("=" * 72)

results = {}

for isl, cls in CONFIGS:
    key  = (isl, cls)
    tag  = f"{isl}×{cls}"
    print(f"\n  Конфігурація {tag}  ", end="", flush=True)

    attempts_list = []
    time_list     = []
    diff_list     = []
    fail_count    = 0

    for run_idx in range(RUNS):
        seed = run_idx * 1000 + isl * 100 + cls
        res  = run_once(isl, cls, seed)
        print(".", end="", flush=True)

        if res is None:
            fail_count += 1
            continue

        attempts, elapsed, regions = res

        players = [r for r in regions if r.type == "player"]
        if len(players) == 2:
            a1, a2 = players[0].area, players[1].area
            diff_pct = abs(a1 - a2) * 100
            diff_list.append(diff_pct)

        if attempts is not None:
            attempts_list.append(attempts)
        time_list.append(elapsed)

    results[key] = {
        "attempts": compute_stats(attempts_list),
        "time":     compute_stats(time_list),
        "diff":     compute_stats(diff_list),
        "fails":    fail_count,
    }

    st = results[key]
    a  = st["attempts"]
    t  = st["time"]
    d  = st["diff"]
    if a: print(f"\n    Спроб:  сер={a['avg']:.0f}  макс={a['max']}")
    if t: print(f"    Час:    сер={t['avg']:.2f}с")
    if d: print(f"    Різниця гравців: {d['avg']:.1f}% ± {d['std']:.1f}%")
    if fail_count:
        print(f"    !! Невдалих запусків: {fail_count}")

print("\n\n" + "=" * 72)
print("  ПІДСУМКОВА ТАБЛИЦЯ")
print("=" * 72)
print(f"  {'Конфіг.':<10} {'Спроб сер.(макс.)':<22} {'Рівень':<8} "
      f"{'Час, с':<10} {'Різниця А1-А2, %'}")
print("  " + "-" * 68)

for isl, cls in CONFIGS:
    key = (isl, cls)
    tag = f"{isl}×{cls}"
    st  = results[key]
    a   = st["attempts"]
    t   = st["time"]
    d   = st["diff"]

    attempts_str = f"{a['avg']:.0f} ({a['max']})" if a else "—"
    time_str     = f"{t['avg']:.1f}"              if t else "—"
    diff_str     = f"{d['avg']:.1f} ± {d['std']:.1f}" if d else "—"
    fail_str     = f"  (!{st['fails']} невд.)" if st["fails"] else ""

    print(f"  {tag:<10} {attempts_str:<22} {'1':<8} {time_str:<10} {diff_str}{fail_str}")

print("=" * 72)

csv_path = os.path.join(script_dir, "benchmark_results.csv")
with open(csv_path, "w", encoding="utf-8") as f:
    f.write("Конфіг.,Спроб сер.,Спроб макс.,Час сер. с,Різниця сер. %,Різниця std %,Невдалих\n")
    for isl, cls in CONFIGS:
        key = (isl, cls)
        st  = results[key]
        a   = st["attempts"]
        t   = st["time"]
        d   = st["diff"]
        f.write(
            f"{isl}×{cls},"
            f"{a['avg']:.0f}," f"{a['max']},"
            f"{t['avg']:.2f},"
            f"{d['avg']:.1f}," f"{d['std']:.1f},"
            f"{st['fails']}\n"
        )
print(f"\n  CSV збережено: {csv_path}")