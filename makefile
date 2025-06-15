SRCS = func.c alter_table.c
OBJS = func.o alter_table.o

ifeq ($(OS),Windows_NT)
    DLL  = mydb.dll
    CLEAN = del /Q *.o *.dll
    CFLAGS = -Wall -O2 -I. -DBUILD_DLL
    SO_TARGET =
else
    DLL  = libmydb.so
    CLEAN = rm -f *.o *.so
    CFLAGS = -Wall -O2 -I. -fPIC
    SO_TARGET = -shared
endif

all: $(DLL)

$(DLL): $(OBJS)
	$(CC) $(SO_TARGET) -o $@ $^

func.o: func.c db_core.h alter_table.h
	$(CC) $(CFLAGS) -c func.c -o func.o

alter_table.o: alter_table.c alter_table.h db_core.h
	$(CC) $(CFLAGS) -c alter_table.c -o alter_table.o

clean:
	$(CLEAN)

.PHONY: all clean