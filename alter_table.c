#include "alter_table.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

API int add_column(Table* table, const char* col_name, int new_type, DataValue default_value) {
    if (!table || !col_name) return -1;

    int old_cols = table->num_columns;
    int new_cols = old_cols + 1;
    
    // Выделяем новый массив столбцов
    Column* new_columns = (Column*)malloc(new_cols * sizeof(Column));
    if (!new_columns) {
         fprintf(stderr, "add_column: Ошибка выделения памяти для нового массива столбцов\n");
         return -1;
    }
    
    // Копируем старые столбцы
    for (int i = 0; i < old_cols; i++){
         new_columns[i] = table->columns[i];
    }
    
    // Добавляем новый столбец в конец
    memset(new_columns[old_cols].name, 0, sizeof(new_columns[old_cols].name));
    strncpy(new_columns[old_cols].name, col_name, sizeof(new_columns[old_cols].name)-1);
    new_columns[old_cols].type = new_type;
    
    // Обновляем таблицу
    free(table->columns);
    table->columns = new_columns;
    table->num_columns = new_cols;
    
    // Перераспределяем массив значений для каждой строки
    for (int i = 0; i < table->num_rows; i++) {
         DataValue* old_values = table->rows[i].values;
         DataValue* new_values = (DataValue*)malloc(new_cols * sizeof(DataValue));
         if (!new_values) {
              fprintf(stderr, "add_column: Ошибка выделения памяти для значений строки %d\n", i);
              return -1;
         }
         // Копируем старые значения
         for (int j = 0; j < old_cols; j++){
              new_values[j] = old_values[j];
         }
         // Устанавливаем значение по умолчанию для нового столбца
         if (new_type == TYPE_STRING) {
              new_values[old_cols].s = strdup(default_value.s);
         } else {
              new_values[old_cols] = default_value;
         }
         
         free(old_values);
         table->rows[i].values = new_values;
    }
    return 0;
}

API int drop_column(Table* table, const char* col_name) {
    if (!table || !col_name) return -1;
    
    int old_cols = table->num_columns;
    int idx = -1;
    // Находим индекс столбца, который необходимо удалить
    for (int i = 0; i < old_cols; i++){
         if (strcmp(table->columns[i].name, col_name) == 0) {
              idx = i;
              break;
         }
    }
    if (idx < 0) {
         fprintf(stderr, "drop_column: Столбец '%s' не найден\n", col_name);
         return -1;
    }
    
    // Сохраняем тип удаляемого столбца
    int drop_type = table->columns[idx].type;
    
    int new_cols = old_cols - 1;
    Column* new_columns = (Column*)malloc(new_cols * sizeof(Column));
    if (!new_columns) {
         fprintf(stderr, "drop_column: Ошибка выделения памяти для нового массива столбцов\n");
         return -1;
    }
    // Копируем все столбцы, кроме удаляемого
    for (int i = 0, j = 0; i < old_cols; i++){
         if (i == idx) continue;
         new_columns[j++] = table->columns[i];
    }
    free(table->columns);
    table->columns = new_columns;
    table->num_columns = new_cols;
    
    // Перераспределяем массив значений для каждой строки
    for (int i = 0; i < table->num_rows; i++){
         DataValue* old_values = table->rows[i].values;
         DataValue* new_values = (DataValue*)malloc(new_cols * sizeof(DataValue));
         if (!new_values) {
              fprintf(stderr, "drop_column: Ошибка выделения памяти для значений строки %d\n", i);
              return -1;
         }
         for (int j = 0, k = 0; j < old_cols; j++){
              if (j == idx) {
                   // Освобождаем память для строкового значения, если применимо
                   if (drop_type == TYPE_STRING && old_values[j].s != NULL) {
                         free(old_values[j].s);
                   }
                   continue;
              }
              new_values[k++] = old_values[j];
         }
         free(old_values);
         table->rows[i].values = new_values;
    }
    
    return 0;
}
