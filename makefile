SRCS = func.c alter_table.c
OBJS = func.o alter_table.o
DLL  = mydb.dll
CC = gcc
CFLAGS = -Wall -O2 -I. -DBUILD_DLL

all: $(DLL)

$(DLL): $(OBJS)
		$(CC) -shared -o $@ $^

func.o: func.c db_core.h alter_table.h
		$(CC) $(CFLAGS) -c func.c -o func.o

alter_table.o: alter_table.c alter_table.h db_core.h
		$(CC) $(CFLAGS) -c alter_table.c -o alter_table.o

clean:
		del /Q *.o *.dll

.PHONY: all clean