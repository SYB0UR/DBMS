#ifndef DB_CORE_H
#define DB_CORE_H

#ifdef BUILD_DLL
#define API __declspec(dllexport)
#else
#define API __declspec(dllimport)
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define DB_INITIAL_CAPACITY 10
#define TABLE_INITIAL_CAPACITY 10
#define TRANSACTION_INITIAL_CAPACITY 100

typedef enum {
    TYPE_INT,
    TYPE_FLOAT,
    TYPE_STRING
} ColumnType;

// Структура для хранения значения ячейки
typedef union {
    int i;
    float f;
    char* s;
} DataValue;

// Структура для хранения информации о столбце
typedef struct {
    char name[50];
    ColumnType type;
    int is_primary_key;
    int is_foreign_key;
    void* foreign_key;
} Column;

// Структура для хранения информации о внешнем ключе
typedef struct {
    char referenced_table[50];
    char referenced_column[50];
    int column_index;
} ForeignKey;

// Структура для хранения строки
typedef struct {
    DataValue* values;
} Row;

// Структура для хранения таблицы
typedef struct {
    char name[50];
    Column* columns;
    int num_columns;
    Row* rows;
    int num_rows;
    int max_rows;
    ForeignKey** foreign_keys;
    int num_foreign_keys;
} Table;

// Структура для хранения глобального состояния базы данных
typedef struct {
    Table** tables;
    int num_tables;
    int max_tables;
    void* current_transaction;
} Database;

// Перечисление для типов операций транзакции
typedef enum {
    OP_INSERT,
    OP_UPDATE,
    OP_DELETE
} OperationType;

// Структура для хранения изменений в транзакции
typedef struct {
    OperationType operation;
    Table* table;
    int row_index;
    int col_index;
    DataValue old_value;
    DataValue new_value;
} TransactionOperation;

// Структура для хранения транзакции
typedef struct {
    TransactionOperation* operations;
    int num_operations;
    int max_operations;
    int is_active;
    int transaction_id;  // Уникальный идентификатор транзакции
} Transaction;

// Функции для работы с таблицами
API Table* create_table(const char* name, Column* columns, int num_columns);
API int insert_row(Table* table, DataValue* values);
API void print_table(Table* table);
API int update_row(Table* table, int row_index, int col_index, DataValue new_value);
API int delete_row(Table* table, int row_index);
API void free_table(Table* table);
API Table* transform_table(Table* table, Column* new_columns, int num_new_columns);
API int add_column(Table* table, const char* col_name, int new_type, DataValue default_value);
API int drop_column(Table* table, const char* col_name);
API int add_foreign_key(Table* table, const char* column_name, const char* ref_table_name, const char* ref_column_name);
API int remove_foreign_key(Table* table, const char* column_name);
API int validate_foreign_keys(Table* table);

// Функции для работы с базой данных
API void init_database(void);
API void cleanup_database(void);
API int add_table_to_db(Database* db, Table* table);
API Table* get_table_by_name(Database* db, const char* name);
API int check_foreign_key_constraint(Database* db, Table* table, int col_index, DataValue value);

// Функции для работы с транзакциями
API void* begin_transaction();
API int commit_transaction(void* transaction);
API void rollback_transaction(void* transaction);
API void free_transaction(Transaction* transaction);

#endif  // DB_CORE_H
