from db_interface import Database, TYPE_INT, TYPE_STRING, TYPE_FLOAT, lib
from tkinter import messagebox

def test_transactions():
    # Тест 1: Атомарность (Atomicity)
    print("\n=== Тест 1: Атомарность (Atomicity) ===")
    db = Database()
    db.create_table("Departments", [("id", TYPE_INT), ("name", TYPE_STRING)])
    db.create_table("Employees", [("id", TYPE_INT), ("name", TYPE_STRING), 
                                 ("department_id", TYPE_INT), ("salary", TYPE_FLOAT)])
    db.add_foreign_key("Employees", "department_id", "Departments", "id")
    
    try:
        db.begin_transaction()
        db.insert_row("Departments", [1, "IT"])
        db.insert_row("Employees", [1, "John", 999, 50000.0])  # Ошибка: department_id 999 не существует
        db.commit_transaction()
    except Exception as e:
        print(f"Ошибка: {e}")
        db.rollback_transaction()
        print("Все изменения откатились (атомарность)")
    
    print("\nСодержимое таблиц после отката:")
    print("Departments:", db.tables["Departments"].get_all_rows())
    print("Employees:", db.tables["Employees"].get_all_rows())
    
    # Тест 2: Согласованность (Consistency)
    print("\n=== Тест 2: Согласованность (Consistency) ===")
    try:
        db.begin_transaction()
        db.insert_row("Departments", [1, "IT"])
        db.insert_row("Employees", [1, "John", 1, 50000.0])
        db.commit_transaction()
    except Exception as e:
        print(f"Ошибка: {e}")
        db.rollback_transaction()
    
    print("\nСодержимое таблиц после отката:")
    print("Departments:", db.tables["Departments"].get_all_rows())
    print("Employees:", db.tables["Employees"].get_all_rows())
    
    # Тест 3: Изолированность (Isolation)
    print("\n=== Тест 3: Изолированность (Isolation) ===")
    try:
        # Первая транзакция
        db.begin_transaction()
        db.insert_row("Departments", [2, "HR"])
        db.insert_row("Employees", [2, "Alice", 2, 45000.0])
        db.commit_transaction()
        
        print("\nДанные после коммита первой транзакции:")
        print("Departments:", db.tables["Departments"].get_all_rows())
        print("Employees:", db.tables["Employees"].get_all_rows())
        
        # Вторая транзакция
        db.begin_transaction()
        db.update_row("Employees", 1, 3, 55000.0)  # Обновляем зарплату
        print("\nДанные во время транзакции:")
        print("Employees:", db.tables["Employees"].get_all_rows())
        raise Exception("Тестовый откат")
    except Exception as e:
        print(f"Ошибка: {e}")
        db.rollback_transaction()
    
    print("\nСодержимое таблиц после отката:")
    print("Departments:", db.tables["Departments"].get_all_rows())
    print("Employees:", db.tables["Employees"].get_all_rows())
    
    print("\n=== Тест 4: Долговечность (Durability) ===")
    # Очищаем базу данных перед тестом 4
    lib.cleanup_database()
    lib.init_database()
    
    # Создаем новую базу данных для теста долговечности
    db2 = Database()
    
    # Создаем новые таблицы с другими именами
    db2.create_table("DeptTest", [("id", TYPE_INT), ("name", TYPE_STRING)])
    db2.create_table("EmpTest", [("id", TYPE_INT), ("name", TYPE_STRING), 
                                ("department_id", TYPE_INT), ("salary", TYPE_FLOAT)])
    db2.add_foreign_key("EmpTest", "department_id", "DeptTest", "id")
    
    # Добавляем данные и коммитим
    with db2:
        db2.insert_row("DeptTest", [1, "IT"])
        db2.insert_row("EmpTest", [1, "John", 1, 50000.0])
    
    # Проверяем, что данные сохранились
    print("\nДанные после коммита:")
    print("DeptTest:", db2.tables["DeptTest"].get_all_rows())
    print("EmpTest:", db2.tables["EmpTest"].get_all_rows())
    
    # Сохраняем базу данных в файл
    db2.save_to_file("test_db.json")
    
    # Создаем новую базу данных и загружаем из файла
    new_db = Database()
    new_db.load_from_file("test_db.json")
    
    # Проверяем, что данные сохранились
    print("\nДанные после загрузки из файла:")
    print("DeptTest:", new_db.tables["DeptTest"].get_all_rows())
    print("EmpTest:", new_db.tables["EmpTest"].get_all_rows())

if __name__ == "__main__":
    test_transactions() 