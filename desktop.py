"""Windows desktop interface for selecting factors and exporting JSON."""
import csv
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import filedialog, ttk

from select_factors import METHODS, run_selection


class ScreeningWindow:
    def __init__(self, root):
        self.root = root
        root.title("地学因子筛选工具")
        root.geometry("710x590")
        root.minsize(620, 560)
        root.protocol("WM_DELETE_WINDOW", self.close)

        self.input_path = None
        self.output_path = None
        self.results = Queue()
        self.running = False

        frame = ttk.Frame(root, padding=(28, 22))
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

        ttk.Label(frame, text="地学因子筛选工具",
                  font=("Microsoft YaHei UI", 19, "bold")).grid(
                      row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        ttk.Label(frame, text="选择带有 0/1 标签的训练 CSV，然后将筛选结果导出为 JSON。").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 18))

        ttk.Label(frame, text="训练 CSV").grid(row=2, column=0, sticky="w", padx=(0, 18))
        self.input_label = tk.StringVar(value="尚未选择 CSV")
        ttk.Entry(frame, textvariable=self.input_label, state="readonly").grid(
            row=2, column=1, sticky="ew")
        self.input_button = ttk.Button(frame, text="打开 CSV…", command=self.choose_input)
        self.input_button.grid(row=2, column=2, padx=(10, 0))

        ttk.Label(frame, text="目标列").grid(row=3, column=0, sticky="w")
        self.target = ttk.Combobox(frame, state="readonly")
        self.target.grid(row=3, column=1, columnspan=2, sticky="ew", pady=9)

        factors = ttk.Frame(frame)
        factors.grid(row=4, column=1, columnspan=2, sticky="nsew", pady=(0, 10))
        ttk.Label(frame, text="排除列").grid(row=4, column=0, sticky="nw")
        ttk.Label(factors, text="可多选，例如样本编号或坐标。目标列会自动排除。").pack(
            anchor="w", pady=(0, 5))
        scrollbar = ttk.Scrollbar(factors)
        scrollbar.pack(side="right", fill="y")
        self.excluded = tk.Listbox(factors, selectmode="multiple", exportselection=False,
                                   height=5, yscrollcommand=scrollbar.set,
                                   font=("Microsoft YaHei UI", 10))
        self.excluded.pack(fill="both", expand=True)
        scrollbar.configure(command=self.excluded.yview)

        ttk.Label(frame, text="筛选方法").grid(row=5, column=0, sticky="w")
        self.method = ttk.Combobox(frame, values=sorted(METHODS), state="readonly")
        self.method.set("IGR")
        self.method.grid(row=5, column=1, columnspan=2, sticky="ew")

        ttk.Label(frame, text="随机种子").grid(row=6, column=0, sticky="w")
        self.seed = ttk.Entry(frame, width=15)
        self.seed.insert(0, "42")
        self.seed.grid(row=6, column=1, sticky="w", pady=9)

        ttk.Label(frame, text="输出文件").grid(row=7, column=0, sticky="w")
        self.output_label = tk.StringVar(value="尚未选择输出路径")
        ttk.Entry(frame, textvariable=self.output_label, state="readonly").grid(
            row=7, column=1, sticky="ew")
        self.output_button = ttk.Button(frame, text="选择路径…", command=self.choose_output)
        self.output_button.grid(row=7, column=2, padx=(10, 0))

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(15, 8))
        self.status = tk.StringVar(value="打开 CSV 后选择目标列和输出路径。")
        self.status_label = ttk.Label(frame, textvariable=self.status, wraplength=470)
        self.status_label.grid(row=9, column=0, columnspan=2, sticky="w", padx=(0, 12))
        self.run_button = ttk.Button(frame, text="运行并导出", command=self.run, state="disabled")
        self.run_button.grid(row=9, column=2, sticky="e")
        self.input_button.focus_set()

    def choose_input(self):
        name = filedialog.askopenfilename(parent=self.root, title="打开训练 CSV",
                                          filetypes=[("CSV 文件", "*.csv")])
        if name:
            self.set_input(Path(name))

    def set_input(self, path):
        try:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                header = next(csv.reader(stream), [])
            if len(header) < 2 or len(set(header)) != len(header) or any(not h.strip() for h in header):
                raise ValueError("首行需要至少两个不同且非空的列名。")
        except (OSError, UnicodeError, csv.Error, ValueError) as exc:
            self.status.set(f"无法读取 CSV。{exc}")
            return
        self.input_path = path
        self.input_label.set(str(path))
        self.target.configure(values=header)
        self.target.set("label" if "label" in header else "")
        self.excluded.delete(0, tk.END)
        self.excluded.insert(tk.END, *header)
        self.status.set(f"已读取 {len(header)} 个列名。")
        self.refresh()

    def choose_output(self):
        name = filedialog.asksaveasfilename(parent=self.root, title="保存筛选结果",
                                            initialfile="result.json", defaultextension=".json",
                                            filetypes=[("JSON 文件", "*.json")])
        if name:
            self.output_path = Path(name)
            self.output_label.set(name)
            self.refresh()

    def refresh(self):
        self.run_button.configure(state="normal" if self.input_path and self.output_path
                                  and not self.running else "disabled")

    def run(self):
        target = self.target.get()
        if not target:
            self.status.set("请选择包含 0 和 1 标签的目标列。")
            self.target.focus_set()
            return
        try:
            seed = int(self.seed.get())
        except ValueError:
            self.status.set("随机种子请输入整数。")
            self.seed.focus_set()
            return
        excluded = [self.excluded.get(i) for i in self.excluded.curselection()
                    if self.excluded.get(i) != target]
        output = self.output_path
        args = (self.input_path, target, excluded, self.method.get(), output, seed)
        self.running = True
        self.refresh()
        self.input_button.configure(state="disabled")
        self.output_button.configure(state="disabled")
        self.status.set("正在筛选，完成后会导出 JSON。")
        self.progress.start(14)
        Thread(target=self.export, args=args, daemon=True).start()
        self.root.after(100, self.poll)

    def export(self, *args):
        try:
            run_selection(*args)
        except Exception as exc:
            self.results.put(f"导出失败。{exc}")
        else:
            self.results.put(f"已导出 {args[4].name}。")

    def poll(self):
        try:
            result = self.results.get_nowait()
        except Empty:
            self.root.after(100, self.poll)
            return
        self.running = False
        self.progress.stop()
        self.status.set(result)
        self.input_button.configure(state="normal")
        self.output_button.configure(state="normal")
        self.refresh()

    def close(self):
        if self.running:
            self.status.set("正在筛选，请等待导出完成。")
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    ScreeningWindow(root)
    root.mainloop()
