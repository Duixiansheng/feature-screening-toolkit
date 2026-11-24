"""TerraFactor 5 desktop workspace."""
import csv
import json
import os
from pathlib import Path
from queue import Empty, SimpleQueue
import sys
from threading import Event, Thread
import tkinter as tk
from tkinter import filedialog, ttk

from data_audit import audit
from factor_project import ENGINE_REVISION, atomic_json, run_project
from fold_validation import evaluate
from method_comparison import DEFAULT_METHODS, RANKING_METHODS, compare_methods
from screening import METHODS

PAPER, WHITE, INK, MUTED = "#edf3ef", "#ffffff", "#172d29", "#4f635a"
ACCENT, SECOND = "#006857", "#66869e"
TABS = ("audit", "compare", "validate", "project")
TABLES = {
    "audit": (("因子", "类型", "缺失", "无效数值", "有效数值", "不同值", "中位数"), "数据体检"),
    "compare": (("因子", "支持数", "支持方法"), "方法对照"),
    "validate": (("折", "验证样本", "全因子 AP", "Top K AP", "AP 差值", "本折因子"), "留出验证"),
    "project": (("任务", "类型", "状态", "结果文件或错误"), "批量项目"),
}


class TableView:
    def __init__(self, parent, columns, has_chart):
        self.frame = ttk.Frame(parent, padding=12)
        self.columns = columns
        self.summary = tk.StringVar(value="运行后在这里查看结果。")
        ttk.Label(self.frame, textvariable=self.summary, foreground=MUTED,
                  wraplength=880).pack(fill="x", pady=(0, 8))
        if has_chart:
            self.chart = tk.Canvas(self.frame, height=140, background=WHITE, highlightthickness=0)
            self.chart.pack(fill="x", pady=(0, 9))
        else:
            self.chart = None
        container = ttk.Frame(self.frame)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
        vertical = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        for i, name in enumerate(columns):
            self.tree.heading(name, text=name, command=lambda n=i: self.sort(n))
            self.tree.column(name, minwidth=60, width=160 if i in (0, len(columns)-1) else 90)
        self.rows = []
        self.descending = False

    def replace(self, rows):
        self.rows = list(rows)
        self.tree.delete(*self.tree.get_children())
        for row in self.rows:
            self.tree.insert("", "end", values=row)

    def sort(self, index):
        def key(row):
            value = row[index]
            return (0, value) if isinstance(value, (float, int)) else (1, str(value))
        self.replace(sorted(self.rows, key=key, reverse=self.descending))
        self.descending = not self.descending


class TerraFactorStudio:
    def __init__(self, root):
        self.root = root
        self.source = self.project = None
        self.results = {}
        self.events = SimpleQueue()
        self.cancel = Event()
        self.running = False
        self.closing = False
        self.status = tk.StringVar(value="打开 CSV，或者打开一个 TerraFactor 项目。")
        self.filename = tk.StringVar(value="未打开 CSV")
        self.project_label = tk.StringVar(value="未打开项目")
        root.title("TerraFactor 5 · 地学因子分析")
        root.geometry("1060x730")
        root.minsize(910, 665)
        root.configure(background=PAPER)
        root.protocol("WM_DELETE_WINDOW", self.close)
        theme = ttk.Style(root)
        theme.theme_use("clam")
        theme.configure("TFrame", background=PAPER)
        theme.configure("TLabel", background=PAPER, foreground=INK, font=("Microsoft YaHei UI", 9))
        theme.configure("TButton", foreground=INK, padding=(9, 5))
        theme.configure("Action.TButton", background=ACCENT, foreground=WHITE, borderwidth=0)
        theme.map("Action.TButton", background=[("active", "#005747"), ("disabled", "#b8cbc2")],
                  foreground=[("disabled", "#34544a")])
        theme.configure("Treeview", rowheight=25, background=WHITE, fieldbackground=WHITE,
                        foreground=INK)
        theme.configure("TNotebook", background=PAPER)
        theme.configure("TNotebook.Tab", padding=(12, 6))
        theme.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor="#d6e4dd")

        frame = ttk.Frame(root, padding=(22, 15))
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(4, weight=1)
        header = ttk.Frame(frame)
        header.grid(row=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="TerraFactor", font=("Segoe UI Semibold", 24)).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=f"地学因子分析  ·  {ENGINE_REVISION}", foreground=MUTED).grid(
            row=1, column=0, sticky="w")
        self.open_csv = ttk.Button(header, text="打开 CSV…", command=self.choose_csv)
        self.open_csv.grid(row=0, column=1, padx=(0, 8))
        self.open_project = ttk.Button(header, text="打开项目…", command=self.choose_project)
        self.open_project.grid(row=0, column=2, padx=(0, 8))
        self.save_project_button = ttk.Button(header, text="保存项目…", command=self.save_project)
        self.save_project_button.grid(row=0, column=3)

        inputs = ttk.Frame(frame)
        inputs.grid(row=1, sticky="ew", pady=(0, 8))
        inputs.columnconfigure(1, weight=1)
        ttk.Label(inputs, text="样本表").grid(row=0, column=0, sticky="w", padx=(0, 9))
        ttk.Entry(inputs, textvariable=self.filename, state="readonly").grid(row=0, column=1, sticky="ew")
        ttk.Label(inputs, text="目标列").grid(row=0, column=2, padx=(12, 5))
        self.target = ttk.Combobox(inputs, width=15, state="readonly")
        self.target.grid(row=0, column=3)
        ttk.Label(inputs, text="分组列（可选）").grid(row=0, column=4, padx=(12, 5))
        self.group = ttk.Combobox(inputs, width=15, state="readonly")
        self.group.grid(row=0, column=5)
        self.exclusion = ttk.Button(inputs, text="排除列…", command=self.choose_exclusion)
        self.exclusion.grid(row=0, column=6, padx=(8, 0))
        self.excluded = set()

        params = ttk.Frame(frame)
        params.grid(row=2, sticky="ew", pady=(0, 9))
        ttk.Label(params, text="对照方法").pack(side="left", padx=(0, 4))
        self.methods = list(DEFAULT_METHODS)
        self.method_label = tk.StringVar(value="3 种")
        self.method_button = ttk.Button(params, textvariable=self.method_label, command=self.choose_methods)
        self.method_button.pack(side="left", padx=(0, 12))
        ttk.Label(params, text="验证方法").pack(side="left", padx=(0, 4))
        self.validation_method = ttk.Combobox(params, values=sorted(RANKING_METHODS), width=10, state="readonly")
        self.validation_method.set("IGR")
        self.validation_method.pack(side="left", padx=(0, 12))
        self.top_k = self.entry(params, "Top K", "2")
        self.folds = self.entry(params, "折数", "5")
        self.seed = self.entry(params, "种子", "42")
        self.run_button = ttk.Button(params, text="运行当前页", style="Action.TButton", command=self.run)
        self.run_button.pack(side="right")

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=3, sticky="ew", pady=(0, 10))
        self.book = ttk.Notebook(frame)
        self.book.grid(row=4, sticky="nsew")
        self.views = {}
        for key in TABS:
            columns, title = TABLES[key]
            view = TableView(self.book, columns, key in ("compare", "validate"))
            self.book.add(view.frame, text=title)
            self.views[key] = view
            if view.chart:
                view.chart.bind("<Configure>", lambda _, item=key: self.draw_chart(item))
        self.views["project"].summary.set("打开 example-project.json 或自己的项目文件，再运行当前页。")

        footer = ttk.Frame(frame)
        footer.grid(row=5, sticky="ew", pady=(9, 0))
        ttk.Label(footer, textvariable=self.status, foreground=MUTED, wraplength=590).pack(side="left")
        ttk.Button(footer, text="导出 CSV…", command=lambda: self.export("csv")).pack(side="right")
        ttk.Button(footer, text="导出 JSON…", command=lambda: self.export("json")).pack(side="right", padx=(0, 7))
        self.open_csv.focus_set()
        self.root.after(75, self.poll)

    def entry(self, parent, label, value):
        ttk.Label(parent, text=label).pack(side="left", padx=(0, 4))
        entry = ttk.Entry(parent, width=7)
        entry.insert(0, value)
        entry.pack(side="left", padx=(0, 11))
        return entry

    def active(self):
        return TABS[self.book.index(self.book.select())]

    def choose_csv(self):
        name = filedialog.askopenfilename(parent=self.root, filetypes=[("CSV", "*.csv")])
        if name:
            self.set_csv(Path(name))

    def set_csv(self, path):
        try:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                names = next(csv.reader(stream, strict=True), [])
            if len(names) < 2 or len(set(names)) != len(names) or any(not col.strip() for col in names):
                raise ValueError("CSV 至少需要两个不同且非空的列名。")
        except (OSError, UnicodeError, ValueError, csv.Error) as exc:
            self.status.set(str(exc))
            return
        self.source = path
        self.columns = names
        self.set_exclusion([name for name in names if name.casefold() == "sample_id"])
        for key in TABS[:3]:
            self.results.pop(key, None)
            self.views[key].replace([])
            self.views[key].summary.set("运行后在这里查看结果。")
            if self.views[key].chart:
                self.views[key].chart.delete("all")
        self.filename.set(str(path))
        self.target.configure(values=names)
        self.target.set("label" if "label" in names else names[-1])
        group = next((name for name in names if name.casefold() == "basin_id"), "")
        self.group.configure(values=["", *names])
        self.group.set(group)
        hints = ([f"分组 {group}"] if group else []) + ([f"排除 {'、'.join(sorted(self.excluded))}"] if self.excluded else [])
        self.status.set(" · ".join([f"已读取 {len(names)} 个列名", *hints]))

    def choose_project(self):
        name = filedialog.askopenfilename(parent=self.root, filetypes=[("JSON", "*.json")])
        if name:
            self.project = Path(name)
            self.project_label.set(self.project.name)
            self.results.pop("project", None)
            self.views["project"].replace([])
            self.views["project"].summary.set(f"项目：{self.project.name}。运行时请选择输出文件夹。")
            self.book.select(self.views["project"].frame)

    def save_project(self):
        if self.source is None:
            self.status.set("请先打开项目使用的 CSV。")
            return
        target, group = self.target.get(), self.group.get() or None
        try:
            if group == target:
                raise ValueError("分组列和目标列须不同。")
            top_k, folds, seed = int(self.top_k.get()), int(self.folds.get()), int(self.seed.get())
            if not self.methods:
                raise ValueError("至少选择一种对照方法。")
        except ValueError as exc:
            self.status.set(str(exc))
            return
        filename = filedialog.asksaveasfilename(parent=self.root, initialfile="terrafactor-project.json",
                       defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not filename:
            return
        path = Path(filename).resolve()
        try:
            relative_input = os.path.relpath(self.source, path.parent)
        except ValueError:
            relative_input = str(self.source)
        excluded = sorted((self.excluded | ({group} if group else set())) - {target})
        spec = dict(schema=1, input=relative_input, target=target, exclude=excluded, jobs=[
            dict(id="audit", operation="audit"),
            dict(id="compare", operation="compare",
                 options=dict(methods=self.methods, top_k=top_k, seed=seed)),
            dict(id="validation", operation="validate",
                 options=dict(method=self.validation_method.get(), top_k=top_k,
                              folds=folds, group=group, seed=seed)),
        ])
        try:
            atomic_json(path, spec)
        except (OSError, ValueError) as exc:
            self.status.set(str(exc))
        else:
            self.status.set(f"已保存 {path.name}。")

    def pick(self, title, values, current, apply):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        holder = ttk.Frame(dialog, padding=14)
        holder.pack(fill="both", expand=True)
        listbox = tk.Listbox(holder, width=40, height=min(14, max(4, len(values))),
                             selectmode="multiple", exportselection=False)
        scrollbar = ttk.Scrollbar(holder, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        listbox.pack(fill="both", expand=True, pady=(0, 8))
        listbox.insert(tk.END, *values)
        for i, value in enumerate(values):
            if value in current:
                listbox.selection_set(i)
        def confirm():
            apply([values[i] for i in listbox.curselection()])
            dialog.destroy()
        ttk.Button(holder, text="应用", command=confirm).pack(anchor="e")
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        listbox.focus_set()

    def choose_exclusion(self):
        if not self.source:
            self.status.set("请先打开 CSV。")
            return
        self.pick("排除列", self.columns, self.excluded, self.set_exclusion)

    def set_exclusion(self, columns):
        self.excluded = set(columns)
        self.exclusion.configure(text=f"排除列 · {len(columns)}" if columns else "排除列…")

    def choose_methods(self):
        self.pick("对照方法", sorted(METHODS), self.methods, self.set_methods)

    def set_methods(self, methods):
        self.methods = methods
        self.method_label.set(f"{len(methods)} 种")

    def run(self):
        if self.running:
            self.cancel.set()
            self.status.set("当前任务完成后停止保存后续任务。")
            return
        key = self.active()
        target, group = self.target.get(), self.group.get() or None
        excluded = sorted((self.excluded | ({group} if group else set())) - {target})
        source = self.source
        try:
            if key == "project":
                if not self.project:
                    self.choose_project()
                if not self.project:
                    return
                destination = filedialog.askdirectory(parent=self.root, title="选择项目输出文件夹")
                if not destination:
                    return
                project = self.project
                action = lambda: run_project(project, destination, cancelled=self.cancel.is_set,
                    progress=lambda i, n, name: self.events.put(("status", f"项目 {i}/{n} · {name}")))
            else:
                if not source:
                    self.status.set("请先打开 CSV。")
                    return
                if group == target:
                    raise ValueError("分组列和目标列须不同。")
                if key == "audit":
                    action = lambda: audit(source, target, excluded)
                else:
                    top_k, seed = int(self.top_k.get()), int(self.seed.get())
                    if key == "compare":
                        methods = tuple(self.methods)
                        action = lambda: compare_methods(source, target, excluded, methods, top_k, seed)
                    else:
                        method, folds = self.validation_method.get(), int(self.folds.get())
                        action = lambda: evaluate(source, target, excluded, method, top_k, folds, group, seed)
        except ValueError as exc:
            self.views[key].summary.set(str(exc))
            self.status.set(str(exc))
            return
        self.cancel.clear()
        self.running = True
        self.open_csv.configure(state="disabled")
        self.open_project.configure(state="disabled")
        self.save_project_button.configure(state="disabled")
        self.run_button.configure(text="停止后续任务" if key == "project" else "正在运行…",
                                  state="normal" if key == "project" else "disabled")
        self.progress.start(14)
        self.status.set(f"正在运行 {TABLES[key][1]}…")
        self.views[key].summary.set("正在运行…")
        def worker():
            try:
                result = action()
                previews = self.project_previews(result, destination) if key == "project" else {}
                self.events.put(("done", (key, result, previews, "")))
            except Exception as exc:
                self.events.put(("done", (key, None, {}, str(exc))))
        Thread(target=worker, daemon=True).start()

    @staticmethod
    def project_previews(report, destination):
        previews = {}
        for operation in TABS[:3]:
            jobs = [job for job in report["jobs"] if job["operation"] == operation and "file" in job]
            if len(jobs) == 1:
                with (Path(destination) / jobs[0]["file"]).open(encoding="utf-8") as stream:
                    previews[operation] = json.load(stream)["result"]
        return previews

    def poll(self):
        try:
            while True:
                event, data = self.events.get_nowait()
                if event == "status":
                    self.status.set(data)
                    continue
                key, report, previews, error = data
                self.running = False
                self.open_csv.configure(state="normal")
                self.open_project.configure(state="normal")
                self.save_project_button.configure(state="normal")
                self.progress.stop()
                self.run_button.configure(text="运行当前页", state="normal")
                if self.closing:
                    self.root.destroy()
                    return
                if error:
                    self.results.pop(key, None)
                    view = self.views[key]
                    view.replace([])
                    if view.chart:
                        view.chart.delete("all")
                    view.summary.set(f"运行失败。{error}")
                    self.status.set(f"{TABLES[key][1]}运行失败，原因见本页。")
                else:
                    self.results[key] = report
                    self.render(key)
                    if key == "project":
                        for operation, preview in previews.items():
                            self.results[operation] = preview
                            self.render(operation)
                            view = self.views[operation]
                            source_name = Path(report["input"]).name
                            view.summary.set(f"项目数据 {source_name} · {view.summary.get()}")
                        failures = sum(job["state"] == "failed" for job in report["jobs"])
                        self.status.set(f"批量项目处理结束，{failures} 项失败。详情见项目表。")
                    else:
                        self.status.set(f"{TABLES[key][1]}已完成，可导出结果。")
        except Empty:
            pass
        self.root.after(75, self.poll)

    def render(self, key):
        view, report = self.views[key], self.results[key]
        if key == "audit":
            labels = report["class_counts"]
            view.summary.set(f"{report['rows']} 条 · 类别 0 为 {labels['0']}，类别 1 为 {labels['1']} · "
                             f"无效标签 {report['invalid_target']} · 重复行 {report['duplicate_rows']} · "
                             f"高相关对 {len(report['correlated_pairs'])}（见 JSON）")
            rows = [(v["name"], v["kind"], v["missing"], v["invalid_numeric"],
                     v["valid_numeric"], v["distinct_numeric"], v.get("median", "—")) for v in report["columns"]]
        elif key == "compare":
            view.summary.set(f"{len(report['methods'])} 种方法 · Top K = {report['top_k']} · "
                             "支持数是进入各方法候选集的次数（方法配置和交集见 JSON）")
            rows = [(v["factor"], v["votes"], "、".join(v["methods"])) for v in report["votes"]]
        elif key == "validate":
            scores = report["summary"]
            view.summary.set(f"{len(report['folds'])} 折 · 全因子平均 AP {scores['all_factors']['ap']:.3f} · "
                             f"Top K 平均 AP {scores['top_k']['ap']:.3f} · 差值 {scores['delta_ap']:+.3f}")
            rows = [(v["fold"], v["test_rows"], round(v["all_factors"]["ap"], 4),
                     round(v["top_k"]["ap"], 4), round(v["delta_ap"], 4),
                     "、".join(v["selected"])) for v in report["folds"]]
        else:
            view.summary.set(f"{self.project_label.get()} · {len(report['jobs'])} 项已处理 · "
                             f"{sum(v['state'] == 'failed' for v in report['jobs'])} 项失败")
            rows = [(v["id"], v["operation"], v["state"], v.get("file", v.get("error", "")))
                    for v in report["jobs"]]
        view.replace(rows)
        self.draw_chart(key)

    def draw_chart(self, key):
        report = self.results.get(key)
        canvas = self.views[key].chart
        if not (canvas and report):
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 220)
        if key == "compare":
            rows = report["votes"][:4]
            space = max(1, len(report["methods"]))
            canvas.create_text(12, 13, text="候选支持次数", anchor="w", fill=INK)
            for i, row in enumerate(rows):
                y = 37 + 24*i
                canvas.create_text(12, y, text=row["factor"][:19], anchor="w", fill=INK)
                canvas.create_rectangle(148, y-6, 148+(width-196)*row["votes"]/space, y+6,
                                        fill=ACCENT, outline="")
                canvas.create_text(width-14, y, text=str(row["votes"]), anchor="e", fill=INK)
        else:
            canvas.create_text(12, 13, text="每折 AP   ·   蓝：全因子   ·   绿：Top K", anchor="w", fill=INK)
            folds = report["folds"][:12]
            slot = (width-36)/len(folds)
            for i, row in enumerate(folds):
                x, bottom = 18+i*slot, 114
                bar = max(4, min(18, slot/4))
                for j, (name, color) in enumerate((("all_factors", SECOND), ("top_k", ACCENT))):
                    left = x+slot/2+(j-1)*bar
                    canvas.create_rectangle(left, bottom-78*row[name]["ap"], left+bar-1, bottom,
                                            fill=color, outline="")
                canvas.create_text(x+slot/2, 126, text=str(row["fold"]), fill=MUTED)

    def export(self, format_name):
        key = self.active()
        if key not in self.results:
            self.status.set("当前页还没有分析结果。")
            return
        name = filedialog.asksaveasfilename(parent=self.root, initialfile=f"terrafactor-{key}.{format_name}",
                defaultextension=f".{format_name}", filetypes=[(format_name.upper(), f"*.{format_name}")])
        if not name:
            return
        try:
            if format_name == "json":
                atomic_json(name, self.results[key])
            else:
                with open(name, "w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(self.views[key].columns)
                    writer.writerows(self.views[key].rows)
        except (OSError, ValueError) as exc:
            self.status.set(str(exc))
        else:
            self.status.set(f"已导出 {Path(name).name}。")

    def close(self):
        if self.running:
            self.closing = True
            self.cancel.set()
            self.status.set("当前计算完成后关闭。")
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = TerraFactorStudio(root)
    if len(sys.argv) == 2:
        path = Path(sys.argv[1]).resolve()
        if path.suffix.lower() == ".csv" and path.is_file():
            app.set_csv(path)
    root.mainloop()


if __name__ == "__main__":
    main()
