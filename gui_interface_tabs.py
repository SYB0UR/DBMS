import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from db_interface import DBTable, TYPE_INT, TYPE_STRING, TYPE_FLOAT, load_table_from_json, save_table_to_json
import json
import os
import zipfile
import shutil
import threading
import time

MIN_NUM_WIDTH = 40  # Минимальная ширина для столбца "№"

class TableManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("СУБД с вкладками")
        self.geometry("900x700")
        
        self.tables = {}      
        self.table_tabs = {}  
        self.buttons_position = "top"  # top или bottom
        
        # --- Меню ---
        menubar = tk.Menu(self)
        
        # Меню файл
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Сохранить базу данных", command=self.save_database)
        file_menu.add_command(label="Загрузить базу данных", command=self.load_database)
        file_menu.add_separator()
        file_menu.add_command(label="Сделать резервную копию", command=self.make_backup)
        menubar.add_cascade(label="Файл", menu=file_menu)
        
        # Меню настроек
        settings_menu = tk.Menu(menubar, tearoff=0)
        self.buttons_position_var = tk.StringVar(value=self.buttons_position)
        settings_menu.add_radiobutton(label="Кнопки сверху", variable=self.buttons_position_var, value="top", command=self.update_buttons_position)
        settings_menu.add_radiobutton(label="Кнопки снизу", variable=self.buttons_position_var, value="bottom", command=self.update_buttons_position)
        menubar.add_cascade(label="Настройки", menu=settings_menu)
        self.config(menu=menubar)
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Привязываем обработчик правого клика по вкладке
        self.notebook.bind('<Button-3>', self.on_tab_right_click)
        
        self.manage_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.manage_tab, text="Управление таблицами")
        self.create_manage_tab(self.manage_tab)
        
        self.backup_interval = 5 * 60  # 5 минут в секундах
        self.backup_thread = threading.Thread(target=self._auto_backup_loop, daemon=True)
        self.backup_thread.start()
    
    def create_manage_tab(self, parent):
        tk.Label(parent, text="Список таблиц:").pack(pady=5)
        self.table_listbox = tk.Listbox(parent, height=8)
        self.table_listbox.pack(fill=tk.X, padx=10)
        
        btn_frame = tk.Frame(parent)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Создать таблицу", command=self.create_table_dialog).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Открыть таблицу", command=self.open_table).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Удалить таблицу", command=self.delete_table).pack(side=tk.LEFT, padx=5)
    
    def create_table_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Создание новой таблицы")
        dialog.geometry("400x350")
        
        tk.Label(dialog, text="Название таблицы:").pack(pady=5)
        entry_table_name = tk.Entry(dialog)
        entry_table_name.pack(pady=5)
        
        tk.Label(dialog, text="Количество столбцов:").pack(pady=5)
        entry_columns_count = tk.Entry(dialog)
        entry_columns_count.pack(pady=5)
        
        columns_frame = tk.Frame(dialog)
        columns_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        
        def on_columns_count():
            try:
                count = int(entry_columns_count.get())
                for widget in columns_frame.winfo_children():
                    widget.destroy()
                self.column_entries = []
                for i in range(count):
                    row_frame = tk.Frame(columns_frame)
                    row_frame.pack(pady=2, fill=tk.X, padx=10)
                    tk.Label(row_frame, text=f"Столбец {i+1} имя:").pack(side=tk.LEFT)
                    entry_name = tk.Entry(row_frame, width=12)
                    entry_name.pack(side=tk.LEFT, padx=5)
                    tk.Label(row_frame, text="Тип:").pack(side=tk.LEFT)
                    combo_type = ttk.Combobox(row_frame, values=["int", "float", "string"], width=10)
                    combo_type.pack(side=tk.LEFT, padx=5)
                    self.column_entries.append((entry_name, combo_type))
            except ValueError:
                messagebox.showerror("Ошибка", "Введите корректное число столбцов.")
        
        tk.Button(dialog, text="Указать столбцы", command=on_columns_count).pack(pady=5)
        
        def on_create():
            table_name = entry_table_name.get().strip()
            if not table_name:
                messagebox.showerror("Ошибка", "Введите имя таблицы.")
                return
            if table_name in self.tables:
                messagebox.showerror("Ошибка", "Такая таблица уже существует.")
                return
            try:
                col_defs = []
                for entry, combo in self.column_entries:
                    col_name = entry.get().strip()
                    col_type_str = combo.get().strip().lower()
                    if not col_name or not col_type_str:
                        raise ValueError("Все поля столбцов должны быть заполнены.")
                    if col_type_str == "int":
                        col_type = TYPE_INT
                    elif col_type_str == "float":
                        col_type = TYPE_FLOAT
                    elif col_type_str == "string":
                        col_type = TYPE_STRING
                    else:
                        raise ValueError("Неверный тип столбца: " + col_type_str)
                    col_defs.append((col_name, col_type))
                # Проверка на уникальность имён столбцов
                col_names = [col_name for col_name, _ in col_defs]
                if len(col_names) != len(set(col_names)):
                    messagebox.showerror("Ошибка", "Названия столбцов должны быть уникальными!")
                    return
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
                return
            
            table = DBTable(table_name, col_defs)
            self.tables[table_name] = table
            self.table_listbox.insert(tk.END, table_name)
            messagebox.showinfo("Успех", f"Таблица {table_name} создана!")
            dialog.destroy()
        
        tk.Button(dialog, text="Создать таблицу", command=on_create).pack(pady=10)
    
    def on_tab_right_click(self, event):
        """Обработчик правого клика по вкладке"""
        # Получаем индекс вкладки
        index = self.notebook.index(f"@{event.x},{event.y}")
        if index is not None:
            # Получаем текст вкладки
            tab_text = self.notebook.tab(index, "text")
            # Если это не вкладка управления таблицами
            if tab_text != "Управление таблицами":
                # Создаем контекстное меню
                menu = tk.Menu(self, tearoff=0)
                menu.add_command(label="Закрыть", command=lambda: self.close_tab_by_index(index))
                menu.post(event.x_root, event.y_root)
    
    def open_table(self):
        selection = self.table_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите таблицу из списка.")
            return
        index = selection[0]
        table_name = self.table_listbox.get(index)
        if table_name in self.table_tabs:
            self.notebook.select(self.table_tabs[table_name])
            # Обновляем данные при переключении на существующую вкладку
            tab = self.table_tabs[table_name]
            tab.rows_data = tab.dbtable.get_all_rows()
            tab.original_rows_data = list(tab.rows_data)
            self.refresh_table_tab(tab)
        else:
            table = self.tables[table_name]
            new_tab = ttk.Frame(self.notebook)
            self.table_tabs[table_name] = new_tab
            self.notebook.add(new_tab, text=table_name)
            self.create_table_tab(new_tab, table)
            # Обновляем данные при создании новой вкладки
            new_tab.rows_data = table.get_all_rows()
            new_tab.original_rows_data = list(new_tab.rows_data)
            self.refresh_table_tab(new_tab)
            self.notebook.select(new_tab)
    
    def create_table_tab(self, parent, table):
        parent.dbtable = table
        parent.rows_data = table.get_all_rows()
        parent.original_rows_data = list(parent.rows_data)
        parent.sort_state = {}
        parent.search_active = False
        parent.search_results = []  # Новое поле для хранения результатов поиска

        # --- Контейнеры для размещения ---
        top_frame = tk.Frame(parent)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        bottom_frame = tk.Frame(parent)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # --- СТРОКА ПОИСКА ---
        search_frame = tk.Frame(top_frame)
        search_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5, 0))
        columns = ["№"] + [col_def[0] for col_def in table.columns_info]
        search_options = ["Вся таблица"] + [col for col in columns if col != "№"]
        parent.search_column = tk.StringVar(value="Вся таблица")
        parent.search_entry = tk.Entry(search_frame, width=20)
        search_combo = ttk.Combobox(search_frame, values=search_options, state="readonly", width=15, textvariable=parent.search_column)
        search_combo.pack(side=tk.LEFT, padx=5)
        parent.search_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(search_frame, text="Поиск", command=lambda: self.search_in_table(parent)).pack(side=tk.LEFT, padx=5)
        tk.Button(search_frame, text="Сбросить", command=lambda: self.reset_search(parent)).pack(side=tk.LEFT, padx=5)

        # Добавляем кнопку закрытия вкладки
        close_button = tk.Button(search_frame, text="✕", width=2, command=lambda: self.close_table_tab(parent))
        close_button.pack(side=tk.RIGHT, padx=5)

        # --- СКРОЛЛИРУЕМАЯ СТРОКА ВВОДА ---
        input_canvas = tk.Canvas(top_frame, height=40)
        input_scroll = tk.Scrollbar(top_frame, orient="horizontal", command=input_canvas.xview)
        input_frame = tk.Frame(input_canvas)
        input_frame_id = input_canvas.create_window((0, 0), window=input_frame, anchor="nw")
        input_canvas.configure(xscrollcommand=input_scroll.set)

        def on_input_frame_configure(event):
            input_canvas.configure(scrollregion=input_canvas.bbox("all"))
        input_frame.bind("<Configure>", on_input_frame_configure)

        input_canvas.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(10, 0))
        input_scroll.pack(side=tk.TOP, fill=tk.X, padx=10)
        
        parent.entry_vars = []
        parent.entry_labels = []
        parent.entry_entries = []
        # Получаем информацию о внешних ключах
        fk_info = {fk['column']: fk for fk in table.get_foreign_keys()}
        for idx, col_def in enumerate(table.columns_info):
            col_name, _ = col_def
            lbl = tk.Label(input_frame, text=f"{col_name}:")
            lbl.pack(side=tk.LEFT, padx=5)
            var = tk.StringVar()
            # Если столбец внешний ключ — делаем Combobox
            if col_name in fk_info:
                fk = fk_info[col_name]
                ref_table_name = fk['referenced_table']
                ref_col_name = fk['referenced_column']
                ref_table = self.tables.get(ref_table_name)
                values = []
                if ref_table:
                    col_idx = None
                    for i, (n, _) in enumerate(ref_table.columns_info):
                        if n == ref_col_name:
                            col_idx = i
                            break
                    if col_idx is not None:
                        values = [str(ref_table.get_value(row, col_idx)) for row in range(ref_table.get_num_rows())]
                ent = ttk.Combobox(input_frame, textvariable=var, values=values, width=10, state="readonly")
            else:
                ent = tk.Entry(input_frame, textvariable=var, width=10)
            ent.pack(side=tk.LEFT, padx=5)
            parent.entry_vars.append(var)
            parent.entry_labels.append(lbl)
            parent.entry_entries.append(ent)

        # --- КНОПКИ ---
        if self.buttons_position == "top":
            buttons_frame = tk.Frame(top_frame)
            buttons_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5, 10))
        else:
            buttons_frame = tk.Frame(bottom_frame)
            buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(5, 10))

        tk.Button(buttons_frame, text="Insert Row", 
                  command=lambda: self.insert_row_in_table(table, parent)).pack(side=tk.LEFT, padx=5)
        tk.Button(buttons_frame, text="Delete Selected Row", 
                  command=lambda: self.delete_selected_row(table, parent)).pack(side=tk.LEFT, padx=5)
        tk.Button(buttons_frame, text="Refresh Table", 
                  command=lambda: self.refresh_table_tab(parent)).pack(side=tk.LEFT, padx=5)
        tk.Button(buttons_frame, text="Add Column", 
                  command=lambda: self.add_column_in_table(table, parent)).pack(side=tk.LEFT, padx=5)
        tk.Button(buttons_frame, text="Delete Column", 
                  command=lambda: self.delete_column_in_table(table, parent)).pack(side=tk.LEFT, padx=5)

        # Добавляем кнопки для работы с внешними ключами
        fk_frame = tk.Frame(buttons_frame)
        fk_frame.pack(side=tk.LEFT, padx=5)
        tk.Button(fk_frame, text="Add Foreign Key", 
                 command=lambda: self.add_foreign_key_dialog(table, parent)).pack(side=tk.LEFT, padx=5)
        tk.Button(fk_frame, text="Remove Foreign Key", 
                 command=lambda: self.remove_foreign_key_dialog(table, parent)).pack(side=tk.LEFT, padx=5)
        tk.Button(fk_frame, text="Show Foreign Keys", 
                 command=lambda: self.show_foreign_keys(table)).pack(side=tk.LEFT, padx=5)

        # --- ТАБЛИЦА ---
        parent.tree = ttk.Treeview(parent, columns=columns, show="headings")
        max_num = max(1, len(parent.rows_data))
        num_digits = len(str(max_num))
        num_width = max(MIN_NUM_WIDTH, 10 * num_digits + 16)
        for col in columns:
            parent.tree.heading(col, text=col)
            if col == "№":
                parent.tree.column(col, width=num_width, anchor="center", stretch=False)
            else:
                parent.tree.column(col, width=100)
        parent.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Сортировка по столбцам ---
        def on_heading_click(event):
            region = parent.tree.identify_region(event.x, event.y)
            if region != "heading":
                return
            col = parent.tree.identify_column(event.x)
            col_index = int(col.replace("#", "")) - 1
            if col_index == 0:
                return  # Не сортируем по '№'
            col_name = parent.tree['columns'][col_index]
            # Сбросить стрелки у всех столбцов
            for c in parent.tree['columns']:
                if c != col_name:
                    parent.tree.heading(c, text=c)
            # Определить текущее состояние сортировки
            state = parent.sort_state.get(col_name, None)
            if state is None:
                # Сортируем текущие данные (результаты поиска или основные данные)
                current_data = parent.search_results if parent.search_active and parent.search_results else parent.rows_data
                current_data.sort(key=lambda row: row[col_index-1])
                parent.sort_state[col_name] = 'asc'
                parent.tree.heading(col_name, text=f"{col_name} ▼")
            elif state == 'asc':
                # Сортируем текущие данные в обратном порядке
                current_data = parent.search_results if parent.search_active and parent.search_results else parent.rows_data
                current_data.sort(key=lambda row: row[col_index-1], reverse=True)
                parent.sort_state[col_name] = 'desc'
                parent.tree.heading(col_name, text=f"{col_name} ▲")
            else:
                # Сбрасываем сортировку, возвращаясь к исходным данным
                if parent.search_active and parent.search_results:
                    parent.search_results = list(parent.dbtable.get_all_rows())
                else:
                    parent.rows_data = list(parent.original_rows_data)
                parent.sort_state[col_name] = None
                parent.tree.heading(col_name, text=col_name)
            for c in parent.tree['columns']:
                if c != col_name:
                    parent.sort_state[c] = None
            self.refresh_table_tab(parent)
        for col in columns:
            parent.tree.heading(col, command=lambda c=col: None)
        parent.tree.bind("<Button-1>", on_heading_click)

        # --- Контекстное меню для переименования столбца ---
        def on_heading_right_click(event):
            region = parent.tree.identify_region(event.x, event.y)
            if region != "heading":
                return
            col = parent.tree.identify_column(event.x)
            col_index = int(col.replace("#", "")) - 1
            if col_index == 0:
                return  # Нельзя переименовать '№'
            col_name = parent.tree['columns'][col_index]
            menu = tk.Menu(parent, tearoff=0)
            menu.add_command(label=f"Переименовать столбец '{col_name}'", command=lambda: self.rename_column(parent, table, col_index))
            menu.tk_popup(event.x_root, event.y_root)
        parent.tree.bind("<Button-3>", on_heading_right_click)
        
        parent.tree.bind("<Double-1>", lambda event, t=table, p=parent: self.on_cell_double_click(event, t, p))
    
    def insert_row_in_table(self, table, tab):
        values = []
        for var, col_def in zip(tab.entry_vars, table.columns_info):
            col_name, col_type = col_def
            val = var.get().strip()
            try:
                if val == '':
                    if col_type == TYPE_INT:
                        values.append(0)
                    elif col_type == TYPE_FLOAT:
                        values.append(0.0)
                    elif col_type == TYPE_STRING:
                        values.append('')
                    else:
                        values.append(None)
                else:
                    if col_type == TYPE_INT:
                        values.append(int(val))
                    elif col_type == TYPE_FLOAT:
                        values.append(float(val))
                    elif col_type == TYPE_STRING:
                        values.append(val)
            except Exception:
                messagebox.showerror("Ошибка", f"Неверное значение для столбца {col_name}")
                return
        table.insert(values)
        tab.rows_data = table.get_all_rows()
        tab.original_rows_data = list(tab.rows_data)
        self.apply_active_sort(tab)
        self.refresh_table_tab(tab)
        for var in tab.entry_vars:
            var.set('')
    
    def delete_selected_row(self, table, tab):
        selected = tab.tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите строку для удаления.")
            return
        index = tab.tree.index(selected[0])
        if index < 0 or index >= len(tab.rows_data):
            messagebox.showerror("Ошибка", f"Неверный индекс строки: {index}. Всего строк: {len(tab.rows_data)}")
            return
        old_count = len(tab.rows_data)
        table.delete(index)
        tab.rows_data = table.get_all_rows()
        tab.original_rows_data = list(tab.rows_data)
        self.apply_active_sort(tab)
        self.refresh_table_tab(tab)
        if len(tab.rows_data) == old_count:
            messagebox.showerror("Ошибка", "Не удалось удалить строку.")
    
    def refresh_table_tab(self, tab):
        # Проверяем, есть ли активная сортировка
        active_sort = False
        if hasattr(tab, 'sort_state'):
            for v in tab.sort_state.values():
                if v is not None:
                    active_sort = True
                    break

        # Определяем, какие данные показывать
        if tab.search_active and tab.search_results:
            display_data = tab.search_results
        else:
            if not active_sort:
                tab.rows_data = tab.dbtable.get_all_rows()
                if not hasattr(tab, 'original_rows_data') or len(tab.original_rows_data) != len(tab.rows_data):
                    tab.original_rows_data = list(tab.rows_data)
            display_data = tab.rows_data

        self.apply_active_sort(tab)
        table_columns = ["№"] + [col_def[0] for col_def in tab.dbtable.columns_info]
        current_columns = list(tab.tree['columns'])
        if current_columns != table_columns:
            self.recreate_table_tab(tab, tab.dbtable)
            return

        for item in tab.tree.get_children():
            tab.tree.delete(item)

        for idx, row in enumerate(display_data, 1):
            tab.tree.insert("", tk.END, values=(idx,) + row)

        # Динамическая ширина для столбца "№" с stretch=False
        max_num = max(1, len(display_data))
        num_digits = len(str(max_num))
        num_width = max(MIN_NUM_WIDTH, 10 * num_digits + 16)
        tab.tree.column("№", width=num_width, anchor="center", stretch=False)

        # --- Обновление значений в Combobox для внешних ключей ---
        fk_info = {fk['column']: fk for fk in tab.dbtable.get_foreign_keys()}
        for idx, (var, ent) in enumerate(zip(tab.entry_vars, tab.entry_entries)):
            col_name, _ = tab.dbtable.columns_info[idx]
            if col_name in fk_info and isinstance(ent, ttk.Combobox):
                fk = fk_info[col_name]
                ref_table_name = fk['referenced_table']
                ref_col_name = fk['referenced_column']
                ref_table = self.tables.get(ref_table_name)
                values = []
                if ref_table:
                    col_idx = None
                    for i, (n, _) in enumerate(ref_table.columns_info):
                        if n == ref_col_name:
                            col_idx = i
                            break
                    if col_idx is not None:
                        values = [str(ref_table.get_value(row, col_idx)) for row in range(ref_table.get_num_rows())]
                ent['values'] = values
    
    def add_column_in_table(self, table, tab):
        dialog = tk.Toplevel(self)
        dialog.title("Добавление столбца")
        dialog.geometry("300x200")
        
        tk.Label(dialog, text="Имя столбца:").pack(pady=5)
        entry_col_name = tk.Entry(dialog)
        entry_col_name.pack(pady=5)
        
        tk.Label(dialog, text="Тип (int, float, string):").pack(pady=5)
        combo_col_type = ttk.Combobox(dialog, values=["int", "float", "string"], width=10)
        combo_col_type.pack(pady=5)
        
        def on_add():
            col_name = entry_col_name.get().strip()
            col_type_str = combo_col_type.get().strip().lower()
            if not col_name or not col_type_str:
                messagebox.showerror("Ошибка", "Заполните все поля.")
                return
            # Проверка на уникальность имени столбца
            if col_name in [col[0] for col in table.columns_info]:
                messagebox.showerror("Ошибка", "Столбец с таким именем уже существует!")
                return
            if col_type_str == "int":
                col_type = TYPE_INT
                default_value = 0
            elif col_type_str == "float":
                col_type = TYPE_FLOAT
                default_value = 0.0
            elif col_type_str == "string":
                col_type = TYPE_STRING
                default_value = ""
            else:
                messagebox.showerror("Ошибка", "Неверный тип столбца.")
                return
            ret = table.add_column(col_name, col_type, default_value)
            if ret != 0:
                messagebox.showerror("Ошибка", "Не удалось добавить столбец в таблицу.")
                return
            tab.rows_data = table.get_all_rows()
            tab.original_rows_data = list(tab.rows_data)
            self.apply_active_sort(tab)
            self.recreate_table_tab(tab, table)
            dialog.destroy()
        
        tk.Button(dialog, text="Добавить", command=on_add).pack(pady=10)
    
    def delete_column_in_table(self, table, tab):
        dialog = tk.Toplevel(self)
        dialog.title("Удаление столбца")
        dialog.geometry("300x150")
        
        tk.Label(dialog, text="Выберите столбец для удаления:").pack(pady=5)
        col_names = [col_def[0] for col_def in table.columns_info]
        combo = ttk.Combobox(dialog, values=col_names, state="readonly")
        combo.pack(pady=5)
        
        def on_delete():
            selected = combo.get()
            if not selected:
                messagebox.showerror("Ошибка", "Выберите столбец.")
                return
            old_count = len(table.columns_info)
            table.drop_column(selected)
            tab.rows_data = table.get_all_rows()
            tab.original_rows_data = list(tab.rows_data)
            self.apply_active_sort(tab)
            self.recreate_table_tab(tab, table)
            dialog.destroy()
            if len(table.columns_info) == old_count:
                messagebox.showerror("Ошибка", "Не удалось удалить столбец из таблицы.")
        
        tk.Button(dialog, text="Удалить", command=on_delete).pack(pady=10)
    
    def recreate_table_tab(self, tab, table):
        for widget in tab.winfo_children():
            widget.destroy()
        self.create_table_tab(tab, table)
        self.refresh_table_tab(tab)
        # Динамическая ширина для столбца "№" после пересоздания вкладки с минимальным значением
        max_num = max(1, len(tab.rows_data))
        num_digits = len(str(max_num))
        num_width = max(MIN_NUM_WIDTH, 10 * num_digits + 16)
        tab.tree.column("№", width=num_width, anchor="center", stretch=False)
    
    def on_cell_double_click(self, event, table, tab):
        region = tab.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = tab.tree.identify_column(event.x)
        row = tab.tree.identify_row(event.y)
        if not row or not col:
            return
        col_index = int(col.replace("#", "")) - 1
        if col_index == 0:
            # Клик по столбцу '№' — ничего не делаем
            return
        row_id = tab.tree.index(row)
        x, y, width, height = tab.tree.bbox(row, col)
        edit = tk.Entry(tab.tree)
        current_value = tab.tree.item(row, "values")[col_index]
        edit.insert(0, current_value)
        edit.place(x=x, y=y, width=width, height=height)
        edit.focus_set()
        
        def on_return(event):
            new_value = edit.get()
            old_rows = tab.dbtable.get_all_rows()
            table.update(row_id, col_index - 1, new_value)
            tab.rows_data = tab.dbtable.get_all_rows()
            self.refresh_table_tab(tab)
            if tab.rows_data[row_id][col_index - 1] == old_rows[row_id][col_index - 1]:
                messagebox.showerror("Ошибка", f"Не удалось обновить ячейку ({row_id}, {col_index - 1}).")
            edit.destroy()
        
        edit.bind("<Return>", on_return)
        edit.bind("<FocusOut>", lambda event: edit.destroy())

    def rename_column(self, parent, table, col_index):
        old_name = table.columns_info[col_index - 1][0]
        new_name = simpledialog.askstring("Переименование столбца", f"Введите новое имя для столбца '{old_name}':", parent=parent)
        if not new_name:
            return
        new_name = new_name.strip()
        if new_name == "№":
            messagebox.showerror("Ошибка", "Имя '№' зарезервировано!")
            return
        if new_name in [col[0] for col in table.columns_info]:
            messagebox.showerror("Ошибка", "Столбец с таким именем уже существует!")
            return
        # Меняем имя в columns_info
        table.columns_info[col_index - 1] = (new_name, table.columns_info[col_index - 1][1])
        # Пересоздаём вкладку для корректного обновления всего интерфейса
        self.recreate_table_tab(parent, table)

    def update_buttons_position(self):
        self.buttons_position = self.buttons_position_var.get()
        # Пересоздать все открытые вкладки
        for tab in self.table_tabs.values():
            self.recreate_table_tab(tab, tab.dbtable)

    def apply_active_sort(self, tab):
        if hasattr(tab, 'sort_state'):
            for col_name, state in tab.sort_state.items():
                if state in ('asc', 'desc'):
                    columns = ["№"] + [col_def[0] for col_def in tab.dbtable.columns_info]
                    if col_name not in columns:
                        continue
                    col_index = columns.index(col_name)
                    reverse = (state == 'desc')
                    # Сортируем текущие данные
                    current_data = tab.search_results if tab.search_active and tab.search_results else tab.rows_data
                    current_data.sort(key=lambda row: row[col_index-1], reverse=reverse)
                    # Обновить стрелку
                    arrow = "▼" if state == 'asc' else "▲"
                    for c in columns:
                        if c == col_name:
                            tab.tree.heading(c, text=f"{c} {arrow}")
                        else:
                            tab.tree.heading(c, text=c)
                    break

    def delete_table(self):
        selection = self.table_listbox.curselection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите таблицу для удаления.")
            return
        index = selection[0]
        table_name = self.table_listbox.get(index)
        if messagebox.askyesno("Подтверждение", f"Удалить таблицу '{table_name}'?"):
            # Удалить из self.tables
            if table_name in self.tables:
                del self.tables[table_name]
            # Удалить вкладку, если открыта
            if table_name in self.table_tabs:
                tab = self.table_tabs[table_name]
                self.notebook.forget(tab)
                del self.table_tabs[table_name]
            # Удалить из Listbox
            self.table_listbox.delete(index)

    def search_in_table(self, tab):
        query = tab.search_entry.get().strip()
        if not query:
            return
        col_name = tab.search_column.get()
        all_rows = tab.dbtable.get_all_rows()
        filtered = []
        if col_name == "Вся таблица":
            for row in all_rows:
                if any(query.lower() in str(cell).lower() for cell in row):
                    filtered.append(row)
        else:
            # Определяем индекс столбца в данных (без учёта '№')
            col_names = [col_def[0] for col_def in tab.dbtable.columns_info]
            try:
                col_index = col_names.index(col_name)
            except ValueError:
                pass
            for row in all_rows:
                if query.lower() in str(row[col_index]).lower():
                    filtered.append(row)
        
        if not filtered:
            messagebox.showinfo("Результаты поиска", "По вашему запросу ничего не найдено")
            return
            
        tab.search_results = filtered  # Сохраняем результаты поиска
        tab.search_active = True
        tab.sort_state = {}
        self.refresh_table_tab(tab)

    def reset_search(self, tab):
        tab.search_results = []  # Очищаем результаты поиска
        tab.search_active = False
        tab.sort_state = {}
        self.refresh_table_tab(tab)

    def save_database(self):
        """Сохранение всей базы данных в JSON файл"""
        if not self.tables:
            messagebox.showwarning("Внимание", "Нет таблиц для сохранения.")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Сохранить базу данных"
        )
        
        if not file_path:
            return
            
        try:
            db_data = {}
            for table_name, table in self.tables.items():
                table_data = {
                    'columns_info': table.columns_info,
                    'rows': table.get_all_rows(),
                    'foreign_keys': []  # Добавляем информацию о внешних ключах
                }
                
                # Сохраняем информацию о внешних ключах
                for fk in table.get_foreign_keys():
                    table_data['foreign_keys'].append({
                        'column': fk['column'],
                        'referenced_table': fk['referenced_table'],
                        'referenced_column': fk['referenced_column']
                    })
                
                db_data[table_name] = table_data
                
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(db_data, f, ensure_ascii=False, indent=2)
                
            messagebox.showinfo("Успех", "База данных успешно сохранена!")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить базу данных: {str(e)}")

    def load_database(self):
        """Загрузка базы данных из JSON файла"""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Загрузить базу данных"
        )
        if not file_path:
            return
        try:
            import db_interface
            if hasattr(db_interface, 'lib') and hasattr(db_interface.lib, 'cleanup_database'):
                db_interface.lib.cleanup_database()
                db_interface.lib.init_database()
            # Очищаем текущие данные
            self.tables.clear()
            self.table_listbox.delete(0, tk.END)
            for tab in list(self.table_tabs.values()):
                self.notebook.forget(tab)
            self.table_tabs.clear()
            with open(file_path, 'r', encoding='utf-8') as f:
                db_data = json.load(f)
            # Загружаем новые данные
            for table_name, table_data in db_data.items():
                columns_info = table_data['columns_info']
                rows = table_data['rows']
                table = DBTable(table_name, columns_info)
                if not table.table_ptr:
                    messagebox.showerror("Ошибка", f"Не удалось создать таблицу {table_name} при загрузке базы данных.")
                    continue
                self.tables[table_name] = table
                self.table_listbox.insert(tk.END, table_name)
                for row in rows:
                    table.insert(row)
                if 'foreign_keys' in table_data:
                    for fk_data in table_data['foreign_keys']:
                        ret = table.add_foreign_key(
                            fk_data['column'],
                            fk_data['referenced_table'],
                            fk_data['referenced_column']
                        )
                        if ret != 0:
                            messagebox.showwarning("Предупреждение", 
                                f"Не удалось восстановить внешний ключ для столбца {fk_data['column']} в таблице {table_name}")
            messagebox.showinfo("Успех", "База данных успешно загружена!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить базу данных: {str(e)}")

    def close_tab_by_index(self, index):
        """Закрытие вкладки по индексу"""
        # Получаем текст вкладки
        tab_text = self.notebook.tab(index, "text")
        # Находим соответствующую вкладку
        if tab_text in self.table_tabs:
            self.notebook.forget(index)
            del self.table_tabs[tab_text]
            # Удаляем выделение в списке таблиц
            for i in range(self.table_listbox.size()):
                if self.table_listbox.get(i) == tab_text:
                    self.table_listbox.selection_clear(0, tk.END)
                    break

    def close_table_tab(self, tab):
        """Закрытие вкладки таблицы"""
        # Находим имя таблицы по вкладке
        table_name = None
        for name, t in self.table_tabs.items():
            if t == tab:
                table_name = name
                break
        
        if table_name:
            # Удаляем вкладку
            self.notebook.forget(tab)
            del self.table_tabs[table_name]
            # Удаляем выделение в списке таблиц
            for i in range(self.table_listbox.size()):
                if self.table_listbox.get(i) == table_name:
                    self.table_listbox.selection_clear(0, tk.END)
                    break

    def add_foreign_key_dialog(self, table, parent):
        """Диалог добавления внешнего ключа"""
        dialog = tk.Toplevel(self)
        dialog.title("Add Foreign Key")
        dialog.geometry("400x300")

        # Выбор столбца текущей таблицы
        tk.Label(dialog, text="Select column:").pack(pady=5)
        col_names = [col_def[0] for col_def in table.columns_info]
        col_combo = ttk.Combobox(dialog, values=col_names, state="readonly")
        col_combo.pack(pady=5)

        # Выбор таблицы для связи
        tk.Label(dialog, text="Select referenced table:").pack(pady=5)
        ref_tables = [name for name in self.tables.keys() if name != table.name.decode("utf-8")]
        ref_table_combo = ttk.Combobox(dialog, values=ref_tables, state="readonly")
        ref_table_combo.pack(pady=5)

        # Выбор столбца в связанной таблице
        tk.Label(dialog, text="Select referenced column:").pack(pady=5)
        ref_col_combo = ttk.Combobox(dialog, state="readonly")
        ref_col_combo.pack(pady=5)

        def get_type_name(type_id):
            if type_id == TYPE_INT:
                return "int"
            elif type_id == TYPE_FLOAT:
                return "float"
            elif type_id == TYPE_STRING:
                return "string"
            return "unknown"

        def on_ref_table_select(event):
            selected = ref_table_combo.get()
            if selected:
                ref_cols = [col[0] for col in self.tables[selected].columns_info]
                ref_col_combo['values'] = ref_cols

        ref_table_combo.bind('<<ComboboxSelected>>', on_ref_table_select)

        def on_add():
            col_name = col_combo.get()
            ref_table = ref_table_combo.get()
            ref_col = ref_col_combo.get()

            if not all([col_name, ref_table, ref_col]):
                messagebox.showerror("Error", "Please fill all fields")
                return

            # Проверяем типы данных
            col_type = None
            ref_col_type = None
            
            # Находим тип столбца в текущей таблице
            for col_def in table.columns_info:
                if col_def[0] == col_name:
                    col_type = col_def[1]
                    break
                
            # Находим тип столбца в связанной таблице
            for col_def in self.tables[ref_table].columns_info:
                if col_def[0] == ref_col:
                    ref_col_type = col_def[1]
                    break

            if col_type != ref_col_type:
                messagebox.showerror("Error", 
                    f"Типы данных не совпадают!\n"
                    f"Текущий столбец: {col_name} ({get_type_name(col_type)})\n"
                    f"Связанный столбец: {ref_col} ({get_type_name(ref_col_type)})")
                return

            ret = table.add_foreign_key(col_name, ref_table, ref_col)
            if ret == 0:
                messagebox.showinfo("Success", "Foreign key added successfully")
                dialog.destroy()
                self.recreate_table_tab(parent, table)
            else:
                messagebox.showerror("Error", "Failed to add foreign key")

        tk.Button(dialog, text="Add", command=on_add).pack(pady=10)

    def remove_foreign_key_dialog(self, table, parent):
        """Диалог удаления внешнего ключа"""
        dialog = tk.Toplevel(self)
        dialog.title("Remove Foreign Key")
        dialog.geometry("300x150")

        # Получаем список столбцов с внешними ключами
        fk_columns = []
        for fk in table.get_foreign_keys():
            fk_columns.append(fk['column'])

        if not fk_columns:
            messagebox.showinfo("Info", "No foreign keys found")
            dialog.destroy()
            return

        tk.Label(dialog, text="Select foreign key to remove:").pack(pady=5)
        col_combo = ttk.Combobox(dialog, values=fk_columns, state="readonly")
        col_combo.pack(pady=5)

        def on_remove():
            col_name = col_combo.get()
            if not col_name:
                messagebox.showerror("Error", "Please select a column")
                return

            ret = table.remove_foreign_key(col_name)
            if ret == 0:
                messagebox.showinfo("Success", "Foreign key removed successfully")
                dialog.destroy()
                self.recreate_table_tab(parent, table)
            else:
                messagebox.showerror("Error", "Failed to remove foreign key")

        tk.Button(dialog, text="Remove", command=on_remove).pack(pady=10)

    def show_foreign_keys(self, table):
        """Показать информацию о внешних ключах"""
        fk_list = table.get_foreign_keys()
        if not fk_list:
            messagebox.showinfo("Foreign Keys", "No foreign keys found")
            return

        # Создаем окно с информацией
        dialog = tk.Toplevel(self)
        dialog.title("Foreign Keys")
        dialog.geometry("400x300")

        # Создаем текстовое поле с прокруткой
        text = tk.Text(dialog, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(dialog, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        # Размещаем элементы
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Добавляем информацию о внешних ключах
        for fk in fk_list:
            text.insert(tk.END, f"Column: {fk['column']}\n")
            text.insert(tk.END, f"References: {fk['referenced_table']}.{fk['referenced_column']}\n")
            text.insert(tk.END, "-" * 40 + "\n")

        text.configure(state='disabled')  # Делаем текст только для чтения

    def save_table(self, table_name):
        """Сохраняет таблицу в JSON файл"""
        table = self.tables.get(table_name)
        if not table:
            messagebox.showerror("Ошибка", f"Таблица {table_name} не найдена")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title=f"Сохранить таблицу {table_name}"
        )
        
        if filename:
            try:
                save_table_to_json(table, filename)
                messagebox.showinfo("Успех", f"Таблица {table_name} успешно сохранена")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка при сохранении таблицы: {str(e)}")

    def load_table(self):
        """Загружает таблицу из JSON файла"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Загрузить таблицу"
        )
        
        if filename:
            try:
                table = load_table_from_json(filename)
                table_name = table.name.decode("utf-8")
                
                # Добавляем таблицу в базу данных
                if lib.add_table_to_db(None, table) != 0:
                    messagebox.showwarning("Предупреждение", 
                        f"Не удалось добавить таблицу {table_name} в базу данных")
                
                # Обновляем GUI
                self.tables[table_name] = table
                self.update_table_list()
                self.show_table(table_name)
                messagebox.showinfo("Успех", f"Таблица {table_name} успешно загружена")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка при загрузке таблицы: {str(e)}")

    def make_backup(self, silent=False):
        """Создать резервную копию базы данных (JSON-файл) в папке backups"""
        try:
            if not self.tables:
                if not silent:
                    messagebox.showwarning("Внимание", "Нет таблиц для резервного копирования.")
                return
            backup_dir = os.path.join(os.getcwd(), 'backups')
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            backup_name = f'backup_{timestamp}.json'
            backup_path = os.path.join(backup_dir, backup_name)
            db_data = {}
            for table_name, table in self.tables.items():
                table_data = {
                    'columns_info': table.columns_info,
                    'rows': table.get_all_rows(),
                    'foreign_keys': []
                }
                for fk in table.get_foreign_keys():
                    table_data['foreign_keys'].append({
                        'column': fk['column'],
                        'referenced_table': fk['referenced_table'],
                        'referenced_column': fk['referenced_column']
                    })
                db_data[table_name] = table_data
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(db_data, f, ensure_ascii=False, indent=2)
            self._cleanup_old_backups(backup_dir)
            if not silent:
                messagebox.showinfo("Резервное копирование", f"Резервная копия базы данных создана: {backup_name}")
        except Exception as e:
            if not silent:
                messagebox.showerror("Ошибка резервного копирования", str(e))

    def _auto_backup_loop(self):
        while True:
            time.sleep(self.backup_interval)
            try:
                self.make_backup(silent=True)
            except Exception:
                pass  # Не показываем messagebox из потока, чтобы не мешать GUI

    def _cleanup_old_backups(self, backup_dir):
        backups = [f for f in os.listdir(backup_dir) if f.startswith('backup_') and f.endswith('.json')]
        backups.sort()
        if len(backups) > 10:
            for old in backups[:-10]:
                try:
                    os.remove(os.path.join(backup_dir, old))
                except Exception:
                    pass

class TableTab(tk.Frame):
    def __init__(self, master, table_name, columns):
        super().__init__(master)
        self.table = DBTable(table_name, columns)
        
        self.row_entry = tk.Entry(self, width=5)
        self.row_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(self, text="Номер строки (1-based) для удаления").pack(side=tk.LEFT)
        tk.Button(self, text="Удалить строку", command=self.delete_selected_row).pack(side=tk.LEFT, padx=10)
        
        tk.Button(self, text="Вывести таблицу", command=self.refresh_table).pack(side=tk.LEFT, padx=10)
        
        self.output = tk.Text(self, height=10, width=60)
        self.output.pack(padx=10, pady=10)
    
    def delete_selected_row(self):
        row_str = self.row_entry.get()
        try:
            user_index = int(row_str)
            if user_index <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Ошибка", "Укажите корректный номер строки (целое положительное число)")
            return
        self.delete_row_gui(user_index)
    
    def delete_row_gui(self, user_index):
        index = user_index - 1
        ret = self.table.delete(index)
        if ret != 0:
            messagebox.showerror("Ошибка", "Ошибка при удалении строки.")
        else:
            messagebox.showinfo("Информация", f"Строка {user_index} успешно удалена.")
        self.refresh_table()
    
    def refresh_table(self):
        self.output.delete("1.0", tk.END)
        self.table.print_table()

if __name__ == "__main__":
    app = TableManager()
    app.mainloop()
