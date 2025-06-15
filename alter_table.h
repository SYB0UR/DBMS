#ifndef ALTER_TABLE_H
#define ALTER_TABLE_H

#include "db_core.h"  // содержит определения DataType, DataValue, Column, Row, Table



API int add_column(Table* table, const char* col_name, int new_type, DataValue default_value);
API int drop_column(Table* table, const char* col_name);

#endif // ALTER_TABLE_H
