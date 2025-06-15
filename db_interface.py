import ctypes
from ctypes import c_int, c_float, c_char_p, c_char, Structure, POINTER, Union, c_void_p
import os
import json
import sys

TYPE_INT    = 0
TYPE_FLOAT  = 1
TYPE_STRING = 2

class DataValue(Union):
    _fields_ = [
        ("i", c_int),
        ("f", c_float),
        ("s", c_char_p)
    ]


class Column(Structure):
    _fields_ = [
        ("name", c_char * 50),
        ("type", c_int),
        ("is_primary_key", c_int),
        ("is_foreign_key", c_int),
        ("foreign_key", c_void_p)
    ]

class ForeignKey(Structure):
    _fields_ = [
        ("referenced_table", c_char * 50),
        ("referenced_column", c_char * 50),
        ("column_index", c_int)
    ]

class Row(Structure):
    _fields_ = [
        ("values", POINTER(DataValue))
    ]

class Table(Structure):
    _fields_ = [
        ("name", c_char * 50),
        ("columns", POINTER(Column)),
        ("num_columns", c_int),
        ("rows", POINTER(Row)),
        ("num_rows", c_int),
        ("max_rows", c_int),
        ("foreign_keys", POINTER(POINTER(ForeignKey))),
        ("num_foreign_keys", c_int)
    ]

# Получаем путь к папке, где находится этот скрипт
base_dir = os.path.dirname(os.path.abspath(__file__))

# В зависимости от ОС выбираем имя библиотеки
if sys.platform == "win32":
    libname = "mydb.dll"
else:
    libname = "mydb.so"

# Формируем полный путь к библиотеке
lib_path = os.path.join(base_dir, libname)

# Загружаем библиотеку
lib = ctypes.cdll.LoadLibrary(lib_path)

lib.transform_table.argtypes = [POINTER(Table), POINTER(Column), c_int]
lib.transform_table.restype  = POINTER(Table)

lib.create_table.argtypes = [c_char_p, POINTER(Column), c_int]
lib.create_table.restype  = POINTER(Table)

lib.insert_row.argtypes = [POINTER(Table), POINTER(DataValue)]
lib.insert_row.restype  = c_int

lib.print_table.argtypes = [POINTER(Table)]
lib.print_table.restype  = None

lib.update_row.argtypes = [POINTER(Table), c_int, c_int, DataValue]
lib.update_row.restype  = c_int

lib.delete_row.argtypes = [POINTER(Table), c_int]
lib.delete_row.restype  = c_int

lib.free_table.argtypes = [POINTER(Table)]
lib.free_table.restype  = None

lib.add_column.argtypes = [POINTER(Table), c_char_p, c_int, DataValue]
lib.add_column.restype  = c_int

lib.drop_column.argtypes = [POINTER(Table), c_char_p]
lib.drop_column.restype  = c_int

lib.add_foreign_key.argtypes = [POINTER(Table), c_char_p, c_char_p, c_char_p]
lib.add_foreign_key.restype = c_int

lib.remove_foreign_key.argtypes = [POINTER(Table), c_char_p]
lib.remove_foreign_key.restype = c_int

lib.validate_foreign_keys.argtypes = [POINTER(Table)]
lib.validate_foreign_keys.restype = c_int

# Добавляем определения для новых функций
lib.init_database.argtypes = []
lib.init_database.restype = None

lib.cleanup_database.argtypes = []
lib.cleanup_database.restype = None

lib.add_table_to_db.argtypes = [c_void_p, POINTER(Table)]
lib.add_table_to_db.restype = c_int

# Добавляем определения для функций транзакций
lib.begin_transaction.argtypes = []
lib.begin_transaction.restype = c_void_p

lib.commit_transaction.argtypes = [c_void_p]
lib.commit_transaction.restype = c_int

lib.rollback_transaction.argtypes = [c_void_p]
lib.rollback_transaction.restype = None

# Инициализируем базу данных при импорте модуля
lib.init_database()

class DBTable:
    def __init__(self, name, columns):
        """
        Создаёт таблицу с заданным именем и списком столбцов.
        Аргумент columns – список кортежей: (имя_столбца, тип),
        где тип – одно из значений: TYPE_INT, TYPE_FLOAT, TYPE_STRING.
        """
        self.name = name.encode("utf-8")
        self.columns_info = columns  
        self.num_columns = len(columns)

        columns_array = (Column * self.num_columns)()
        for i, (col_name, col_type) in enumerate(columns):
            encoded_name = col_name.encode("utf-8")
            padded_name = (encoded_name + b'\0' * 50)[:50]
            columns_array[i].name = padded_name
            columns_array[i].type = col_type
            columns_array[i].is_primary_key = 0
            columns_array[i].is_foreign_key = 0
            columns_array[i].foreign_key = None

        self.table_ptr = lib.create_table(self.name, columns_array, self.num_columns)
        
        # Добавляем таблицу в базу данных
        if self.table_ptr:
            ret = lib.add_table_to_db(None, self.table_ptr)
            if ret != 0:
                from tkinter import messagebox
                messagebox.showerror("Ошибка", "Не удалось добавить таблицу в базу данных.")
                lib.free_table(self.table_ptr)
                self.table_ptr = None

    def insert(self, values):
        """
        Вставляет строку в таблицу.
        values – список значений (согласно порядку столбцов).
        """
        if len(values) != self.num_columns:
            from tkinter import messagebox
            messagebox.showerror("Ошибка", "Количество значений не совпадает с количеством столбцов.")
            return -1

        values_array = (DataValue * self.num_columns)()
        for i, val in enumerate(values):
            col_type = self.columns_info[i][1]
            if col_type == TYPE_INT:
                values_array[i].i = int(val) if val is not None else 0
            elif col_type == TYPE_FLOAT:
                values_array[i].f = float(val) if val is not None else 0.0
            elif col_type == TYPE_STRING:
                if val is None:
                    values_array[i].s = None
                elif isinstance(val, str):
                    values_array[i].s = val.encode('utf-8')
                else:
                    values_array[i].s = str(val).encode('utf-8')
        ret = lib.insert_row(self.table_ptr, values_array)
        if ret != 0:
            from tkinter import messagebox
            messagebox.showerror("Ошибка", "Ошибка при вставке строки.")
        return ret

    def update(self, row_index, col_index, new_value):
        """
        Обновляет значение в таблице для заданной строки (row_index)
        и столбца (col_index). new_value должен соответствовать типу столбца.
        """
        col_type = self.columns_info[col_index][1]
        dv = DataValue()
        if col_type == TYPE_INT:
            dv.i = int(new_value) if new_value is not None else 0
        elif col_type == TYPE_FLOAT:
            dv.f = float(new_value) if new_value is not None else 0.0
        elif col_type == TYPE_STRING:
            if new_value is None:
                dv.s = None
            elif isinstance(new_value, str):
                dv.s = new_value.encode('utf-8')
            else:
                dv.s = str(new_value).encode('utf-8')
        ret = lib.update_row(self.table_ptr, row_index, col_index, dv)
        if ret != 0:
            from tkinter import messagebox
            messagebox.showerror("Ошибка", "Ошибка при обновлении строки.")
        return ret

    def delete(self, row_index):
        """
        Удаляет строку с индексом row_index.
        """
        ret = lib.delete_row(self.table_ptr, row_index)
        if ret != 0:
            from tkinter import messagebox
            messagebox.showerror("Ошибка", "Ошибка при удалении строки.")
        return ret

    def print_table(self):
        """
        Вызывает C-функцию для вывода таблицы в консоль.
        """
        lib.print_table(self.table_ptr)

    def free(self):
        """
        Освобождает память, выделенную под таблицу.
        """
        lib.free_table(self.table_ptr)
        self.table_ptr = None

    def transform(self, new_columns):
        """
        Преобразует таблицу к новой схеме.
        new_columns – список новых кортежей (имя, тип).
        Возвращает новый экземпляр DBTable.
        """
        num_columns = len(new_columns)
        columns_array = (Column * num_columns)()
        for i, (col_name, col_type) in enumerate(new_columns):
            encoded_name = col_name.encode("utf-8")
            padded_name = (encoded_name + b'\0' * 50)[:50]
            columns_array[i].name = padded_name
            columns_array[i].type = col_type
        new_table_ptr = lib.transform_table(self.table_ptr, columns_array, num_columns)
        new_dbtable = DBTable.__new__(DBTable)
        new_dbtable.table_ptr = new_table_ptr
        new_dbtable.columns_info = new_columns
        new_dbtable.name = self.name
        new_dbtable.num_columns = num_columns
        return new_dbtable


    def add_column(self, col_name, new_type, default_value):
        dv = DataValue()
        if new_type == TYPE_INT:
            dv.i = int(default_value)
        elif new_type == TYPE_FLOAT:
            dv.f = float(default_value)
        elif new_type == TYPE_STRING:
            dv.s = default_value.encode("utf-8")  
        else:
            from tkinter import messagebox
            messagebox.showerror("Ошибка", "Неизвестный тип столбца")
            return -1
        ret = lib.add_column(self.table_ptr, col_name.encode("utf-8"), new_type, dv)
        if ret != 0:
            from tkinter import messagebox
            messagebox.showerror("Ошибка", "Не удалось добавить столбец в таблицу.")
            return ret
        self.columns_info.append((col_name, new_type))
        return 0


    def drop_column(self, col_name):
        """
        Удаляет столбец из таблицы по его имени.
        """
        ret = lib.drop_column(self.table_ptr, col_name.encode("utf-8"))
        if ret != 0:
            from tkinter import messagebox
            messagebox.showerror("Ошибка", "Не удалось удалить столбец из таблицы.")
        else:
            self.columns_info = [col for col in self.columns_info if col[0] != col_name]
        return ret

    def get_value(self, row_idx, col_idx):
        # Получить значение ячейки из C-структуры
        class RowStruct(ctypes.Structure):
            _fields_ = [("values", ctypes.POINTER(DataValue))]
        class TableStruct(ctypes.Structure):
            _fields_ = [("name", ctypes.c_char * 50),
                        ("columns", ctypes.c_void_p),
                        ("num_columns", ctypes.c_int),
                        ("rows", ctypes.POINTER(RowStruct)),
                        ("num_rows", ctypes.c_int),
                        ("max_rows", ctypes.c_int)]
        t = TableStruct.from_address(ctypes.addressof(self.table_ptr.contents))
        row = t.rows[row_idx]
        col_type = self.columns_info[col_idx][1]
        if col_type == TYPE_INT:
            return row.values[col_idx].i
        elif col_type == TYPE_FLOAT:
            return row.values[col_idx].f
        elif col_type == TYPE_STRING:
            s = row.values[col_idx].s
            if s:
                try:
                    # Пробуем декодировать как UTF-8
                    return s.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        # Если не получилось, пробуем cp1251
                        return s.decode('cp1251')
                    except UnicodeDecodeError:
                        # Если и это не получилось, возвращаем как есть
                        return str(s)
            return ""

    def get_all_rows(self):
        """
        Возвращает все строки таблицы как список кортежей Python.
        """
        result = []
        num_rows = self.get_num_rows()
        num_cols = len(self.columns_info)
        for row_idx in range(num_rows):
            row = []
            for col_idx, (col_name, col_type) in enumerate(self.columns_info):
                val = self.get_value(row_idx, col_idx)
                row.append(val)
            result.append(tuple(row))
        return result

    def get_num_rows(self):
        # Получить количество строк из C-структуры
        class TableStruct(ctypes.Structure):
            _fields_ = [("name", ctypes.c_char * 50),
                        ("columns", ctypes.c_void_p),
                        ("num_columns", ctypes.c_int),
                        ("rows", ctypes.c_void_p),
                        ("num_rows", ctypes.c_int),
                        ("max_rows", ctypes.c_int)]
        t = TableStruct.from_address(ctypes.addressof(self.table_ptr.contents))
        return t.num_rows

    def add_foreign_key(self, column_name, ref_table_name, ref_column_name):
        """Добавить внешний ключ"""
        # Проверяем, не существует ли уже такая связь
        existing_fks = self.get_foreign_keys()
        for fk in existing_fks:
            if (fk['column'] == column_name and 
                fk['referenced_table'] == ref_table_name and 
                fk['referenced_column'] == ref_column_name):
                from tkinter import messagebox
                messagebox.showerror("Ошибка", 
                    f"Такая связь уже существует:\n"
                    f"Столбец {column_name} уже связан с {ref_table_name}.{ref_column_name}")
                return -1
        
        ret = lib.add_foreign_key(
            self.table_ptr,
            column_name.encode('utf-8'),
            ref_table_name.encode('utf-8'),
            ref_column_name.encode('utf-8')
        )
        if ret != 0:
            from tkinter import messagebox
            messagebox.showerror("Ошибка", "Не удалось добавить внешний ключ.")
        return ret

    def remove_foreign_key(self, column_name):
        """Удалить внешний ключ"""
        ret = lib.remove_foreign_key(
            self.table_ptr,
            column_name.encode('utf-8')
        )
        if ret != 0:
            from tkinter import messagebox
            messagebox.showerror("Ошибка", "Не удалось удалить внешний ключ.")
        return ret

    def validate_foreign_keys(self):
        """Проверить целостность внешних ключей"""
        return lib.validate_foreign_keys(self.table_ptr)

    def get_foreign_keys(self):
        """Получить информацию о внешних ключах"""
        if not self.table_ptr:
            return []

        foreign_keys = []
        for i in range(self.table_ptr.contents.num_foreign_keys):
            fk = self.table_ptr.contents.foreign_keys[i].contents
            col_name = self.table_ptr.contents.columns[fk.column_index].name.decode('utf-8')
            foreign_keys.append({
                'column': col_name,
                'referenced_table': fk.referenced_table.decode('utf-8'),
                'referenced_column': fk.referenced_column.decode('utf-8')
            })
        return foreign_keys

def save_table_to_json(table, filename):
    """Сохраняет таблицу в JSON файл"""
    data = {
        "name": table.name.decode("utf-8"),
        "columns": [],
        "rows": [],
        "foreign_keys": []  # Добавляем информацию о внешних ключах
    }
    
    # Сохраняем информацию о столбцах
    for i in range(table.num_columns):
        col = table.columns[i]
        col_data = {
            "name": col.name.decode("utf-8"),
            "type": col.type,
            "is_primary_key": col.is_primary_key,
            "is_foreign_key": col.is_foreign_key
        }
        data["columns"].append(col_data)
    
    # Сохраняем информацию о внешних ключах
    for i in range(table.num_foreign_keys):
        fk = table.foreign_keys[i].contents
        fk_data = {
            "column": table.columns[fk.column_index].name.decode("utf-8"),
            "referenced_table": fk.referenced_table.decode("utf-8"),
            "referenced_column": fk.referenced_column.decode("utf-8")
        }
        data["foreign_keys"].append(fk_data)
    
    # Сохраняем данные строк
    for i in range(table.num_rows):
        row_data = []
        for j in range(table.num_columns):
            col_type = table.columns[j].type
            if col_type == TYPE_INT:
                row_data.append(table.rows[i].values[j].i)
            elif col_type == TYPE_FLOAT:
                row_data.append(table.rows[i].values[j].f)
            elif col_type == TYPE_STRING:
                row_data.append(table.rows[i].values[j].s.decode("utf-8"))
        data["rows"].append(row_data)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_table_from_json(filename):
    """Загружает таблицу из JSON файла"""
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Создаем массив столбцов
    columns = (Column * len(data["columns"]))()
    for i, col_data in enumerate(data["columns"]):
        columns[i].name = col_data["name"].encode("utf-8")
        columns[i].type = col_data["type"]
        columns[i].is_primary_key = col_data.get("is_primary_key", 0)
        columns[i].is_foreign_key = col_data.get("is_foreign_key", 0)
        columns[i].foreign_key = None  # Временно устанавливаем в None
    
    # Создаем таблицу
    table = lib.create_table(data["name"].encode("utf-8"), columns, len(columns))
    
    # Загружаем данные строк
    for row_data in data["rows"]:
        values = (DataValue * len(row_data))()
        for j, value in enumerate(row_data):
            col_type = table.columns[j].type
            if col_type == TYPE_INT:
                values[j].i = value
            elif col_type == TYPE_FLOAT:
                values[j].f = value
            elif col_type == TYPE_STRING:
                values[j].s = value.encode("utf-8")
        lib.insert_row(table, values)
    
    # Восстанавливаем внешние ключи после загрузки данных
    if "foreign_keys" in data:
        for fk_data in data["foreign_keys"]:
            ret = lib.add_foreign_key(
                table,
                fk_data["column"].encode("utf-8"),
                fk_data["referenced_table"].encode("utf-8"),
                fk_data["referenced_column"].encode("utf-8")
            )
            if ret != 0:
                print(f"Warning: Failed to restore foreign key for column {fk_data['column']}")
    
    return table

class Database:
    def __init__(self):
        """Инициализация базы данных"""
        try:
            lib.init_database()
            self.tables = {}
            self.current_transaction = None
        except Exception as e:
            print(f"Ошибка при инициализации базы данных: {e}")
            raise

    def __del__(self):
        """Очистка ресурсов при удалении объекта"""
        try:
            if self.current_transaction:
                self.rollback_transaction()
            lib.cleanup_database()
        except Exception as e:
            print(f"Ошибка при очистке базы данных: {e}")

    def create_table(self, name, columns):
        """Создание таблицы с поддержкой транзакций"""
        try:
            table = DBTable(name, columns)
            if table.table_ptr:
                self.tables[name] = table
                return table
            return None
        except Exception as e:
            print(f"Ошибка при создании таблицы {name}: {e}")
            return None

    def insert_row(self, table_name, values):
        """Вставляет новую строку в таблицу"""
        if not self.tables:
            raise Exception("База данных не инициализирована")
            
        table = self.tables.get(table_name)
        if not table:
            raise Exception(f"Таблица {table_name} не найдена")
            
        if len(values) != table.num_columns:
            raise Exception(f"Неверное количество значений. Ожидается {table.num_columns}, получено {len(values)}")
            
        try:
            # Преобразуем значения в нужные типы
            c_values = (DataValue * table.num_columns)()
            for i, value in enumerate(values):
                if value is None:
                    c_values[i].i = 0  # NULL значение
                    continue
                    
                if table.columns_info[i][1] == TYPE_INT:
                    c_values[i].i = int(value)
                elif table.columns_info[i][1] == TYPE_FLOAT:
                    c_values[i].f = float(value)
                elif table.columns_info[i][1] == TYPE_STRING:
                    if not isinstance(value, str):
                        value = str(value)
                    c_values[i].s = value.encode('utf-8')
                    
            # Проверяем внешние ключи
            for i, col in enumerate(table.columns_info):
                if col[0] in [fk['column'] for fk in table.get_foreign_keys()] and values[i] is not None:
                    fk = next(fk for fk in table.get_foreign_keys() if fk['column'] == col[0])
                    ref_table = self.tables.get(fk['referenced_table'])
                    if not ref_table:
                        raise Exception(f"Связанная таблица {fk['referenced_table']} не найдена")
                        
                    # Находим индекс столбца в связанной таблице
                    ref_col_index = -1
                    for j, ref_col in enumerate(ref_table.columns_info):
                        if ref_col[0] == fk['referenced_column']:
                            ref_col_index = j
                            break
                            
                    if ref_col_index == -1:
                        raise Exception(f"Столбец {fk['referenced_column']} не найден в таблице {fk['referenced_table']}")
                        
                    # Проверяем существование значения
                    value_exists = False
                    for row in range(ref_table.get_num_rows()):
                        ref_value = ref_table.get_value(row, ref_col_index)
                        if ref_value == values[i]:
                            value_exists = True
                            break
                            
                    if not value_exists:
                        raise Exception(f"Нарушение целостности внешнего ключа: значение {values[i]} не найдено в таблице {fk['referenced_table']}")
                        
            result = lib.insert_row(table.table_ptr, c_values)
            if result != 0:
                raise Exception(f"Ошибка при вставке строки: {result}")
                
            return table.get_num_rows() - 1
        except Exception as e:
            print(f"Ошибка при вставке строки в таблицу {table_name}: {e}")
            raise

    def update_row(self, table_name, row_index, col_index, new_value):
        """Обновление строки с поддержкой транзакций"""
        if table_name not in self.tables:
            return False
        
        table = self.tables[table_name]
        return table.update(row_index, col_index, new_value)

    def delete_row(self, table_name, row_index):
        """Удаление строки с поддержкой транзакций"""
        if table_name not in self.tables:
            return False
        
        table = self.tables[table_name]
        return table.delete(row_index)

    def add_foreign_key(self, table_name, column_name, ref_table_name, ref_column_name):
        """Добавление внешнего ключа с поддержкой транзакций"""
        if table_name not in self.tables or ref_table_name not in self.tables:
            return False
        
        table = self.tables[table_name]
        return table.add_foreign_key(column_name, ref_table_name, ref_column_name)

    def remove_foreign_key(self, table_name, column_name):
        """Удаление внешнего ключа с поддержкой транзакций"""
        if table_name not in self.tables:
            return False
        
        table = self.tables[table_name]
        return table.remove_foreign_key(column_name)

    def save_to_file(self, filename):
        """Сохраняет базу данных в JSON файл"""
        data = {
            "tables": []
        }
        
        for table_name, table in self.tables.items():
            table_data = {
                "name": table_name,
                "columns": [],
                "rows": [],
                "foreign_keys": []
            }
            
            # Сохраняем информацию о столбцах
            for col_name, col_type in table.columns_info:
                table_data["columns"].append({
                    "name": col_name,
                    "type": col_type
                })
            
            # Сохраняем данные строк
            for row in table.get_all_rows():
                table_data["rows"].append(list(row))
            
            # Сохраняем информацию о внешних ключах
            for fk in table.get_foreign_keys():
                table_data["foreign_keys"].append(fk)
            
            data["tables"].append(table_data)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_file(self, filename):
        """Загружает базу данных из JSON файла"""
        # Полная очистка C-базы и Python-словаря
        lib.cleanup_database()
        lib.init_database()

        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Очищаем текущие таблицы
        for table in self.tables.values():
            table.free()
        self.tables.clear()

        # Новый вариант: если это просто словарь с таблицами
        if isinstance(data, dict) and "tables" not in data:
            for table_name, table_data in data.items():
                columns = [(col[0], col[1]) for col in table_data["columns_info"]]
                table = self.create_table(table_name, columns)
                if table:
                    for row in table_data["rows"]:
                        table.insert(row)
        # Старый вариант: если есть ключ "tables"
        elif "tables" in data:
            for table_data in data["tables"]:
                columns = [(col["name"], col["type"]) for col in table_data["columns"]]
                table = self.create_table(table_data["name"], columns)
                if table:
                    for row in table_data["rows"]:
                        table.insert(row)
                    for fk in table_data["foreign_keys"]:
                        table.add_foreign_key(
                            fk["column"],
                            fk["referenced_table"],
                            fk["referenced_column"]
                        )

    def begin_transaction(self):
        """Начало транзакции"""
        if self.current_transaction:
            try:
                self.rollback_transaction()
            except Exception as e:
                print(f"Ошибка при откате предыдущей транзакции: {e}")
        
        transaction = lib.begin_transaction()
        if transaction:
            self.current_transaction = transaction
            return True
        return False

    def commit_transaction(self):
        """Фиксация транзакции"""
        if not self.current_transaction:
            return False
        
        try:
            result = lib.commit_transaction(self.current_transaction)
            if result:
                self.current_transaction = None
            return result
        except Exception as e:
            print(f"Ошибка при фиксации транзакции: {e}")
            return False

    def rollback_transaction(self):
        """Откат транзакции"""
        if not self.current_transaction:
            return
        
        try:
            lib.rollback_transaction(self.current_transaction)
            self.current_transaction = None
        except Exception as e:
            print(f"Ошибка при откате транзакции: {e}")
            self.current_transaction = None

    def __enter__(self):
        """Поддержка контекстного менеджера для транзакций"""
        if not self.begin_transaction():
            raise Exception("Не удалось начать транзакцию")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматическая фиксация или откат транзакции при выходе из контекста"""
        try:
            if exc_type is None:
                if not self.commit_transaction():
                    raise Exception("Не удалось зафиксировать транзакцию")
            else:
                self.rollback_transaction()
        except Exception as e:
            print(f"Ошибка при завершении транзакции: {e}")
            self.rollback_transaction()

if __name__ == "__main__":
    columns = [
        ("id", TYPE_INT),
        ("name", TYPE_STRING),
        ("salary", TYPE_FLOAT)
    ]
    table = DBTable("Employees", columns)
    table.insert([1, "Alice", 50000.0])
    table.insert([2, "Bob", 60000.0])
    print("После вставки строк:")
    table.print_table()

    table.update(0, 2, 55000.0)
    print("\nПосле обновления первой строки:")
    table.print_table()

    table.delete(1)
    print("\nПосле удаления второй строки:")
    table.print_table()

    new_columns = [
        ("id", TYPE_INT),
        ("name", TYPE_STRING),
        ("salary", TYPE_FLOAT),
        ("department", TYPE_STRING)
    ]
    table = table.transform(new_columns)
    print("\nПосле трансформации (добавлен столбец department):")
    table.print_table()

    table.add_column("age", TYPE_INT, 0)
    print("\nПосле добавления столбца age:")
    table.print_table()

    table.drop_column("salary")
    print("\nПосле удаления столбца salary:")
    table.print_table()

    table.free()
