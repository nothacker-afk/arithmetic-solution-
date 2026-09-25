# Arithmetic Super App

A modular arithmetic engine supporting basic, scientific, and matrix operations.

## Installation

    pip install -e .

## Usage

    from arithmetic import add, sqrt, matrix_multiply
    print(add(2, 3))
    print(sqrt(16))
    print(matrix_multiply([[1, 2]], [[3], [4]]))

## Development

    pip install -e ".[dev]"
    pytest
