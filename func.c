#ifdef BUILD_DLL
#define API __declspec(dllexport)
#else
#define API __declspec(dllimport)
#endif

#include "db_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Глобальная переменная для хранения базы данных
static Database* global_db = NULL;

// Глобальная переменная для генерации ID транзакций
static int next_transaction_id = 1;

// Глобальная переменная для текущей транзакции
static Transaction* current_transaction = NULL;

// Добавляем структуру для блокировок
typedef struct {
    int is_locked;
    int transaction_id;
} TableLock;

// Глобальная переменная для хранения блокировок
static TableLock* table_locks = NULL;
static int num_locks = 0;

// Прототип функции для добавления операции в транзакцию
static void add_operation(Transaction* t, int op_type, Table* table, 
                         int row_index, int col_index, 
                         DataValue old_value, DataValue new_value);

API Database* create_database(void) {
    Database* db = (Database*)malloc(sizeof(Database));
    if (!db) {
        fprintf(stderr, "Ошибка выделения памяти для базы данных\n");
        return NULL;
    }
    
    db->tables = (Table**)malloc(DB_INITIAL_CAPACITY * sizeof(Table*));
    if (!db->tables) {
        fprintf(stderr, "Ошибка выделения памяти для массива таблиц\n");
        free(db);
        return NULL;
    }
    
    db->num_tables = 0;
    db->max_tables = DB_INITIAL_CAPACITY;
    return db;
}

API void free_table(Table *table) {
    if (!table) return;
    
    // Освобождаем память для строк и их значений
    for (int i = 0; i < table->num_rows; i++){
         for (int j = 0; j < table->num_columns; j++){
              if (table->columns[j].type == TYPE_STRING)
                   free(table->rows[i].values[j].s);
         }
         free(table->rows[i].values);
    }
    
    // Освобождаем память для внешних ключей
    if (table->foreign_keys) {
        for (int i = 0; i < table->num_foreign_keys; i++) {
            free(table->foreign_keys[i]);
        }
        free(table->foreign_keys);
    }
    
    free(table->rows);
    free(table->columns);
    free(table);
}

API void free_database(Database* db) {
    if (!db) return;
    
    for (int i = 0; i < db->num_tables; i++) {
        free_table(db->tables[i]);
    }
    free(db->tables);
    free(db);
}

API int add_table_to_db(Database* db, Table* table) {
    if (!table) return -1;
    
    // Используем глобальную базу данных, если не указана конкретная
    if (!db) {
        if (!global_db) {
            init_database();
            if (!global_db) {
                fprintf(stderr, "Error creating global database\n");
                return -1;
            }
        }
        db = global_db;
    }
    
    // Проверяем, не существует ли уже таблица с таким именем
    for (int i = 0; i < db->num_tables; i++) {
        if (strcmp(db->tables[i]->name, table->name) == 0) {
            fprintf(stderr, "Table with name %s already exists\n", table->name);
            return -1;
        }
    }
    
    // Увеличиваем размер массива при необходимости
    if (db->num_tables >= db->max_tables) {
        int new_max = db->max_tables * 2;
        Table** temp = (Table**)realloc(db->tables, new_max * sizeof(Table*));
        if (!temp) {
            fprintf(stderr, "Error reallocating memory for tables array\n");
            return -1;
        }
        db->tables = temp;
        db->max_tables = new_max;
    }
    
    db->tables[db->num_tables++] = table;
    return 0;
}

API Table* get_table_by_name(Database* db, const char* name) {
    if (!db || !name) return NULL;
    
    for (int i = 0; i < db->num_tables; i++) {
        if (strcmp(db->tables[i]->name, name) == 0) {
            return db->tables[i];
        }
    }
    return NULL;
}

API int check_foreign_key_constraint(Database* db, Table* table, int col_index, DataValue value) {
    if (!table || col_index < 0 || col_index >= table->num_columns) {
        return 0;
    }
    
    if (!table->columns[col_index].is_foreign_key || !table->columns[col_index].foreign_key) {
        return 1;
    }
    
    // Используем глобальную базу данных, если не указана конкретная
    if (!db) {
        if (!global_db) {
            fprintf(stderr, "База данных не инициализирована\n");
            return 0;
        }
        db = global_db;
    }
    
    ForeignKey* fk = table->columns[col_index].foreign_key;
    Table* ref_table = NULL;
    
    // Ищем связанную таблицу
    for (int i = 0; i < db->num_tables; i++) {
        if (strcmp(db->tables[i]->name, fk->referenced_table) == 0) {
            ref_table = db->tables[i];
            break;
        }
    }
    
    if (!ref_table) {
        fprintf(stderr, "Связанная таблица %s не найдена\n", fk->referenced_table);
        return 0;
    }
    
    // Находим индекс столбца в связанной таблице
    int ref_col_index = -1;
    for (int i = 0; i < ref_table->num_columns; i++) {
        if (strcmp(ref_table->columns[i].name, fk->referenced_column) == 0) {
            ref_col_index = i;
            break;
        }
    }
    
    if (ref_col_index == -1) {
        fprintf(stderr, "Столбец %s не найден в таблице %s\n", 
                fk->referenced_column, fk->referenced_table);
        return 0;
    }
    
    // Проверяем существование значения в связанной таблице
    for (int i = 0; i < ref_table->num_rows; i++) {
        DataValue ref_value = ref_table->rows[i].values[ref_col_index];
        if (table->columns[col_index].type == TYPE_INT && 
            ref_table->columns[ref_col_index].type == TYPE_INT) {
            if (value.i == ref_value.i) return 1;
        }
        else if (table->columns[col_index].type == TYPE_FLOAT && 
                 ref_table->columns[ref_col_index].type == TYPE_FLOAT) {
            if (value.f == ref_value.f) return 1;
        }
        else if (table->columns[col_index].type == TYPE_STRING && 
                 ref_table->columns[ref_col_index].type == TYPE_STRING) {
            if (value.s && ref_value.s && strcmp(value.s, ref_value.s) == 0) return 1;
        }
    }
    
    fprintf(stderr, "Нарушение целостности внешнего ключа: значение не найдено в таблице %s\n", 
            fk->referenced_table);
    return 0;
}

// Обновляем функцию check_foreign_key_value
static int check_foreign_key_value(Table* table, int col_index, DataValue value) {
    if (!global_db) {
        fprintf(stderr, "Database not initialized\n");
        return 0;
    }

    // Получаем информацию о внешнем ключе
    ForeignKey* fk = (ForeignKey*)table->columns[col_index].foreign_key;
    if (!fk) {
        fprintf(stderr, "No foreign key constraint found\n");
        return 0;
    }

    // Находим связанную таблицу
    Table* ref_table = NULL;
    for (int i = 0; i < global_db->num_tables; i++) {
        if (strcmp(global_db->tables[i]->name, fk->referenced_table) == 0) {
            ref_table = global_db->tables[i];
            break;
        }
    }

    if (!ref_table) {
        fprintf(stderr, "Referenced table not found\n");
        return 0;
    }

    // Находим индекс столбца в связанной таблице
    int ref_col_index = -1;
    for (int i = 0; i < ref_table->num_columns; i++) {
        if (strcmp(ref_table->columns[i].name, fk->referenced_column) == 0) {
            ref_col_index = i;
            break;
        }
    }

    if (ref_col_index == -1) {
        fprintf(stderr, "Referenced column not found\n");
        return 0;
    }

    // Проверяем существование значения в связанной таблице
    for (int i = 0; i < ref_table->num_rows; i++) {
        if (table->columns[col_index].type == TYPE_INT && 
            ref_table->columns[ref_col_index].type == TYPE_INT) {
            if (value.i == ref_table->rows[i].values[ref_col_index].i) {
                return 1;
            }
        }
    }

    fprintf(stderr, "Error: foreign key value %d not found in referenced table\n", value.i);
    return 0;
}

// Инициализация базы данных при запуске
API void init_database(void) {
    if (global_db == NULL) {
        global_db = (Database*)malloc(sizeof(Database));
        if (!global_db) {
            fprintf(stderr, "Ошибка выделения памяти для базы данных\n");
            return;
        }
        
        global_db->tables = (Table**)malloc(DB_INITIAL_CAPACITY * sizeof(Table*));
        if (!global_db->tables) {
            free(global_db);
            global_db = NULL;
            fprintf(stderr, "Ошибка выделения памяти для массива таблиц\n");
            return;
        }
        
        global_db->num_tables = 0;
        global_db->max_tables = DB_INITIAL_CAPACITY;
        global_db->current_transaction = NULL;
        
        // Инициализируем массив таблиц
        for (int i = 0; i < DB_INITIAL_CAPACITY; i++) {
            global_db->tables[i] = NULL;
        }
    }
}

// Очистка базы данных при завершении
API void cleanup_database(void) {
    if (!global_db) return;
    
    // Откатываем активную транзакцию, если она есть
    if (global_db->current_transaction) {
        rollback_transaction(global_db->current_transaction);
    }
    
    // Освобождаем память таблиц
    for (int i = 0; i < global_db->num_tables; i++) {
        if (global_db->tables[i]) {
            free_table(global_db->tables[i]);
            global_db->tables[i] = NULL;
        }
    }
    
    // Освобождаем память базы данных
    free(global_db->tables);
    free(global_db);
    global_db = NULL;
}

API Table* create_table(const char* name, Column* columns, int num_columns) {
    if (!name || !columns || num_columns <= 0) {
        fprintf(stderr, "Неверные параметры для create_table\n");
        return NULL;
    }
    
    Table* table = (Table*)malloc(sizeof(Table));
    if (!table) {
        fprintf(stderr, "Ошибка выделения памяти для таблицы\n");
        return NULL;
    }
    
    // Инициализируем структуру таблицы
    memset(table, 0, sizeof(Table));
    
    // Копируем имя таблицы
    strncpy(table->name, name, sizeof(table->name) - 1);
    table->name[sizeof(table->name) - 1] = '\0';
    
    // Выделяем память для столбцов
    table->num_columns = num_columns;
    table->columns = (Column*)malloc(num_columns * sizeof(Column));
    if (!table->columns) {
        fprintf(stderr, "Ошибка выделения памяти для столбцов\n");
        free(table);
        return NULL;
    }
    
    // Копируем информацию о столбцах
    for (int i = 0; i < num_columns; i++) {
        memset(&table->columns[i], 0, sizeof(Column));
        strncpy(table->columns[i].name, columns[i].name, sizeof(table->columns[i].name) - 1);
        table->columns[i].name[sizeof(table->columns[i].name) - 1] = '\0';
        table->columns[i].type = columns[i].type;
        table->columns[i].is_primary_key = 0;
        table->columns[i].is_foreign_key = 0;
        table->columns[i].foreign_key = NULL;
    }
    
    // Инициализируем массив строк
    table->num_rows = 0;
    table->max_rows = TABLE_INITIAL_CAPACITY;
    table->rows = (Row*)malloc(table->max_rows * sizeof(Row));
    if (!table->rows) {
        fprintf(stderr, "Ошибка выделения памяти для строк\n");
        free(table->columns);
        free(table);
        return NULL;
    }
    
    // Инициализируем массив строк
    for (int i = 0; i < table->max_rows; i++) {
        table->rows[i].values = NULL;
    }
    
    // Инициализируем внешние ключи
    table->foreign_keys = NULL;
    table->num_foreign_keys = 0;
    
    return table;
}

// Функция для получения блокировки таблицы
static int lock_table(Table* table, int transaction_id) {
    if (!table) return 0;
    
    // Ищем блокировку для таблицы
    for (int i = 0; i < num_locks; i++) {
        if (table_locks[i].is_locked && table_locks[i].transaction_id != transaction_id) {
            return 0; // Таблица уже заблокирована другой транзакцией
        }
    }
    
    // Создаем новую блокировку
    TableLock* new_locks = realloc(table_locks, (num_locks + 1) * sizeof(TableLock));
    if (!new_locks) return 0;
    
    table_locks = new_locks;
    table_locks[num_locks].is_locked = 1;
    table_locks[num_locks].transaction_id = transaction_id;
    num_locks++;
    
    return 1;
}

// Функция для освобождения блокировки
static void unlock_table(Table* table, int transaction_id) {
    if (!table) return;
    
    for (int i = 0; i < num_locks; i++) {
        if (table_locks[i].transaction_id == transaction_id) {
            table_locks[i].is_locked = 0;
            break;
        }
    }
}

API void* begin_transaction() {
    if (!global_db) {
        fprintf(stderr, "Database not initialized\n");
        return NULL;
    }

    if (current_transaction) {
        fprintf(stderr, "Transaction already active\n");
        return NULL;
    }

    // Создаем новую транзакцию
    current_transaction = (Transaction*)malloc(sizeof(Transaction));
    if (!current_transaction) {
        fprintf(stderr, "Error allocating memory for transaction\n");
        return NULL;
    }

    current_transaction->operations = (TransactionOperation*)malloc(
        TRANSACTION_INITIAL_CAPACITY * sizeof(TransactionOperation));
    if (!current_transaction->operations) {
        free(current_transaction);
        current_transaction = NULL;
        fprintf(stderr, "Error allocating memory for transaction operations\n");
        return NULL;
    }

    current_transaction->num_operations = 0;
    current_transaction->max_operations = TRANSACTION_INITIAL_CAPACITY;
    current_transaction->is_active = 1;
    current_transaction->transaction_id = next_transaction_id++;  // Устанавливаем уникальный ID

    return current_transaction;
}

// Функция для добавления операции в транзакцию
static void add_operation(Transaction* t, int op_type, Table* table, 
                         int row_index, int col_index, 
                         DataValue old_value, DataValue new_value) {
    if (!t || !t->is_active) return;

    // Увеличиваем размер массива при необходимости
    if (t->num_operations >= t->max_operations) {
        int new_max = t->max_operations * 2;
        TransactionOperation* temp = (TransactionOperation*)realloc(
            t->operations, new_max * sizeof(TransactionOperation));
        if (!temp) {
            fprintf(stderr, "Ошибка перераспределения памяти для операций\n");
            return;
        }
        t->operations = temp;
        t->max_operations = new_max;
    }

    // Добавляем операцию
    t->operations[t->num_operations].operation = op_type;
    t->operations[t->num_operations].table = table;
    t->operations[t->num_operations].row_index = row_index;
    t->operations[t->num_operations].col_index = col_index;
    t->operations[t->num_operations].old_value = old_value;
    t->operations[t->num_operations].new_value = new_value;
    t->num_operations++;
}

API void rollback_transaction(void* transaction) {
    if (!transaction || !current_transaction) return;

    // Отменяем операции в обратном порядке
    for (int i = current_transaction->num_operations - 1; i >= 0; i--) {
        TransactionOperation* op = &current_transaction->operations[i];
        switch (op->operation) {
            case OP_INSERT:
                // Удаляем вставленную строку
                delete_row(op->table, op->row_index);
                break;
            case OP_UPDATE:
                // Восстанавливаем старое значение
                update_row(op->table, op->row_index, op->col_index, op->old_value);
                break;
            case OP_DELETE:
                // Восстанавливаем удаленную строку
                insert_row(op->table, op->table->rows[op->row_index].values);
                break;
        }
    }

    // Освобождаем все блокировки транзакции
    for (int i = 0; i < num_locks; i++) {
        if (table_locks[i].transaction_id == current_transaction->transaction_id) {
            table_locks[i].is_locked = 0;
        }
    }

    // Освобождаем память транзакции
    free(current_transaction->operations);
    free(current_transaction);
    current_transaction = NULL;
}

API int commit_transaction(void* transaction) {
    if (!transaction || !current_transaction) return 0;

    // Проверяем целостность данных
    for (int i = 0; i < current_transaction->num_operations; i++) {
        TransactionOperation* op = &current_transaction->operations[i];
        if (op->operation == OP_INSERT || op->operation == OP_UPDATE) {
            for (int j = 0; j < op->table->num_columns; j++) {
                if (op->table->columns[j].is_foreign_key) {
                    DataValue value = op->table->rows[op->row_index].values[j];
                    if (!check_foreign_key_value(op->table, j, value)) {
                        rollback_transaction(transaction);
                        return 0;
                    }
                }
            }
        }
    }

    // Снимаем все блокировки, связанные с этой транзакцией
    for (int i = 0; i < num_locks; i++) {
        if (table_locks[i].transaction_id == current_transaction->transaction_id) {
            table_locks[i].is_locked = 0;
        }
    }

    // Освобождаем память транзакции
    free(current_transaction->operations);
    free(current_transaction);
    current_transaction = NULL;
    return 1;
}

void set_value(Table* table, int row_idx, int col_idx, DataValue value) {
    if (!table || !table->rows || row_idx < 0 || row_idx >= table->num_rows ||
        col_idx < 0 || col_idx >= table->num_columns) {
        return;
    }

    Row* row = &table->rows[row_idx];
    if (!row->values) {
        row->values = (DataValue*)calloc(table->num_columns, sizeof(DataValue));
        if (!row->values) {
            return;
        }
    }

    // Очищаем предыдущее значение
    if (row->values[col_idx].s) {
        free(row->values[col_idx].s);
        row->values[col_idx].s = NULL;
    }

    // Копируем новое значение
    if (table->columns[col_idx].type == TYPE_STRING && value.s) {
        size_t len = strlen(value.s);
        row->values[col_idx].s = (char*)malloc(len + 1);
        if (row->values[col_idx].s) {
            strncpy(row->values[col_idx].s, value.s, len);
            row->values[col_idx].s[len] = '\0';
        }
    } else {
        row->values[col_idx] = value;
    }
}

API int insert_row(Table* table, DataValue* values) {
    if (!table || !values) {
        fprintf(stderr, "Invalid parameters for insert_row\n");
        return -1;
    }

    // Получаем блокировку таблицы
    if (current_transaction && !lock_table(table, current_transaction->transaction_id)) {
        fprintf(stderr, "Error: table is locked by another transaction\n");
        return -1;
    }

    // Проверяем внешние ключи
    for (int i = 0; i < table->num_columns; i++) {
        if (table->columns[i].is_foreign_key) {
            if (!check_foreign_key_value(table, i, values[i])) {
                if (current_transaction) unlock_table(table, current_transaction->transaction_id);
                return -1;
            }
        }
    }

    // Проверяем уникальность первичного ключа
    for (int i = 0; i < table->num_columns; i++) {
        if (table->columns[i].is_primary_key) {
            for (int j = 0; j < table->num_rows; j++) {
                int is_duplicate = 0;
                if (table->columns[i].type == TYPE_INT) {
                    if (table->rows[j].values[i].i == values[i].i) {
                        is_duplicate = 1;
                    }
                } else if (table->columns[i].type == TYPE_FLOAT) {
                    if (table->rows[j].values[i].f == values[i].f) {
                        is_duplicate = 1;
                    }
                } else if (table->columns[i].type == TYPE_STRING) {
                    if (values[i].s && table->rows[j].values[i].s && strcmp(table->rows[j].values[i].s, values[i].s) == 0) {
                        is_duplicate = 1;
                    }
                }
                if (is_duplicate) {
                    if (current_transaction) unlock_table(table, current_transaction->transaction_id);
                    fprintf(stderr, "Error: primary key violation for column %s\n", table->columns[i].name);
                    return -1;
                }
            }
        }
    }

    // Выполняем вставку
    if (table->num_rows >= table->max_rows) {
        int new_max = table->max_rows * 2;
        Row* temp = realloc(table->rows, new_max * sizeof(Row));
        if (!temp) {
            if (current_transaction) unlock_table(table, current_transaction->transaction_id);
            fprintf(stderr, "Failed to reallocate memory for rows\n");
            return -1;
        }
        table->rows = temp;
        table->max_rows = new_max;
    }

    Row new_row;
    new_row.values = (DataValue*)calloc(table->num_columns, sizeof(DataValue));
    if (!new_row.values) {
        if (current_transaction) unlock_table(table, current_transaction->transaction_id);
        fprintf(stderr, "Error allocating memory for new row\n");
        return -1;
    }

    // Копируем значения
    for (int i = 0; i < table->num_columns; i++) {
        if (table->columns[i].type == TYPE_STRING && values[i].s) {
            size_t len = strlen(values[i].s);
            new_row.values[i].s = (char*)malloc(len + 1);
            if (new_row.values[i].s) {
                strncpy(new_row.values[i].s, values[i].s, len);
                new_row.values[i].s[len] = '\0';
            }
        } else {
            new_row.values[i] = values[i];
        }
    }

    // Добавляем строку
    table->rows[table->num_rows] = new_row;
    int row_index = table->num_rows;
    table->num_rows++;

    // Если есть активная транзакция, добавляем операцию
    if (current_transaction && current_transaction->is_active) {
        DataValue empty_value = {0};
        add_operation(current_transaction, OP_INSERT, table, row_index, -1, 
                     empty_value, empty_value);
    }

    // Освобождаем блокировку
    if (current_transaction) unlock_table(table, current_transaction->transaction_id);
    return 0;
}

API int update_row(Table* table, int row_index, int col_index, DataValue new_value) {
    if (!table || row_index < 0 || row_index >= table->num_rows || 
        col_index < 0 || col_index >= table->num_columns) {
        return -1;
    }

    // Проверяем внешний ключ
    if (table->columns[col_index].is_foreign_key) {
        if (!check_foreign_key_value(table, col_index, new_value)) {
            fprintf(stderr, "Error: foreign key constraint violation for column %s\n", 
                    table->columns[col_index].name);
            return -1;
        }
    }

    // Проверяем уникальность первичного ключа
    if (table->columns[col_index].is_primary_key) {
        for (int i = 0; i < table->num_rows; i++) {
            if (i != row_index && table->columns[col_index].type == TYPE_INT && 
                table->rows[i].values[col_index].i == new_value.i) {
                fprintf(stderr, "Error: primary key violation for column %s\n", 
                        table->columns[col_index].name);
                return -1;
            }
        }
    }

    // Сохраняем старое значение
    DataValue old_value = table->rows[row_index].values[col_index];

    // Обновляем значение
    if (table->columns[col_index].type == TYPE_STRING) {
        if (table->rows[row_index].values[col_index].s) {
            free(table->rows[row_index].values[col_index].s);
        }
        if (new_value.s) {
            size_t len = strlen(new_value.s);
            table->rows[row_index].values[col_index].s = (char*)malloc(len + 1);
            if (table->rows[row_index].values[col_index].s) {
                strncpy(table->rows[row_index].values[col_index].s, new_value.s, len);
                table->rows[row_index].values[col_index].s[len] = '\0';
            }
        } else {
            table->rows[row_index].values[col_index].s = NULL;
        }
    } else {
        table->rows[row_index].values[col_index] = new_value;
    }

    // Если есть активная транзакция, добавляем операцию
    if (current_transaction && current_transaction->is_active) {
        add_operation(current_transaction, OP_UPDATE, table, row_index, col_index, 
                     old_value, new_value);
    }

    return 0;
}

API int delete_row(Table* table, int row_index) {
    if (!table || row_index < 0 || row_index >= table->num_rows) {
        return -1;
    }

    // Если есть активная транзакция, сохраняем данные строки
    if (current_transaction && current_transaction->is_active) {
        DataValue empty_value = {0};
        add_operation(current_transaction, OP_DELETE, table, row_index, -1, 
                     empty_value, empty_value);
    }

    // Освобождаем память строки
    for (int i = 0; i < table->num_columns; i++) {
        if (table->columns[i].type == TYPE_STRING && 
            table->rows[row_index].values[i].s) {
            free(table->rows[row_index].values[i].s);
        }
    }
    free(table->rows[row_index].values);

    // Сдвигаем оставшиеся строки
    for (int i = row_index; i < table->num_rows - 1; i++) {
        table->rows[i] = table->rows[i + 1];
    }

    table->num_rows--;
    return 0;
}

API void print_table(Table *table) {
    if (!table) return;
    printf("Таблица: %s\n", table->name);
    for (int i = 0; i < table->num_columns; i++){
         printf("%-15s", table->columns[i].name);
    }
    printf("\n");
    for (int i = 0; i < table->num_columns; i++){
         printf("---------------");
    }
    printf("\n");
    for (int i = 0; i < table->num_rows; i++){
         for (int j = 0; j < table->num_columns; j++){
              int col_type = table->columns[j].type;
              if (col_type == TYPE_INT)
                  printf("%-15d", table->rows[i].values[j].i);
              else if (col_type == TYPE_FLOAT)
                  printf("%-15f", table->rows[i].values[j].f);
              else if (col_type == TYPE_STRING)
                  printf("%-15s", table->rows[i].values[j].s);
         }
         printf("\n");
    }
}

/*
 * Функция transform_table
 *
 * Параметры:
 *   old_table       - указатель на старую таблицу
 *   new_columns     - массив новых описаний столбцов
 *   new_num_columns - новое число столбцов
 *
 * Создаёт новую таблицу по схеме new_columns:
 *   — Если в старой таблице найден столбец с таким же именем и совпадающим типом,
 *     копируется его значение.
 *   — Иначе устанавливается значение по умолчанию (0, 0.0 или пустая строка).
 */
API Table* transform_table(Table* old_table, Column* new_columns, int new_num_columns) {
    Table* new_table = create_table(old_table->name, new_columns, new_num_columns);
    if (!new_table) {
         fprintf(stderr, "Ошибка создания новой таблицы\n");
         return NULL;
    }
    for (int i = 0; i < old_table->num_rows; i++) {
         DataValue* new_values = (DataValue*)malloc(new_num_columns * sizeof(DataValue));
         if (!new_values) {
             fprintf(stderr, "Ошибка выделения памяти для новой строки\n");
             continue;
         }
         for (int j = 0; j < new_num_columns; j++) {
             int found = 0;
             for (int k = 0; k < old_table->num_columns; k++) {
                 if (strcmp(old_table->columns[k].name, new_columns[j].name) == 0) {
                     found = 1;
                     if (old_table->columns[k].type == new_columns[j].type) {
                         if (new_columns[j].type == TYPE_STRING) {
                              new_values[j].s = strdup(old_table->rows[i].values[k].s);
                         } else {
                              new_values[j] = old_table->rows[i].values[k];
                         }
                     } else {
                         if (new_columns[j].type == TYPE_INT) {
                              new_values[j].i = 0;
                         } else if (new_columns[j].type == TYPE_FLOAT) {
                              new_values[j].f = 0.0f;
                         } else if (new_columns[j].type == TYPE_STRING) {
                              new_values[j].s = strdup("");
                         }
                     }
                     break;
                 }
             }
             if (!found) {
                 if (new_columns[j].type == TYPE_INT) {
                      new_values[j].i = 0;
                 } else if (new_columns[j].type == TYPE_FLOAT) {
                      new_values[j].f = 0.0f;
                 } else if (new_columns[j].type == TYPE_STRING) {
                      new_values[j].s = strdup("");
                 }
             }
         }
         if (insert_row(new_table, new_values) != 0) {
             fprintf(stderr, "Ошибка вставки строки при трансформации\n");
         }
         free(new_values);
    }
    return new_table;
}

API int add_foreign_key(Table* table, const char* column_name, 
                       const char* ref_table_name, const char* ref_column_name) {
    if (!table || !column_name || !ref_table_name || !ref_column_name) {
        return -1;
    }

    // Находим индекс столбца
    int col_index = -1;
    for (int i = 0; i < table->num_columns; i++) {
        if (strcmp(table->columns[i].name, column_name) == 0) {
            col_index = i;
            break;
        }
    }

    if (col_index == -1) {
        fprintf(stderr, "Столбец '%s' не найден\n", column_name);
        return -1;
    }

    // Создаем новый внешний ключ
    ForeignKey* new_fk = (ForeignKey*)malloc(sizeof(ForeignKey));
    if (!new_fk) {
        fprintf(stderr, "Ошибка выделения памяти для внешнего ключа\n");
        return -1;
    }

    strncpy(new_fk->referenced_table, ref_table_name, sizeof(new_fk->referenced_table) - 1);
    strncpy(new_fk->referenced_column, ref_column_name, sizeof(new_fk->referenced_column) - 1);
    new_fk->column_index = col_index;

    // Увеличиваем массив внешних ключей
    ForeignKey** new_fks = (ForeignKey**)realloc(table->foreign_keys, 
                                               (table->num_foreign_keys + 1) * sizeof(ForeignKey*));
    if (!new_fks) {
        fprintf(stderr, "Ошибка выделения памяти для массива внешних ключей\n");
        free(new_fk);
        return -1;
    }

    table->foreign_keys = new_fks;
    table->foreign_keys[table->num_foreign_keys] = new_fk;
    table->num_foreign_keys++;

    // Обновляем информацию о столбце
    table->columns[col_index].is_foreign_key = 1;
    table->columns[col_index].foreign_key = new_fk;

    return 0;
}

API int remove_foreign_key(Table* table, const char* column_name) {
    if (!table || !column_name) {
        return -1;
    }

    // Находим индекс внешнего ключа
    int fk_index = -1;
    for (int i = 0; i < table->num_foreign_keys; i++) {
        if (strcmp(table->columns[table->foreign_keys[i]->column_index].name, column_name) == 0) {
            fk_index = i;
            break;
        }
    }

    if (fk_index == -1) {
        fprintf(stderr, "Внешний ключ для столбца '%s' не найден\n", column_name);
        return -1;
    }

    // Обновляем информацию о столбце
    int col_index = table->foreign_keys[fk_index]->column_index;
    table->columns[col_index].is_foreign_key = 0;
    table->columns[col_index].foreign_key = NULL;

    // Удаляем внешний ключ из массива
    free(table->foreign_keys[fk_index]);
    for (int i = fk_index; i < table->num_foreign_keys - 1; i++) {
        table->foreign_keys[i] = table->foreign_keys[i + 1];
    }
    table->num_foreign_keys--;

    // Уменьшаем размер массива
    if (table->num_foreign_keys > 0) {
        ForeignKey** new_fks = (ForeignKey**)realloc(table->foreign_keys, 
                                                   table->num_foreign_keys * sizeof(ForeignKey*));
        if (new_fks) {
            table->foreign_keys = new_fks;
        }
    } else {
        free(table->foreign_keys);
        table->foreign_keys = NULL;
    }

    return 0;
}

API int validate_foreign_keys(Table* table) {
    if (!table) {
        return -1;
    }

    for (int i = 0; i < table->num_foreign_keys; i++) {
        ForeignKey* fk = table->foreign_keys[i];
        int col_index = fk->column_index;

        // Проверяем каждое значение в столбце
        for (int j = 0; j < table->num_rows; j++) {
            DataValue value = table->rows[j].values[col_index];
            // Здесь должна быть проверка существования значения в referenced_table
            // Для этого нужен доступ к другим таблицам, что требует дополнительной инфраструктуры
        }
    }

    return 0;
}

API int get_referenced_tables(Table* table, char** table_names, int* num_tables) {
    if (!table || !table_names || !num_tables) {
        return -1;
    }

    *num_tables = 0;
    for (int i = 0; i < table->num_foreign_keys; i++) {
        const char* ref_table = table->foreign_keys[i]->referenced_table;
        
        // Проверяем, не добавлена ли уже эта таблица
        int is_duplicate = 0;
        for (int j = 0; j < *num_tables; j++) {
            if (strcmp(table_names[j], ref_table) == 0) {
                is_duplicate = 1;
                break;
            }
        }

        if (!is_duplicate) {
            table_names[*num_tables] = strdup(ref_table);
            if (!table_names[*num_tables]) {
                // Освобождаем память в случае ошибки
                for (int j = 0; j < *num_tables; j++) {
                    free(table_names[j]);
                }
                return -1;
            }
            (*num_tables)++;
        }
    }

    return 0;
}
