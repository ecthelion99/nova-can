CC = gcc
CFLAGS = -I./c/unity -I../src/c

UNITY_SRC = c/unity/unity.c
TEST_SRC = c/test_canid.c

TARGET = test_canid

all: $(TARGET)

$(TARGET): $(UNITY_SRC) $(TEST_SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(UNITY_SRC) $(TEST_SRC)

clean:
	rm -f $(TARGET)

run: $(TARGET)
	./$(TARGET) 