CC = gcc
CFLAGS = -I./c/unity -I../src/c

UNITY_SRC = c/unity/unity.c
TEST_SRC = c/test_canid.c

TARGET = test_canid

# Python test targets
PYTHON_TESTS = python/run_tests.py

all: $(TARGET) python-tests

$(TARGET): $(UNITY_SRC) $(TEST_SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(UNITY_SRC) $(TEST_SRC)

python-tests:
	@echo "Running Python tests..."
	@python3 $(PYTHON_TESTS)

test: run python-tests

clean:
	rm -f $(TARGET)

run: $(TARGET)
	./$(TARGET)

.PHONY: all python-tests test clean run 