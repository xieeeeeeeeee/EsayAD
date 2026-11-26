"""Compact native layout; persistent actions remain outside the resizing body."""
import tkinter as tk
from tkinter import ttk
import os
import webbrowser

BG = '#F5FBFA'
INK = '#203B38'
MUTED = '#607874'
ACCENT = '#2F8076'
LINE = '#C9DED8'
SOFT = '#E1F0EC'
TABLE = '#E8F3EF'
BLUE = '#5FA8C7'
WARM = '#F0C36A'
VERSION = '0.4.0'


def build_ui(app):
    app.title('立创元件助手 · ' + VERSION)
    app.geometry('900x650')
    app.minsize(760, 560)
    app.configure(bg=BG)
    icon = os.path.join(os.path.dirname(__file__), 'assets', 'app.ico')
    if os.path.isfile(icon):
        app.iconbitmap(icon)
    style = ttk.Style(app)
    style.theme_use('clam')
    style.configure('.', font=('Microsoft YaHei UI', 9), background=BG, foreground=INK)
    style.configure('TFrame', background=BG)
    style.configure('TLabel', background=BG, foreground=INK)
    style.configure('Muted.TLabel', foreground=MUTED)
    style.configure('TButton', padding=(10, 5), borderwidth=1, relief='flat', background='white', bordercolor=LINE)
    style.map('TButton', background=[('active', SOFT)], foreground=[('disabled', MUTED)])
    style.configure('TMenubutton', background=SOFT, foreground=INK, padding=(10, 5), borderwidth=0)
    style.configure('Accent.TButton', background=ACCENT, foreground='white', bordercolor=ACCENT, padding=(15, 6))
    style.map('Accent.TButton', background=[('disabled', SOFT), ('pressed', '#226860'), ('active', '#28776E')], foreground=[('disabled', MUTED), ('!disabled', 'white')])
    style.configure('TEntry', padding=7, fieldbackground='white', bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
    style.map('TEntry', bordercolor=[('focus', ACCENT)], lightcolor=[('focus', ACCENT)])
    style.configure('Treeview', rowheight=27, background='white', fieldbackground='white', foreground=INK, borderwidth=0)
    style.map('Treeview', background=[('selected', SOFT)], foreground=[('selected', INK)])
    style.configure('Treeview.Heading', font=('Microsoft YaHei UI', 9), background=TABLE, foreground=INK, padding=(8, 7), relief='flat', borderwidth=0)
    style.configure('Horizontal.TProgressbar', background=ACCENT, troughcolor=TABLE, borderwidth=0, thickness=3)
    style.configure('Vertical.TScrollbar', width=10, arrowsize=9, background=LINE, troughcolor='white', borderwidth=0)

    # Pack the bottom bar first, so it cannot be pushed out by growing content.
    bottom = tk.Frame(app, bg='white', padx=16, pady=10, highlightbackground=LINE, highlightthickness=1)
    bottom.pack(side='bottom', fill='x')
    attribution = tk.Frame(bottom, bg='white')
    attribution.pack(side='bottom', fill='x', pady=(8, 0))
    tk.Label(attribution, text='模型来自嘉立创EDA/EasyEDA官方库 · 转换后请核对封装', bg='white', fg=MUTED, font=('Microsoft YaHei UI', 8)).pack(side='left')
    for text, url in (('EasyEDA', 'https://easyeda.com/'), ('嘉立创EDA', 'https://lceda.cn/')):
        link = tk.Label(attribution, text=text, bg='white', fg=ACCENT, font=('Microsoft YaHei UI', 8), cursor='hand2')
        link.pack(side='right', padx=(7, 0))
        link.bind('<Button-1>', lambda _, u=url: webbrowser.open(u))
    app.import_button = ttk.Button(bottom, text='导入 AD 并放置', style='Accent.TButton', command=lambda: app.export(True), state='disabled')
    app.import_button.pack(side='right')
    app.export_button = ttk.Button(bottom, text='生成库', command=lambda: app.export(False), state='disabled')
    app.export_button.pack(side='right', padx=8)
    ttk.Button(bottom, text='输出目录', command=app.open_output).pack(side='left')
    ttk.Button(bottom, text='商品页面', command=app.open_product).pack(side='left', padx=6)

    header = tk.Frame(app, bg=BG, padx=16, pady=10)
    header.pack(fill='x')
    mark = tk.Canvas(header, width=28, height=28, bg=BG, highlightthickness=0)
    mark.pack(side='left', padx=(0, 9))
    mark.create_rectangle(6, 6, 22, 22, fill=ACCENT, outline=ACCENT)
    mark.create_rectangle(11, 11, 17, 17, fill=WARM, outline=WARM)
    for offset in (10, 18):
        for xy in ((offset, 2, offset, 6), (offset, 22, offset, 26), (2, offset, 6, offset), (22, offset, 26, offset)):
            mark.create_line(*xy, fill=ACCENT, width=2)
    tk.Label(header, text='立创元件助手', font=('Microsoft YaHei UI', 13, 'bold'), fg=INK, bg=BG).pack(side='left')
    tk.Label(header, text='AD20+  /  ' + VERSION, font=('Segoe UI', 9), fg=MUTED, bg=BG).pack(side='left', padx=10)
    menu = tk.Menu(app, tearoff=False, font=('Microsoft YaHei UI', 10), bg='white', fg=INK)
    menu.add_command(label='设置 AD 路径', command=app.configure_ad)
    menu.add_command(label='AD 版本与兼容信息', command=app.compatibility_info)
    menu.add_command(label='解除导入等待…', command=app.reset_ad_wait)
    menu.add_separator()
    menu.add_command(label='查看日志', command=lambda: show_log(app))
    menu.add_command(label='使用说明', command=lambda: os.startfile(str(app.root_dir / 'README.md')))
    more = ttk.Menubutton(header, text='更多', menu=menu)
    more.pack(side='right')

    body = ttk.Frame(app, padding=(16, 0, 16, 0))
    body.pack(fill='both', expand=True)
    body.columnconfigure(0, weight=1)
    body.rowconfigure(3, weight=1, minsize=60)
    search = ttk.Frame(body)
    search.grid(row=0, column=0, sticky='ew', pady=(1, 7))
    ttk.Label(search, text='搜索元件', style='Muted.TLabel').pack(side='left', padx=(0, 10))
    app.entry = ttk.Entry(search, font=('Microsoft YaHei UI', 11))
    app.entry.pack(side='left', fill='x', expand=True)
    app.entry.bind('<Return>', lambda _: app.search())
    app.search_button = ttk.Button(search, text='搜索', style='Accent.TButton', command=app.search)
    app.search_button.pack(side='left', padx=(8, 0))
    app.source = tk.StringVar(value='型号 / 关键词 / C料号 · 关键词来自嘉立创贴片目录，非商城全量')
    ttk.Label(body, textvariable=app.source, style='Muted.TLabel', font=('Microsoft YaHei UI', 8)).grid(row=1, column=0, sticky='ew', pady=(0, 8))
    table = tk.Frame(body, bg='white', highlightbackground=LINE, highlightthickness=1)
    table.grid(row=3, column=0, sticky='nsew')
    table.rowconfigure(0, weight=1)
    table.columnconfigure(0, weight=1)
    app.table = ttk.Treeview(table, columns=('lcsc', 'model', 'manufacturer', 'package', 'description'), show='headings', selectmode='browse', height=5)
    for name, title, width in zip(app.table['columns'], ('料号', '型号', '厂家', '封装', '描述'), (100, 190, 130, 100, 270)):
        app.table.heading(name, text=title, anchor='w')
        app.table.column(name, width=width, minwidth=70, stretch=True)
    scroll = ttk.Scrollbar(table, orient='vertical', command=app.table.yview)
    horizontal = ttk.Scrollbar(table, orient='horizontal', command=app.table.xview)
    app.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
    app.table.grid(row=0, column=0, sticky='nsew')
    scroll.grid(row=0, column=1, sticky='ns')
    horizontal.grid(row=1, column=0, sticky='ew')
    app.table.bind('<<TreeviewSelect>>', app.selected)
    pager = ttk.Frame(body)
    pager.grid(row=4, column=0, sticky='ew', pady=6)
    app.previous = ttk.Button(pager, text='上一页', command=lambda: app.search(app.page-1), state='disabled')
    app.previous.pack(side='left')
    app.next = ttk.Button(pager, text='下一页', command=lambda: app.search(app.page+1), state='disabled')
    app.next.pack(side='left', padx=5)
    app.summary = tk.StringVar(value='试试 C25804 或 ESP8266')
    ttk.Label(pager, textvariable=app.summary, style='Muted.TLabel').pack(side='right')
    app.details = tk.StringVar(value='选择元件，预览符号和封装')
    detail = ttk.Label(body, textvariable=app.details, font=('Microsoft YaHei UI', 9, 'bold'), anchor='w')
    detail.grid(row=5, column=0, sticky='ew', pady=(2, 7))
    previews = ttk.Frame(body)
    previews.grid(row=6, column=0, sticky='ew')
    previews.columnconfigure((0, 1), weight=1, uniform='preview')
    app.canvases = []
    for i, title in enumerate(('原理图符号', 'PCB 封装 / 俯视图')):
        pane = tk.Frame(previews, bg='white', highlightbackground=LINE, highlightthickness=1)
        pane.grid(row=0, column=i, sticky='ew', padx=(0, 4) if i == 0 else (4, 0))
        tk.Label(pane, text=title, font=('Microsoft YaHei UI', 8), bg='white', fg=MUTED, anchor='w', padx=10, pady=5).pack(fill='x')
        canvas = tk.Canvas(pane, width=1, height=112, bg='white', highlightthickness=0)
        canvas.pack(fill='x')
        app.canvases.append(canvas)
        canvas.bind('<Configure>', lambda _, a=app: redraw(a))
    app.status = tk.StringVar(value='就绪 · 符号与封装配套导入')
    status = ttk.Label(body, textvariable=app.status, style='Muted.TLabel', font=('Microsoft YaHei UI', 8), anchor='w')
    status.grid(row=7, column=0, sticky='ew', pady=(7, 4))
    # Labels stay single-line so long errors cannot push the actions off-screen;
    # full messages are available in More > Log.
    progress_frame = tk.Frame(body, height=3, bg=TABLE)
    progress_frame.grid(row=8, column=0, sticky='ew', pady=(0, 7))
    progress_frame.pack_propagate(False)
    app.progress = ttk.Progressbar(progress_frame, mode='indeterminate')
    app.progress.pack(fill='both', expand=True)
    app.log = tk.Text(app, state='disabled')
    app.preview_geometry = None
    app.after(100, app.drain)
    app.entry.focus_set()


def redraw(app):
    geometry = getattr(app, 'preview_geometry', None)
    if geometry:
        app.draw(*geometry)


def show_log(app):
    window = tk.Toplevel(app)
    window.title('运行日志')
    window.geometry('680x360')
    text = tk.Text(window, wrap='word', font=('Microsoft YaHei UI', 10), padx=12, pady=12, bg='white', fg=INK)
    text.pack(fill='both', expand=True)
    text.insert('1.0', app.log.get('1.0', 'end'))
    text.configure(state='disabled')
