import sys
import unittest
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Step:
    index: int
    page: int
    frames: List[Optional[int]]
    hit: bool
    replaced: Optional[int] = None
    reason: str = ""


@dataclass
class SimulationResult:
    algorithm: str
    reference_string: List[int]
    num_frames: int
    steps: List[Step] = field(default_factory=list)

    @property
    def hits(self) -> int:
        return sum(1 for s in self.steps if s.hit)

    @property
    def faults(self) -> int:
        return sum(1 for s in self.steps if not s.hit)

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def hit_ratio(self) -> float:
        return self.hits / self.total if self.total else 0.0

    @property
    def fault_ratio(self) -> float:
        return self.faults / self.total if self.total else 0.0

    @property
    def final_frames(self) -> List[Optional[int]]:
        return list(self.steps[-1].frames) if self.steps else [None] * self.num_frames


def parse_reference_string(text: str) -> List[int]:
    tokens = text.replace(",", " ").split()
    if not tokens:
        raise ValueError("Reference string is empty.")
    pages = []
    for token in tokens:
        try:
            value = int(token)
        except ValueError:
            raise ValueError(f"'{token}' is not a valid integer page number.")
        if value < 0:
            raise ValueError(f"Page number {value} is negative.")
        pages.append(value)
    return pages


def validate_frames(value) -> int:
    try:
        n = int(value)
    except (ValueError, TypeError):
        raise ValueError("Number of frames must be an integer.")
    if n < 1:
        raise ValueError("Number of frames must be at least 1.")
    return n


def fifo(refs: List[int], num_frames: int) -> SimulationResult:
    result = SimulationResult("FIFO", list(refs), num_frames)
    frames: List[Optional[int]] = [None] * num_frames
    next_victim = 0

    for i, page in enumerate(refs, start=1):
        if page in frames:
            result.steps.append(Step(i, page, list(frames), True,
                                     reason="Page already in memory"))
        elif None in frames:
            frames[frames.index(None)] = page
            result.steps.append(Step(i, page, list(frames), False,
                                     reason="Free frame available"))
        else:
            victim = frames[next_victim]
            frames[next_victim] = page
            next_victim = (next_victim + 1) % num_frames
            result.steps.append(Step(i, page, list(frames), False, victim,
                                     f"Replaced oldest page {victim}"))
    return result


def lru(refs: List[int], num_frames: int) -> SimulationResult:
    result = SimulationResult("LRU", list(refs), num_frames)
    frames: List[Optional[int]] = [None] * num_frames
    last_used = {}

    for i, page in enumerate(refs, start=1):
        if page in frames:
            last_used[page] = i
            result.steps.append(Step(i, page, list(frames), True,
                                     reason="Page already in memory (recency updated)"))
        elif None in frames:
            frames[frames.index(None)] = page
            last_used[page] = i
            result.steps.append(Step(i, page, list(frames), False,
                                     reason="Free frame available"))
        else:
            slot = min(range(num_frames), key=lambda s: last_used[frames[s]])
            victim = frames[slot]
            victim_last = last_used[victim]
            frames[slot] = page
            last_used[page] = i
            result.steps.append(Step(i, page, list(frames), False, victim,
                                     f"Replaced least recently used page {victim} "
                                     f"(last used at ref {victim_last})"))
    return result


def optimal(refs: List[int], num_frames: int) -> SimulationResult:
    result = SimulationResult("Optimal", list(refs), num_frames)
    frames: List[Optional[int]] = [None] * num_frames
    load_time = {}

    for i, page in enumerate(refs, start=1):
        if page in frames:
            result.steps.append(Step(i, page, list(frames), True,
                                     reason="Page already in memory"))
            continue
        if None in frames:
            frames[frames.index(None)] = page
            load_time[page] = i
            result.steps.append(Step(i, page, list(frames), False,
                                     reason="Free frame available"))
            continue

        future = refs[i:]
        best_slot, best_key, best_next = None, None, None
        for s in range(num_frames):
            p = frames[s]
            if p in future:
                nxt = future.index(p) + i + 1
                key = (nxt, 0)
            else:
                nxt = None
                key = (float("inf"), -load_time[p])
            if best_key is None or key > best_key:
                best_slot, best_key, best_next = s, key, nxt

        victim = frames[best_slot]
        frames[best_slot] = page
        load_time[page] = i
        if best_next is None:
            why = f"Replaced page {victim} (never used again)"
        else:
            why = f"Replaced page {victim} (next used at ref {best_next}, farthest)"
        result.steps.append(Step(i, page, list(frames), False, victim, why))
    return result


ALGORITHMS = {"FIFO": fifo, "LRU": lru, "Optimal": optimal}


def run_all(refs: List[int], num_frames: int):
    return [fn(refs, num_frames) for fn in ALGORITHMS.values()]


def best_algorithm(results) -> str:
    fewest = min(r.faults for r in results)
    return ", ".join(r.algorithm for r in results if r.faults == fewest)


DEFAULT_REFS = "7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1"
DEFAULT_FRAMES = "3"


def fmt_frames(frames):
    return " | ".join(f"{'-' if f is None else f:>2}" for f in frames)


def render_trace(result) -> str:
    n = result.num_frames
    lines = [f"=== {result.algorithm} ===",
             f"Reference string : {' '.join(map(str, result.reference_string))}",
             f"Page frames      : {n}", ""]
    header = (f"{'Ref':>3}  {'Page':>4}  "
              + "  ".join(f"F{k + 1:<2}" for k in range(n))
              + "  Result  Note")
    lines.append(header)
    lines.append("-" * len(header) + "-" * 30)
    for s in result.steps:
        cells = "  ".join(f"{'-' if f is None else f:>3}" for f in s.frames)
        lines.append(f"{s.index:>3}  {s.page:>4}  {cells}  "
                     f"{'HIT  ' if s.hit else 'FAULT'}   {s.reason}")
    lines.append("")
    lines.append(f"Final frames : [{fmt_frames(result.final_frames)}]")
    lines.append(f"Total hits   : {result.hits}")
    lines.append(f"Total faults : {result.faults}")
    lines.append(f"Hit ratio    : {result.hit_ratio * 100:.2f}%   "
                 f"Fault ratio : {result.fault_ratio * 100:.2f}%")
    return "\n".join(lines)


def render_comparison(results) -> str:
    lines = ["=== COMPARISON ===",
             f"{'Algorithm':<10} {'Hits':>5} {'Faults':>7} {'Hit %':>8} {'Fault %':>8}",
             "-" * 42]
    for r in results:
        lines.append(f"{r.algorithm:<10} {r.hits:>5} {r.faults:>7} "
                     f"{r.hit_ratio * 100:>7.2f}% {r.fault_ratio * 100:>7.2f}%")
    lines.append("")
    lines.append(f"Fewest page faults: {best_algorithm(results)}")
    lines.append("Optimal gives the theoretical minimum faults; LRU approximates it "
                 "using past usage; FIFO ignores usage and may suffer Belady's anomaly.")
    return "\n".join(lines)


def read_inputs_cli():
    while True:
        try:
            refs = parse_reference_string(
                input(f"Enter page-reference string [{DEFAULT_REFS}]: ").strip() or DEFAULT_REFS)
            frames = validate_frames(
                input(f"Enter number of page frames [{DEFAULT_FRAMES}]: ").strip() or DEFAULT_FRAMES)
            return refs, frames
        except ValueError as e:
            print(f"  Invalid input: {e}\n")


def cli():
    menu = ("\n" + "=" * 36 + "\n PAGE REPLACEMENT SIMULATOR\n" + "=" * 36 +
            "\n1. FIFO\n2. LRU\n3. Optimal\n4. Compare All Algorithms\n5. Exit\n")
    names = list(ALGORITHMS)
    while True:
        print(menu)
        choice = input("Select option: ").strip()
        if choice == "5":
            print("Goodbye!")
            return
        if choice not in {"1", "2", "3", "4"}:
            print("Invalid option. Choose 1-5.")
            continue
        refs, frames = read_inputs_cli()
        if choice == "4":
            results = run_all(refs, frames)
            for r in results:
                print("\n" + render_trace(r))
            print("\n" + render_comparison(results))
        else:
            r = ALGORITHMS[names[int(choice) - 1]](refs, frames)
            print("\n" + render_trace(r))


def gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, font as tkfont

    BG = "#f5f7fb"
    CARD = "#ffffff"
    BORDER = "#e3e8f2"
    TRACK = "#eceff6"
    CELL = "#f6f8fc"
    TEXT = "#1b2236"
    MUTED = "#6b7692"
    ACCENT = "#4c6ef5"
    ACCENT_DARK = "#3b5bdb"
    HIT = "#2f9e44"
    HIT_DARK = "#237032"
    HIT_LIGHT = "#d3f9d8"
    FAULT = "#e03131"
    FAULT_LIGHT = "#ffe3e3"

    root = tk.Tk()
    root.title("Page Replacement Simulator")
    root.geometry("1040x760")
    root.minsize(900, 640)
    root.configure(bg=BG)

    def make_icon(size=32):
        icon = tk.PhotoImage(width=size, height=size)
        radius = 8
        for y in range(size):
            edge = min(y + 0.5, size - y - 0.5)
            inset = 0
            if edge < radius:
                inset = round(radius - (radius ** 2 - (radius - edge) ** 2) ** 0.5)
            icon.put(ACCENT, to=(inset, y, size - inset, y + 1))
        for x, y, color in ((6, 6, "#ffffff"), (17, 6, "#8ce99a"),
                            (6, 17, "#ff8787"), (17, 17, "#ffffff")):
            icon.put(color, to=(x, y, x + 9, y + 9))
        return icon

    app_icon = make_icon()
    root.iconphoto(True, app_icon)

    available = set(tkfont.families())
    family = next((f for f in ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Ubuntu", "DejaVu Sans")
                   if f in available), tkfont.nametofont("TkDefaultFont").actual("family"))

    def font(size=10, weight="normal"):
        return (family, size, weight)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=TEXT, font=font())
    style.configure("TFrame", background=BG)
    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab", padding=(24, 10), background=TRACK,
                    foreground=MUTED, borderwidth=0, font=font(10, "bold"))
    style.map("TNotebook.Tab", background=[("selected", CARD)],
              foreground=[("selected", ACCENT_DARK)])
    for orient in ("Vertical", "Horizontal"):
        style.configure(f"{orient}.TScrollbar", background=TRACK, troughcolor=CARD,
                        bordercolor=CARD, lightcolor=TRACK, darkcolor=TRACK,
                        arrowcolor=MUTED)

    refs_var = tk.StringVar(value=DEFAULT_REFS)
    frames_var = tk.StringVar(value=DEFAULT_FRAMES)
    algo_var = tk.StringVar(value="Compare All")
    status_var = tk.StringVar(value="Pick an algorithm and press Run.")

    def make_button(parent, text, command, bg, hover, fg="white"):
        label = tk.Label(parent, text=text, bg=bg, fg=fg, font=font(10, "bold"),
                         padx=18, pady=10, cursor="hand2")
        label.bind("<Button-1>", lambda e: command())
        label.bind("<Enter>", lambda e: label.configure(bg=hover))
        label.bind("<Leave>", lambda e: label.configure(bg=bg))
        return label

    def make_segmented(parent, options, var):
        labels = {}

        def refresh(*_):
            for option, label in labels.items():
                selected = var.get() == option
                label.configure(bg=CARD if selected else TRACK,
                                fg=ACCENT_DARK if selected else MUTED)

        for option in options:
            label = tk.Label(parent, text=option, bg=TRACK, fg=MUTED, padx=14, pady=7,
                             font=font(10, "bold"), cursor="hand2")
            label.pack(side="left", padx=3, pady=3)
            label.bind("<Button-1>", lambda e, o=option: var.set(o))
            labels[option] = label
        var.trace_add("write", refresh)
        refresh()

    tk.Label(root, text="Page Replacement Simulator", bg=BG, fg=TEXT, anchor="w",
             font=font(18, "bold")).pack(fill="x", padx=28, pady=(22, 0))
    tk.Label(root, text="Compare FIFO, LRU and Optimal on any page-reference string",
             bg=BG, fg=MUTED, anchor="w", font=font(10)).pack(fill="x", padx=28)

    card = tk.Frame(root, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
    card.pack(fill="x", padx=28, pady=(16, 0))
    form = tk.Frame(card, bg=CARD)
    form.pack(fill="x", padx=18, pady=16)
    form.columnconfigure(0, weight=1)

    def field_label(text, column, left):
        tk.Label(form, text=text, bg=CARD, fg=MUTED, anchor="w",
                 font=font(8, "bold")).grid(row=0, column=column, sticky="w", padx=(left, 0))

    field_label("PAGE-REFERENCE STRING", 0, 0)
    field_label("FRAMES", 1, 16)
    field_label("ALGORITHM", 2, 16)

    tk.Entry(form, textvariable=refs_var, bg=CARD, fg=TEXT, insertbackground=TEXT,
             relief="flat", font=font(11), highlightthickness=1,
             highlightbackground=BORDER, highlightcolor=ACCENT).grid(
        row=1, column=0, sticky="we", pady=(6, 0), ipady=8)
    tk.Spinbox(form, from_=1, to=20, textvariable=frames_var, width=5, bg=CARD, fg=TEXT,
               insertbackground=TEXT, relief="flat", font=font(11), highlightthickness=1,
               highlightbackground=BORDER, highlightcolor=ACCENT).grid(
        row=1, column=1, sticky="ns", padx=(16, 0), pady=(6, 0), ipady=8)
    segmented = tk.Frame(form, bg=TRACK)
    segmented.grid(row=1, column=2, padx=(16, 0), pady=(6, 0))
    make_segmented(segmented, ["FIFO", "LRU", "Optimal", "Compare All"], algo_var)
    buttons = tk.Frame(form, bg=CARD)
    buttons.grid(row=1, column=3, padx=(16, 0), pady=(6, 0))

    status_label = tk.Label(root, textvariable=status_var, bg=BG, fg=MUTED, anchor="w",
                            font=font(10))
    status_label.pack(fill="x", padx=28, pady=(10, 0))

    results = tk.Frame(root, bg=BG)
    results.pack(fill="both", expand=True, padx=28, pady=(10, 22))
    notebook = ttk.Notebook(results)
    notebook.pack(fill="both", expand=True)

    placeholder = tk.Frame(results, bg=BG)
    tk.Label(placeholder, text="No simulation yet", bg=BG, fg=TEXT,
             font=font(15, "bold")).pack()
    tk.Label(placeholder, text="Press Run to see the results here.", bg=BG, fg=MUTED,
             font=font(11)).pack(pady=(4, 0))

    def show_placeholder():
        placeholder.place(relx=0.5, rely=0.5, anchor="center")
        placeholder.lift()

    def hide_placeholder():
        placeholder.place_forget()

    scrollers = {}

    def clear_tabs():
        for tab in notebook.tabs():
            widget = root.nametowidget(tab)
            notebook.forget(tab)
            widget.destroy()
        scrollers.clear()

    def add_scrolling_tab(title):
        outer = ttk.Frame(notebook)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0, yscrollincrement=20)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(canvas, padding=(0, 14, 14, 0))
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        notebook.add(outer, text=title)
        scrollers[str(outer)] = canvas
        return inner

    def on_wheel(event):
        canvas = scrollers.get(str(notebook.select()))
        if canvas is None:
            return
        if event.num == 4:
            step = -3
        elif event.num == 5:
            step = 3
        else:
            step = -3 if event.delta > 0 else 3
        canvas.yview_scroll(step, "units")

    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        root.bind_all(sequence, on_wheel)

    def set_status(text, error=False):
        status_var.set(text)
        status_label.configure(fg=FAULT if error else MUTED)

    def section(parent, text):
        return tk.Label(parent, text=text, bg=BG, fg=TEXT, anchor="w", font=font(11, "bold"))

    def stat_card(parent, caption, value, color):
        box = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        tk.Frame(box, bg=color, height=3).pack(fill="x")
        tk.Label(box, text=value, font=font(22, "bold"), fg=color, bg=CARD,
                 anchor="w").pack(fill="x", padx=14, pady=(8, 0))
        tk.Label(box, text=caption.upper(), font=font(8, "bold"), fg=MUTED, bg=CARD,
                 anchor="w").pack(fill="x", padx=14, pady=(0, 10))
        return box

    def draw_trace(canvas, result, cw, ch, label_w, pad, total_w, total_h):
        n = result.num_frames
        canvas.delete("all")

        def cell(col, row, fill, text, fg, weight="normal"):
            x0 = pad + label_w + col * cw + 3
            y0 = pad + row * ch + 3
            canvas.create_rectangle(x0, y0, x0 + cw - 6, y0 + ch - 6, fill=fill, outline="")
            canvas.create_text(x0 + (cw - 6) / 2, y0 + (ch - 6) / 2, text=text,
                               fill=fg, font=font(10, weight))

        def row_label(row, text):
            canvas.create_text(pad, pad + row * ch + ch / 2, text=text, anchor="w",
                               fill=MUTED, font=font(9, "bold"))

        row_label(0, "Reference")
        for r in range(1, n + 1):
            row_label(r, f"Frame {r}")
        row_label(n + 1, "Result")

        for col, s in enumerate(result.steps):
            cell(col, 0, "#e7ecfb", str(s.page), ACCENT_DARK, "bold")
            for r in range(1, n + 1):
                value = s.frames[r - 1]
                if value is None:
                    cell(col, r, CELL, "-", "#b9c0d4")
                elif value == s.page:
                    cell(col, r, HIT_LIGHT if s.hit else FAULT_LIGHT, str(value),
                         HIT_DARK if s.hit else FAULT, "bold")
                else:
                    cell(col, r, CELL, str(value), TEXT)
            cell(col, n + 1, HIT if s.hit else FAULT, "H" if s.hit else "F", "white", "bold")

        canvas.configure(scrollregion=(0, 0, total_w, total_h))

    def round_rect(canvas, x0, y0, x1, y1, radius, fill):
        points = [x0 + radius, y0, x1 - radius, y0, x1, y0, x1, y0 + radius,
                  x1, y1 - radius, x1, y1, x1 - radius, y1, x0 + radius, y1,
                  x0, y1, x0, y1 - radius, x0, y0 + radius, x0, y0]
        canvas.create_polygon(points, smooth=True, fill=fill, outline="")

    def log_layout(n):
        per_line = min(n, 8)
        lines = -(-n // per_line)
        return per_line, lines, max(44, lines * 34 + 14)

    def draw_log(canvas, result):
        canvas.delete("all")
        width = canvas.winfo_width()
        if width < 200:
            return
        n = result.num_frames
        head_h, chip_w, chip_h, gap = 34, 34, 28, 6
        per_line, lines, row_h = log_layout(n)
        page_c = 46
        frames_x = 100
        frames_w = max(140, per_line * (chip_w + gap))
        result_x = frames_x + frames_w + 16
        evicted_c = result_x + 62 + 16 + 32
        note_x = evicted_c + 32 + 16

        canvas.create_rectangle(0, 0, width, head_h, fill="#eef1f8", outline="")
        for x, text, anchor in ((page_c, "Page", "center"),
                                (frames_x, "Frames after step", "w"),
                                (result_x, "Result", "w"),
                                (evicted_c, "Evicted", "center"),
                                (note_x, "Explanation", "w")):
            canvas.create_text(x, head_h / 2, text=text, anchor=anchor, fill=TEXT,
                               font=font(9, "bold"))

        for i, s in enumerate(result.steps):
            top = head_h + i * row_h
            mid = top + row_h / 2
            canvas.create_rectangle(0, top, width, top + row_h,
                                    fill="#f3fcf5" if s.hit else "#fff6f6", outline="")
            canvas.create_line(0, top + row_h, width, top + row_h, fill=BORDER)
            canvas.create_text(page_c, mid, text=str(s.page), fill=ACCENT_DARK,
                               font=font(12, "bold"))

            for k, value in enumerate(s.frames):
                x0 = frames_x + (k % per_line) * (chip_w + gap)
                cy = mid - (lines * (chip_h + gap) - gap) / 2 + (k // per_line) * (chip_h + gap) + chip_h / 2
                if value is None:
                    fill, fg, text, weight = TRACK, "#b9c0d4", "-", "normal"
                elif value == s.page:
                    fill, fg, text, weight = (HIT if s.hit else FAULT), "white", str(value), "bold"
                else:
                    fill, fg, text, weight = CARD, TEXT, str(value), "normal"
                round_rect(canvas, x0, cy - chip_h / 2, x0 + chip_w, cy + chip_h / 2, 9, fill)
                canvas.create_text(x0 + chip_w / 2, cy, text=text, fill=fg, font=font(11, weight))

            round_rect(canvas, result_x, mid - 12, result_x + 62, mid + 12, 12,
                       HIT if s.hit else FAULT)
            canvas.create_text(result_x + 31, mid, text="HIT" if s.hit else "FAULT",
                               fill="white", font=font(9, "bold"))
            if s.replaced is None:
                canvas.create_text(evicted_c, mid, text="-", fill="#b9c0d4", font=font(11))
            else:
                canvas.create_text(evicted_c, mid, text=str(s.replaced), fill=FAULT,
                                   font=font(11, "bold"))
            canvas.create_text(note_x, mid, text=s.reason, anchor="w", fill=TEXT, font=font(9))

    def build_trace_tab(result):
        page = add_scrolling_tab(result.algorithm)
        n = result.num_frames

        stats = ttk.Frame(page)
        stats.pack(fill="x")
        items = [("Page hits", str(result.hits), HIT),
                 ("Page faults", str(result.faults), FAULT),
                 ("Hit ratio", f"{result.hit_ratio * 100:.1f}%", HIT),
                 ("Fault ratio", f"{result.fault_ratio * 100:.1f}%", FAULT)]
        for col, (caption, value, color) in enumerate(items):
            stat_card(stats, caption, value, color).grid(
                row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 10, 0))
            stats.columnconfigure(col, weight=1, uniform="stat")

        final = " | ".join("-" if f is None else str(f) for f in result.final_frames)
        tk.Label(page, text=f"Final frames:  {final}", bg=BG, fg=MUTED, anchor="w",
                 font=font(10)).pack(fill="x", pady=(10, 0))

        grid_card = tk.Frame(page, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        grid_card.pack(fill="x", pady=(10, 0))
        grid_card.columnconfigure(0, weight=1)

        cw, ch, label_w, pad = 46, 36, 82, 12
        total_w = label_w + cw * len(result.steps) + pad * 2
        total_h = ch * (n + 2) + pad * 2
        canvas = tk.Canvas(grid_card, bg=CARD, highlightthickness=0, height=total_h)
        hbar = ttk.Scrollbar(grid_card, orient="horizontal", command=canvas.xview)
        canvas.configure(xscrollcommand=hbar.set)
        canvas.grid(row=0, column=0, sticky="ew")
        hbar.grid(row=1, column=0, sticky="ew")
        draw_trace(canvas, result, cw, ch, label_w, pad, total_w, total_h)

        section(page, "Step-by-step log").pack(fill="x", pady=(16, 6))
        log = tk.Canvas(page, bg=CARD, highlightbackground=BORDER, highlightthickness=1,
                        height=34 + log_layout(n)[2] * len(result.steps))
        log.pack(fill="x", pady=(0, 14))
        log.bind("<Configure>", lambda e: draw_log(log, result))

    def draw_bar(canvas, ratio):
        canvas.delete("all")
        width = canvas.winfo_width()
        canvas.create_rectangle(0, 0, width, 8, fill=TRACK, outline="")
        canvas.create_rectangle(0, 0, width * ratio, 8, fill=HIT, outline="")

    def build_comparison_tab(results_list):
        page = add_scrolling_tab("Comparison")
        fewest = min(r.faults for r in results_list)

        tk.Label(page, text=f"★  Fewest page faults: {best_algorithm(results_list)}",
                 bg=HIT_LIGHT, fg=HIT_DARK, font=font(11, "bold"), anchor="w",
                 padx=16, pady=10).pack(fill="x")

        cards = ttk.Frame(page)
        cards.pack(fill="x", pady=(14, 0))
        for col, r in enumerate(results_list):
            best = r.faults == fewest
            box = tk.Frame(cards, bg=CARD, highlightbackground=HIT if best else BORDER,
                           highlightthickness=2 if best else 1)
            box.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 10, 0))
            cards.columnconfigure(col, weight=1, uniform="algo")

            head = tk.Frame(box, bg=CARD)
            head.pack(fill="x", padx=16, pady=(14, 0))
            tk.Label(head, text=r.algorithm, bg=CARD, fg=TEXT,
                     font=font(13, "bold")).pack(side="left")
            if best:
                tk.Label(head, text="BEST", bg=HIT_LIGHT, fg=HIT_DARK, font=font(8, "bold"),
                         padx=8, pady=2).pack(side="right")

            tk.Label(box, text=str(r.faults), bg=CARD, fg=FAULT, anchor="w",
                     font=font(30, "bold")).pack(fill="x", padx=16, pady=(8, 0))
            tk.Label(box, text="PAGE FAULTS", bg=CARD, fg=MUTED, anchor="w",
                     font=font(8, "bold")).pack(fill="x", padx=16)

            bar = tk.Canvas(box, height=8, bg=TRACK, highlightthickness=0)
            bar.pack(fill="x", padx=16, pady=(14, 6))
            bar.bind("<Configure>", lambda e, c=bar, ratio=r.hit_ratio: draw_bar(c, ratio))
            tk.Label(box, text=f"{r.hits} hits  ·  {r.hit_ratio * 100:.1f}% hit ratio",
                     bg=CARD, fg=MUTED, anchor="w", font=font(9)).pack(
                fill="x", padx=16, pady=(0, 14))

        tk.Label(page, bg=BG, fg=MUTED, font=font(10), justify="left", anchor="w",
                 wraplength=900, text=(
                     "Optimal gives the theoretical minimum number of faults (it needs future knowledge). "
                     "LRU approximates it using past usage. FIFO ignores usage and can suffer "
                     "Belady's anomaly (more frames -> more faults).")).pack(fill="x", pady=(18, 0))

    def run():
        try:
            refs = parse_reference_string(refs_var.get())
            n = validate_frames(frames_var.get())
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            set_status(f"Error: {e}", error=True)
            return
        clear_tabs()
        hide_placeholder()
        choice = algo_var.get()
        if choice == "Compare All":
            results_list = run_all(refs, n)
            for r in results_list:
                build_trace_tab(r)
            build_comparison_tab(results_list)
            notebook.select(len(results_list))
        else:
            build_trace_tab(ALGORITHMS[choice](refs, n))
        set_status(f"Simulation completed: {len(refs)} references, {n} frame(s), {choice}.")

    def reset():
        refs_var.set(DEFAULT_REFS)
        frames_var.set(DEFAULT_FRAMES)
        algo_var.set("Compare All")
        clear_tabs()
        show_placeholder()
        set_status("Inputs reset.")

    make_button(buttons, "▶  Run", run, ACCENT, ACCENT_DARK).pack(side="left")
    make_button(buttons, "Reset", reset, TRACK, "#dfe4ef", MUTED).pack(side="left", padx=(8, 0))

    show_placeholder()
    root.bind("<Return>", lambda e: run())
    root.mainloop()


TC1 = parse_reference_string("7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1")
TC2 = parse_reference_string("1 2 3 4 1 2 5 1 2 3 4 5")
TC3 = parse_reference_string("2 3 2 1 5 2 4 5 3 2 5 2")


class TestAlgorithms(unittest.TestCase):
    def test_tc1_fifo(self):
        r = fifo(TC1, 3)
        self.assertEqual((r.faults, r.hits), (15, 5))

    def test_tc1_lru(self):
        r = lru(TC1, 3)
        self.assertEqual((r.faults, r.hits), (12, 8))

    def test_tc1_optimal(self):
        r = optimal(TC1, 3)
        self.assertEqual((r.faults, r.hits), (9, 11))

    def test_tc2_belady(self):
        self.assertEqual(fifo(TC2, 3).faults, 9)
        self.assertEqual(fifo(TC2, 4).faults, 10)

    def test_tc2_lru_optimal(self):
        self.assertEqual(lru(TC2, 3).faults, 10)
        self.assertEqual(optimal(TC2, 3).faults, 7)

    def test_tc3(self):
        self.assertEqual(fifo(TC3, 3).faults, 9)
        self.assertEqual(lru(TC3, 3).faults, 7)
        self.assertEqual(optimal(TC3, 3).faults, 6)

    def test_final_frames_fifo_tc1(self):
        self.assertEqual(sorted(fifo(TC1, 3).final_frames), [0, 1, 7])

    def test_hit_does_not_change_frames(self):
        r = fifo([1, 2, 1], 2)
        self.assertEqual(r.steps[1].frames, r.steps[2].frames)
        self.assertTrue(r.steps[2].hit)

    def test_single_frame_all_faults_unless_repeat(self):
        r = lru([1, 1, 2, 2, 1], 1)
        self.assertEqual((r.hits, r.faults), (2, 3))

    def test_optimal_never_worse(self):
        for refs in (TC1, TC2, TC3):
            for n in (1, 2, 3, 4):
                o = optimal(refs, n).faults
                self.assertLessEqual(o, fifo(refs, n).faults)
                self.assertLessEqual(o, lru(refs, n).faults)

    def test_validation(self):
        with self.assertRaises(ValueError):
            parse_reference_string("")
        with self.assertRaises(ValueError):
            parse_reference_string("1 a 3")
        with self.assertRaises(ValueError):
            parse_reference_string("1 -2")
        with self.assertRaises(ValueError):
            validate_frames("0")
        with self.assertRaises(ValueError):
            validate_frames("abc")
        self.assertEqual(parse_reference_string("1,2, 3"), [1, 2, 3])


if __name__ == "__main__":
    if "--test" in sys.argv:
        unittest.main(argv=[sys.argv[0], "-v"])
    elif "--cli" in sys.argv:
        cli()
    else:
        try:
            gui()
        except ImportError:
            print("tkinter is not available; starting console version.\n")
            cli()