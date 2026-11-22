import tkinter as tk
from tkinter import ttk, font
import threading
import sys
import os

BG        = "#0D2B3E"
BG2       = "#0B1E2D"
ACCENT    = "#5C9ABF"
ACCENT2   = "#FFF176"
TEXT      = "#E0EAF0"
TEXT_DIM  = "#7FB3CC"
GREEN     = "#69F0AE"
RED       = "#FF5252"
SLIDER_BG = "#1A3A50"
BTN_BG    = "#1A4F6E"
BTN_HOV   = "#2A6F9E"
BTN_ACT   = "#3A8FBE"

class MapGeneratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Генератор ігрових карт")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.islands_var  = tk.IntVar(value=3)
        self.clusters_var = tk.IntVar(value=3)
        self.seed_var     = tk.StringVar(value="")

        self.buildings_var   = tk.BooleanVar(value=True)
        self.trees_var       = tk.BooleanVar(value=True)
        self.rocks_var       = tk.BooleanVar(value=True)
        self.lighthouses_var = tk.BooleanVar(value=True)
        self.ports_var       = tk.BooleanVar(value=True)
        self.bridges_var     = tk.BooleanVar(value=True)
        self.roads_var       = tk.BooleanVar(value=True)

        self._build_ui()

    def _on_closing(self):
        try:
            import matplotlib.pyplot as plt
            plt.close('all')  
        except ImportError:
            pass
        self.root.quit()
        self.root.destroy()
        os._exit(0)  

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG, pady=16)
        header.pack(fill="x", padx=24)

        tk.Label(header, text="⚔  ГЕНЕРАТОР КАРТ", bg=BG,
                 fg=ACCENT2, font=("Courier", 22, "bold")).pack()

        self._separator()

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", padx=24, pady=4)

        left  = tk.Frame(main, bg=BG)
        right = tk.Frame(main, bg=BG)
        left.pack(side="left", padx=(0, 16), anchor="n")
        right.pack(side="left", anchor="n")

        self._section(left, "  ПАРАМЕТРИ КАРТИ")

        self._slider_row(
            left, label="Кількість островів", var=self.islands_var,
            from_=3, to=5, desc=""
        )
        self._slider_row(
            left, label="Кількість архіпелагів", var=self.clusters_var,
            from_=3, to=5, desc=""
        )

        seed_frame = tk.Frame(left, bg=BG2, padx=12, pady=10)
        seed_frame.pack(fill="x", pady=(0, 8))
        tk.Label(seed_frame, text="Початкова точка:", bg=BG2, fg=TEXT, 
                 font=("Courier", 10, "bold")).pack(side="left")
        tk.Entry(seed_frame, textvariable=self.seed_var, bg=SLIDER_BG, fg=ACCENT2, 
                 font=("Courier", 11, "bold"), insertbackground=TEXT, 
                 relief="flat", width=12, justify="center").pack(side="right")
        tk.Label(seed_frame, text="(залиште пустим)", bg=BG2, fg=TEXT_DIM, 
                 font=("Courier", 8)).pack(side="right", padx=8)

        info = tk.Frame(left, bg=BG2, padx=12, pady=10)
        info.pack(fill="x", pady=(10, 0))
        tk.Label(info, text="👥  Гравців: 2",
                 bg=BG2, fg=ACCENT, font=("Courier", 10, "bold")).pack(anchor="w")

        self._section(right, "  ОБ'ЄКТИ НА КАРТІ")
        self._subtitle(right, "Інфраструктура")

        infra_items = [
            (self.ports_var,   "⚓", "Порти",  "Пірс + якір + флагшток на берегах"),
            (self.bridges_var, "🌉", "Мости",  "З'єднують сусідні острови"),
            (self.roads_var,   "🛤", "Дороги", "Від берега до центру кожного острова"),
        ]
        for var, icon, name, tip in infra_items:
            self._checkbox_row(right, var, icon, name, tip)

        self._subtitle(right, "Природа та будівлі")

        nature_items = [
            (self.lighthouses_var, "🔦", "Маяки",   "На головних островах гравців"),
            (self.buildings_var,   "🏠", "Будівлі", "Будинки з кольоровими дахами"),
            (self.trees_var,       "🌲", "Дерева",  "Вздовж берегів островів"),
            (self.rocks_var,       "🪨", "Скелі",   "Кам'яні виходи на поверхні"),
        ]
        for var, icon, name, tip in nature_items:
            self._checkbox_row(right, var, icon, name, tip)

        btn_row = tk.Frame(right, bg=BG)
        btn_row.pack(fill="x", pady=(8, 0))
        tk.Button(btn_row, text="Вибрати все", bg=SLIDER_BG, fg=TEXT_DIM,
                  font=("Courier", 9), relief="flat", cursor="hand2",
                  command=self._select_all, activebackground=BTN_HOV, activeforeground=TEXT
                  ).pack(side="left", padx=(0, 6))
        tk.Button(btn_row, text="Зняти все", bg=SLIDER_BG, fg=TEXT_DIM,
                  font=("Courier", 9), relief="flat", cursor="hand2",
                  command=self._deselect_all, activebackground=BTN_HOV, activeforeground=TEXT
                  ).pack(side="left")

        self._separator()

        btn_frame = tk.Frame(self.root, bg=BG, pady=8)
        btn_frame.pack(fill="x", padx=24)

        self.gen_btn = tk.Button(
            btn_frame, text="  ⚔   ГЕНЕРУВАТИ КАРТУ   ⚔  ",
            bg=BTN_BG, fg=ACCENT2, font=("Courier", 14, "bold"),
            relief="flat", cursor="hand2", padx=20, pady=12,
            command=self._on_generate, activebackground=BTN_ACT, activeforeground=ACCENT2,
        )
        self.gen_btn.pack(fill="x")
        self.gen_btn.bind("<Enter>", lambda e: self.gen_btn.config(bg=BTN_HOV))
        self.gen_btn.bind("<Leave>", lambda e: self.gen_btn.config(bg=BTN_BG))

        self._separator()

        status_frame = tk.Frame(self.root, bg=BG2, pady=8)
        status_frame.pack(fill="x", padx=24, pady=(0, 16))

        self.status_var = tk.StringVar(value="Готово до генерації")
        self.status_lbl = tk.Label(
            status_frame, textvariable=self.status_var,
            bg=BG2, fg=GREEN, font=("Courier", 10), anchor="w", padx=12,
        )
        self.status_lbl.pack(fill="x")

    def _separator(self):
        tk.Frame(self.root, bg=ACCENT, height=1).pack(fill="x", padx=24, pady=6)

    def _section(self, parent, title):
        tk.Label(parent, text=title, bg=BG, fg=ACCENT,
                 font=("Courier", 11, "bold")).pack(anchor="w", pady=(0, 8))

    def _subtitle(self, parent, text):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", pady=(10, 4))
        tk.Label(f, text=text, bg=BG, fg=TEXT_DIM, font=("Courier", 9, "italic")).pack(side="left")
        tk.Frame(f, bg=SLIDER_BG, height=1).pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _slider_row(self, parent, label, var, from_, to, desc):
        frame = tk.Frame(parent, bg=BG2, padx=12, pady=10)
        frame.pack(fill="x", pady=(0, 8))
        top = tk.Frame(frame, bg=BG2)
        top.pack(fill="x")
        tk.Label(top, text=label, bg=BG2, fg=TEXT, font=("Courier", 10, "bold")).pack(side="left")
        val_lbl = tk.Label(top, text=str(var.get()), bg=BG2, fg=ACCENT2, font=("Courier", 13, "bold"), width=2)
        val_lbl.pack(side="right")
        def on_change(v): val_lbl.config(text=str(int(float(v))))
        scale = tk.Scale(frame, variable=var, from_=from_, to=to, orient="horizontal",
                         bg=BG2, fg=TEXT, troughcolor=SLIDER_BG, highlightthickness=0, bd=0,
                         sliderrelief="flat", sliderlength=20, activebackground=ACCENT,
                         showvalue=False, command=on_change, length=220)
        scale.pack(fill="x", pady=(4, 2))
        lbl_row = tk.Frame(frame, bg=BG2)
        lbl_row.pack(fill="x")
        tk.Label(lbl_row, text=str(from_), bg=BG2, fg=TEXT_DIM, font=("Courier", 8)).pack(side="left")
        tk.Label(lbl_row, text=str(to), bg=BG2, fg=TEXT_DIM, font=("Courier", 8)).pack(side="right")
        tk.Label(frame, text=desc, bg=BG2, fg=TEXT_DIM, font=("Courier", 8), anchor="w").pack(fill="x", pady=(4, 0))

    def _checkbox_row(self, parent, var, icon, name, tip):
        frame = tk.Frame(parent, bg=BG, pady=3)
        frame.pack(fill="x")
        cb = tk.Checkbutton(frame, variable=var, bg=BG, fg=TEXT, selectcolor=SLIDER_BG,
                            activebackground=BG, activeforeground=ACCENT2, highlightthickness=0,
                            relief="flat", cursor="hand2")
        cb.pack(side="left")
        tk.Label(frame, text=f"{icon}  {name}", bg=BG, fg=TEXT, font=("Courier", 10, "bold"), width=14, anchor="w").pack(side="left")
        tk.Label(frame, text=tip, bg=BG, fg=TEXT_DIM, font=("Courier", 9), anchor="w").pack(side="left", padx=(4, 0))

    def _select_all(self):
        for v in [self.buildings_var, self.trees_var, self.rocks_var, self.lighthouses_var, self.ports_var, self.bridges_var, self.roads_var]: v.set(True)

    def _deselect_all(self):
        for v in [self.buildings_var, self.trees_var, self.rocks_var, self.lighthouses_var, self.ports_var, self.bridges_var, self.roads_var]: v.set(False)

    def _set_status(self, text, color=GREEN):
        self.status_var.set(text)
        self.status_lbl.config(fg=color)

    def _on_generate(self):
        self.gen_btn.config(state="disabled", text="  ⏳  Генерується...  ")
        self._set_status("Генерація карти...", ACCENT)

        seed_val = self.seed_var.get().strip()
        seed_int = int(seed_val) if seed_val.isdigit() else None

        params = {
            "islands":      self.islands_var.get(),
            "clusters":     self.clusters_var.get(),
            "seed":         seed_int, 
            "buildings":    self.buildings_var.get(),
            "trees":        self.trees_var.get(),
            "rocks":        self.rocks_var.get(),
            "lighthouses":  self.lighthouses_var.get(),
            "ports":        self.ports_var.get(),
            "bridges":      self.bridges_var.get(),
            "roads":        self.roads_var.get(),
        }

        thread = threading.Thread(target=self._run_generation, args=(params,), daemon=True)
        thread.start()

    def _run_generation(self, params):
        try:
            self.root.after(0, lambda: self._set_status("Імпорт модуля генератора...", ACCENT))

            import importlib
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if script_dir not in sys.path:
                sys.path.insert(0, script_dir)

            gen_module_name = None
            for name in ["islands"]:
                if os.path.exists(os.path.join(script_dir, f"{name}.py")):
                    gen_module_name = name
                    break

            if gen_module_name is None:
                self.root.after(0, lambda: self._set_status("✗ Файл islands.py не знайдено поряд з map_gui.py", RED))
                self.root.after(0, self._reset_button)
                return

            gen = importlib.import_module(gen_module_name)
            importlib.reload(gen)

            self.root.after(0, lambda: self._set_status(f"Генерація: {params['islands']} острів(и), {params['clusters']} кластер(и)...", ACCENT))

            regions, cluster_groups = gen.generate_map(
                params["islands"], 
                params["clusters"], 
                seed=params.get("seed")
            )

            if regions is None:
                self.root.after(0, lambda: self._set_status("✗ Не вдалося згенерувати карту. Спробуй ще раз.", RED))
                self.root.after(0, self._reset_button)
                return

            self.root.after(0, lambda: self._set_status("Візуалізація...", ACCENT))

            _apply_params(gen, params)
            gen.visualize(regions, cluster_groups)

            p = [r for r in regions if r.type == "player"]
            diff = abs(p[0].area - p[1].area)
            self.root.after(0, lambda: self._set_status(f"✓ Готово! Гравці: {p[0].area:.3f} / {p[1].area:.3f}  (різниця {diff:.3f})", GREEN))

        except Exception as e:
            msg = str(e)
            self.root.after(0, lambda: self._set_status(f"✗ Помилка: {msg}", RED))
        finally:
            self.root.after(0, self._reset_button)

    def _reset_button(self):
        self.gen_btn.config(state="normal", text="     ГЕНЕРУВАТИ КАРТУ     ")


def _apply_params(gen, params):
    noop = lambda *a, **kw: None
    if not params["roads"]: gen.draw_roads = noop
    if not params["bridges"]: gen.bridges_between_islands = noop
    if not params["ports"]: gen.draw_port = noop

    if not all([params["buildings"], params["trees"], params["rocks"], params["lighthouses"]]):
        def patched_populate(ax, island, rtype, is_main, zorder=9):
            import random
            import numpy as np
            from shapely.geometry import Point
            try:
                minx, miny, maxx, maxy = island.bounds
                cx, cy = island.centroid.x, island.centroid.y
                placed = []

                def can_place(x, y, r):
                    return (island.contains(Point(x, y)) and
                            all(np.hypot(x-px, y-py) > r+pr for px, py, pr in placed))

                def try_place(draw_fn, r_excl, n_tries=50, **kwargs):
                    for _ in range(n_tries):
                        rx = random.uniform(minx+r_excl, maxx-r_excl)
                        ry = random.uniform(miny+r_excl, maxy-r_excl)
                        if can_place(rx, ry, r_excl):
                            draw_fn(ax, rx, ry, zorder=zorder, **kwargs)
                            placed.append((rx, ry, r_excl))
                            return True
                    return False

                if params["lighthouses"] and is_main and rtype in ("player", "island"):
                    lx = cx + (maxx-minx)*0.05
                    ly = cy + (maxy-miny)*0.08
                    beam = {"player": "#FF6F00", "island": "#40C4FF"}.get(rtype, "#FFD600")
                    gen.draw_lighthouse(ax, lx, ly, beam_color=beam, zorder=zorder+2)
                    placed.append((lx, ly, 0.025))

                if params["buildings"]:
                    n_b = {"player":6,"island":4,"cluster_center":5,"cluster_satellite":2}
                    n_buildings = n_b.get(rtype,3) if is_main else max(1,n_b.get(rtype,3)//2)
                    roof_colors = {"player": "#B71C1C", "island": "#5D4037", "cluster_center": "#5D4037", "cluster_satellite": "#5D4037"}
                    roof = roof_colors.get(rtype,"#E53935")
                    for _ in range(n_buildings):
                        sz   = random.uniform(0.009, 0.013)
                        wall = random.choice(["#CFD8DC","#ECEFF1","#E8EAF6","#FFF3E0"])
                        try_place(gen.draw_building, r_excl=0.017, n_tries=60, sz=sz, wall=wall, roof=roof)

                if params["trees"]:
                    n_trees = random.randint(4,9) if is_main else random.randint(1,4)
                    tree_colors = ["#388E3C","#2E7D32","#43A047","#1B5E20","#558B2F"]
                    for _ in range(n_trees):
                        sz    = random.uniform(0.009, 0.013)
                        color = random.choice(tree_colors)
                        placed_tree = False
                        for _ in range(60):
                            angle = random.uniform(0, 2*np.pi)
                            frac  = random.uniform(0.45, 0.88)
                            r_isl = min(maxx-minx, maxy-miny) * frac * 0.48
                            rx, ry = cx + r_isl*np.cos(angle), cy + r_isl*np.sin(angle)
                            if can_place(rx, ry, 0.013):
                                gen.draw_tree(ax, rx, ry, sz=sz, color=color, zorder=zorder)
                                placed.append((rx, ry, 0.013))
                                placed_tree = True
                                break
                        if not placed_tree:
                            try_place(gen.draw_tree, r_excl=0.012, n_tries=30, sz=sz, color=color)

                if params["rocks"]:
                    n_rocks = random.randint(2,4) if is_main else 1
                    for _ in range(n_rocks):
                        sz = random.uniform(0.006, 0.010)
                        try_place(gen.draw_rock, r_excl=0.012, n_tries=40, sz=sz)
            except Exception:
                pass
        gen.populate_island = patched_populate

def main():
    root = tk.Tk()
    root.configure(bg=BG)
    root.minsize(680, 500)
    app = MapGeneratorGUI(root)
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth()  - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"+{x}+{y}")
    root.mainloop()

if __name__ == "__main__":
    main()