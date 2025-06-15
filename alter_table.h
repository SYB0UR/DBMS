#ifndef ALTER_TABLE_H
#define ALTER_TABLE_H

#include "db_core.h"  // содержит определения DataType, DataValue, Column, Row, Table

#ifdef BUILD_DLL
#define API __declspec(dllexport)
#else
#define API __declspec(dllimport)
#endif

API int add_column(Table* table, const char* col_name, int new_type, DataValue default_value);
API int drop_column(Table* table, const char* col_name);

#endif // ALTER_TABLE_H
