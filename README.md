# Arithmetic Super App

A modular arithmetic engine supporting basic, scientific, and matrix operations.

## Installation

    pip install -e .

## Usage

    from arithmetic import add, sqrt, matrix_multiply

    print(add(2, 3))                             # 5
    print(sqrt(16))                              # 4.0
    print(matrix_multiply([[1, 2]], [[3], [4]]))  # [[11]]

## Development

    pip install -e ".[dev]"
    pytest

## Project Structure

- `arithmetic/basic.py`       -- basic operations
- `arithmetic/scientific.py`  -- scientific operations
- `arithmetic/matrix.py`      -- matrix operations
- `tests/`                    -- pytest test suite
