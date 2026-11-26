"""Chinese desktop UI; all network and conversion work stays off the Tk thread."""
from pathlib import Path
import math
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser

from .catalog import Catalog
from .exporter import Exporter
from .bridge import Bridge, read_receipt
from .workflow import Selection


class App(tk.Tk):
    def __init__(self, root: Path):
        super().__init__()
        self.title('立创元件助手 · AD24')
        self.geometry('1120x800')
        self.minsize(940, 720)
        self.configure(bg='#F3F5F8')
        self.root_dir = root
        self.data = root / 'data'
        self.catalog = Catalog(self.data / 'cache')
        self.exporter = Exporter(self.data / 'libraries')
        self.bridge = Bridge(self.data)
        self.selection = Selection()
        self.events = queue.Queue()
        self.results = []
        self.page = 1
        self.query = ''
        self.project = None
        self.last_receipt = None
        self.export_busy = False
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI', 10))
        style.configure('TFrame', background='#F3F5F8')
        style.configure('TLabel', background='#F3F5F8', foreground='#24334B')
        style.configure('TButton', padding=(12, 7))
        style.configure('Treeview', rowheight=31, background='white', fieldbackground='white')
        style.configure('Treeview.Heading', font=('Microsoft YaHei UI', 10, 'bold'), padding=7)
        style.configure('Accent.TButton', background='#165DDE', foreground='white')
        style.map('Accent.TButton', background=[('active', '#1249AC'), ('disabled', '#AAB8CE')])
        header = tk.Frame(self, bg='#122B4A', padx=24, pady=10)
        header.pack(fill='x')
        tk.Label(header, text='立创元件助手', font=('Microsoft YaHei UI', 21, 'bold'), bg='#122B4A', fg='white').pack(side='left')
        tk.Label(header, text='搜索  →  预览  →  AD24', bg='#122B4A', fg='#CCDDF2', font=('Microsoft YaHei UI', 11)).pack(side='right')
        body = ttk.Frame(self, padding=12)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='型号 / 关键词 / 立创 C 料号').pack(anchor='w')
        search = ttk.Frame(body)
        search.pack(fill='x', pady=(6, 8))
        self.entry = ttk.Entry(search, font=('Microsoft YaHei UI', 12))
        self.entry.pack(side='left', fill='x', expand=True, ipady=7)
        self.entry.bind('<Return>', lambda _: self.search())
        self.search_button = ttk.Button(search, text='搜索元件', style='Accent.TButton', command=self.search)
        self.search_button.pack(side='left', padx=(10, 0))
        ttk.Button(search, text='设置 AD 路径', command=self.configure_ad).pack(side='left', padx=(8, 0))
        self.source = tk.StringVar(value='关键词搜索：嘉立创贴片元件目录；C 料号：EasyEDA 官方库精确查询')
        ttk.Label(body, textvariable=self.source, wraplength=1000).pack(anchor='w', pady=(0, 8))
        table = ttk.Frame(body)
        table.pack(fill='both', expand=True)
        columns = ('lcsc', 'model', 'manufacturer', 'package', 'description')
        self.table = ttk.Treeview(table, columns=columns, show='headings', selectmode='browse', height=5)
        for name, title, width in zip(columns, ('立创料号', '厂家型号', '厂家', '封装', '描述'), (100, 200, 180, 130, 320)):
            self.table.heading(name, text=title)
            self.table.column(name, width=width, minwidth=70)
        scroll = ttk.Scrollbar(table, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.table.bind('<<TreeviewSelect>>', self.selected)
        pager = ttk.Frame(body)
        pager.pack(fill='x', pady=8)
        self.previous = ttk.Button(pager, text='上一页', command=lambda: self.search(self.page - 1), state='disabled')
        self.previous.pack(side='left')
        self.next = ttk.Button(pager, text='下一页', command=lambda: self.search(self.page + 1), state='disabled')
        self.next.pack(side='left', padx=8)
        self.summary = tk.StringVar(value='试试 C25804、NE555DR 或 capacitor')
        ttk.Label(pager, textvariable=self.summary).pack(side='right')
        self.details = tk.StringVar(value='选中元件后获取符号与封装，并检查引脚编号。')
        ttk.Label(body, textvariable=self.details, wraplength=1030).pack(anchor='w', pady=(3, 8))
        previews = ttk.Frame(body)
        previews.pack(fill='x')
        self.canvases = []
        for title in ('原理图符号', 'PCB 封装 · 俯视图'):
            pane = ttk.Frame(previews)
            pane.pack(side='left', fill='both', expand=True, padx=(0, 8))
            ttk.Label(pane, text=title, font=('Microsoft YaHei UI', 10, 'bold')).pack(anchor='w')
            canvas = tk.Canvas(pane, height=140, bg='white', highlightbackground='#D6DDE8', highlightthickness=1)
            canvas.pack(fill='x', pady=5)
            self.canvases.append(canvas)
        actions = ttk.Frame(body)
        actions.pack(fill='x', pady=7)
        self.export_button = ttk.Button(actions, text='生成 AD 库', command=lambda: self.export(False), state='disabled')
        self.export_button.pack(side='left')
        self.import_button = ttk.Button(actions, text='导入 AD 并放置', style='Accent.TButton', command=lambda: self.export(True), state='disabled')
        self.import_button.pack(side='left', padx=8)
        ttk.Button(actions, text='打开输出目录', command=self.open_output).pack(side='left')
        ttk.Button(actions, text='商品页面', command=self.open_product).pack(side='left', padx=8)
        ttk.Button(actions, text='解除导入等待', command=self.reset_ad_wait).pack(side='left')
        ttk.Button(actions, text='使用说明', command=lambda: os.startfile(str(self.root_dir / 'README.md'))).pack(side='right')
        self.status = tk.StringVar(value='就绪 · AD 端导入尚待本机联调')
        ttk.Label(body, textvariable=self.status, wraplength=1030).pack(anchor='w', pady=(2, 5))
        self.progress = ttk.Progressbar(body, mode='indeterminate')
        self.progress.pack(fill='x')
        self.log = tk.Text(body, height=2, wrap='word', font=('Microsoft YaHei UI', 9), bg='#EAF0F7', relief='flat')
        self.log.pack(fill='x', pady=7)
        self.log.configure(state='disabled')
        footer = ttk.Frame(self, padding=(18, 4, 18, 10))
        footer.pack(fill='x')
        ttk.Label(footer, text='模型来源：嘉立创EDA/EasyEDA官方库 · 转换后请核对引脚、焊盘与极性', font=('Microsoft YaHei UI', 9)).pack(side='left')
        link = tk.Label(footer, text='lceda.cn  /  easyeda.com', fg='#165DDE', bg='#F3F5F8', cursor='hand2')
        link.pack(side='right')
        link.bind('<Button-1>', lambda _: webbrowser.open('https://lceda.cn/'))
        self.after(100, self.drain)
        self.entry.focus_set()

    def note(self, text):
        self.status.set(text)
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def worker(self, generation, kind, function):
        self.progress.start(12)
        def run():
            try:
                self.events.put((generation, kind, function(), None))
            except Exception as exc:
                self.events.put((generation, kind, None, str(exc)))
        threading.Thread(target=run, daemon=True).start()

    def search(self, page=1):
        query = self.entry.get().strip()
        if not query:
            self.note('请输入型号、关键词或 C 料号')
            return
        if not isinstance(page, int):
            page = 1
        generation = self.selection.reset()
        self.query, self.page = query, page
        self.results = []
        self.table.delete(*self.table.get_children())
        self.disable_import()
        self.search_button.configure(state='disabled')
        self.previous.configure(state='disabled')
        self.next.configure(state='disabled')
        self.details.set('正在搜索…')
        for canvas in self.canvases:
            canvas.delete('all')
        self.note(f'正在搜索 {query}…')
        self.worker(generation, 'search', lambda: self.catalog.search(query, page))

    def disable_import(self):
        self.export_button.configure(state='disabled')
        self.import_button.configure(state='disabled')

    def selected(self, _=None):
        rows = self.table.selection()
        if not rows:
            return
        part = self.results[int(rows[0])]
        generation = self.selection.reset()
        self.disable_import()
        for canvas in self.canvases:
            canvas.delete('all')
        self.details.set(f'{part.lcsc} · {part.model} · 正在获取模型…')
        def load():
            raw = self.catalog.component(part.lcsc)
            geometry = self.exporter.parse(part.lcsc, raw)
            return part.lcsc, raw, geometry
        self.worker(generation, 'detail', load)

    def drain(self):
        while not self.events.empty():
            generation, kind, value, error = self.events.get_nowait()
            if kind == 'export':
                self.export_busy = False
            if generation != self.selection.generation:
                if kind == 'export':
                    self.enable_import()
                continue
            self.progress.stop()
            self.search_button.configure(state='normal')
            if error:
                self.note(error)
                if kind == 'detail':
                    self.details.set('模型不可导入：' + error)
                elif kind == 'export':
                    self.enable_import()
                continue
            if kind == 'search':
                self.results = value.parts
                self.source.set(value.source)
                for i, part in enumerate(value.parts):
                    self.table.insert('', 'end', iid=str(i), values=(part.lcsc, part.model, part.manufacturer, part.package, part.description))
                self.summary.set(f'第 {value.page} 页 · 共 {value.total} 个结果')
                self.previous.configure(state='normal' if value.page > 1 else 'disabled')
                self.next.configure(state='normal' if value.page * 20 < value.total else 'disabled')
                self.note('选中元件查看模型' if value.parts else '没有匹配结果；可改用准确型号或 C 料号，关键词目录不覆盖全部商城商品')
                if value.parts:
                    self.table.selection_set('0')
            elif kind == 'detail':
                lcsc, raw, geometry = value
                if self.selection.accept(generation, lcsc, raw):
                    symbol, footprint, pins, pads, warnings = geometry
                    self.details.set(f'{lcsc} · {raw["title"]} · {len(pins)} 引脚 / {len(pads)} 焊盘 · 编号匹配')
                    self.draw(symbol, footprint)
                    self.enable_import()
                    self.note('模型已就绪。' + (' '.join(dict.fromkeys(warnings)) if warnings else ''))
            elif kind == 'export':
                result, do_import = value
                self.selection.export = result
                self.note(f'库已生成：{result.schlib.parent}')
                self.enable_import()
                if do_import:
                    try:
                        self.project = self.bridge.prepare(result)
                        self.bridge.launch(self.project)
                        self.last_receipt = None
                        self.import_button.configure(state='disabled')
                        self.note('已向 AD 发送导入请求；请在 AD 激活原理图。实际放置结果等待 AD 回执。')
                    except Exception as exc:
                        self.note(f'库已生成，AD 请求失败：{exc}')
        if self.project:
            receipt = read_receipt(self.project)
            if receipt != self.last_receipt:
                self.last_receipt = receipt
                messages = {'pending': '等待 AD 回执，请勿重复运行脚本。若 AD 报错，先执行“运行 → 停止”，再解除等待。',
                            'opened': 'AD 已安装库', 'placing': 'AD 正在放置：点击原理图落下器件，Esc 结束',
                            'placed': 'AD 回执：原理图元件数量已增加', 'cancelled': '已取消放置，库仍保存在本地',
                            'no_schematic': '库已安装；请在 AD 激活 .SchDoc，再点击导入', 'failed': 'AD 脚本执行失败，请查看 AD 提示'}
                self.note(messages[receipt])
        try:
            active = self.bridge.active_project()
            if active:
                if self.project is None:
                    self.project = active
                self.import_button.configure(state='disabled')
            elif self.selection.raw and not self.export_busy:
                self.import_button.configure(state='normal')
        except RuntimeError:
            self.import_button.configure(state='disabled')
        self.after(150, self.drain)

    def enable_import(self):
        if self.selection.raw and not self.export_busy:
            self.export_button.configure(state='normal')
            try:
                if self.bridge.active_project() is None:
                    self.import_button.configure(state='normal')
            except RuntimeError:
                self.import_button.configure(state='disabled')

    def export(self, do_import):
        if not self.selection.raw:
            return
        if self.export_busy:
            return
        if do_import:
            try:
                if self.bridge.active_project() is not None:
                    self.note('上一次 AD 导入仍在运行，请先完成或停止脚本')
                    return
            except RuntimeError as exc:
                self.note(str(exc))
                return
        lcsc, raw = self.selection.lcsc, self.selection.raw
        self.export_busy = True
        self.disable_import()
        self.note(f'正在生成 {lcsc} 的 AD 库…')
        self.worker(self.selection.generation, 'export', lambda: (self.exporter.export(lcsc, raw), do_import))

    def draw(self, symbol, footprint):
        for canvas, shapes in zip(self.canvases, (self.symbol_shapes(symbol), self.footprint_shapes(footprint))):
            canvas.delete('all')
            for method, coords, options in shapes:
                getattr(canvas, method)(*coords, **options)
            box = canvas.bbox('all')
            if box:
                width, height = max(canvas.winfo_width(), 350), canvas.winfo_height()
                factor = min((width - 70) / max(box[2]-box[0], 1), (height-50) / max(box[3]-box[1], 1))
                canvas.scale('all', 0, 0, factor, factor)
                box = canvas.bbox('all')
                canvas.move('all', (width-box[2]-box[0])/2, (height-box[3]-box[1])/2)

    def symbol_shapes(self, symbol):
        shapes = []
        for line in symbol.lines:
            shapes.append(('create_line', [line.x1, -line.y1, line.x2, -line.y2], {'fill': '#8E263D', 'width': 2}))
        for r in symbol.rects:
            shapes.append(('create_rectangle', [r.x1, -r.y1, r.x2, -r.y2], {'outline': '#8E263D', 'fill': '#FFF2C8', 'width': 2}))
        for arc in symbol.arcs:
            shapes.append(('create_arc', [arc.cx-arc.radius, -arc.cy-arc.radius, arc.cx+arc.radius, -arc.cy+arc.radius], {'start': arc.start_angle, 'extent': (arc.end_angle-arc.start_angle) or 359.9, 'style': 'arc', 'outline': '#8E263D'}))
        for pin in symbol.pins:
            dx, dy = ((1, 0), (0, -1), (-1, 0), (0, 1))[pin.orientation]
            x, y = pin.x, -pin.y
            shapes.append(('create_line', [x, y, x+dx*pin.length, y+dy*pin.length], {'fill': '#165DDE', 'width': 2}))
            shapes.append(('create_text', [x, y-4], {'text': pin.number, 'fill': '#24334B', 'font': ('Segoe UI', 8)}))
        return shapes

    def footprint_shapes(self, footprint):
        shapes = []
        scale = 100000
        for track in footprint.tracks:
            shapes.append(('create_line', [track.x1/scale, -track.y1/scale, track.x2/scale, -track.y2/scale], {'fill': '#76879F', 'width': 1}))
        for pad in footprint.pads:
            angle = math.radians(pad.rotation)
            points = []
            for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                x, y = dx*pad.size_x/2, dy*pad.size_y/2
                points += [(pad.x+x*math.cos(angle)-y*math.sin(angle))/scale, -(pad.y+x*math.sin(angle)+y*math.cos(angle))/scale]
            shapes.append(('create_polygon', points, {'fill': '#CC8B39', 'outline': '#855824'}))
            shapes.append(('create_text', [pad.x/scale, -pad.y/scale], {'text': pad.name, 'fill': '#122B4A', 'font': ('Segoe UI', 8)}))
        return shapes

    def open_output(self):
        folder = self.selection.export.schlib.parent if self.selection.export else self.data / 'libraries'
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))

    def open_product(self):
        rows = self.table.selection()
        if rows:
            url = self.results[int(rows[0])].url
            if url.startswith('https://') or url.startswith('http://'):
                webbrowser.open(url)

    def configure_ad(self):
        path = filedialog.askopenfilename(title='选择 AD 的 X2.EXE', initialdir=str(self.bridge.altium.parent), filetypes=[('Altium Designer', 'X2.EXE')])
        if path:
            self.bridge.altium = Path(path)
            self.note('AD 路径：' + path)

    def reset_ad_wait(self):
        if messagebox.askyesno('确认 AD 脚本已停止', '请先在 AD 关闭错误提示，并执行“运行 → 停止”。\n\n确认 AD 脚本已经停止后，才可解除助手等待。\n现在是否已经停止？'):
            self.bridge.reset_after_ad_stopped()
            self.project = None
            self.last_receipt = None
            self.enable_import()
            self.note('已解除等待；请激活目标原理图后再导入')


def main():
    root = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    if root.name == 'dist' and (root.parent / 'Start.cmd').is_file():
        root = root.parent
    App(root).mainloop()
