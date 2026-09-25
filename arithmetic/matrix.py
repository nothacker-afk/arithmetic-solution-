"""Matrix operations using pure Python."""

def _validate(matrix, name="matrix"):
    if not matrix or not isinstance(matrix, list):
        raise ValueError(f"{name} must be a non-empty list of lists")
    width = len(matrix[0])
    if width == 0:
        raise ValueError(f"{name} rows cannot be empty")
    for row in matrix:
        if len(row) != width:
            raise ValueError(f"{name} must be rectangular")

def matrix_add(a, b):
    """Add two matrices of the same dimensions."""
    _validate(a, "a"); _validate(b, "b")
    if len(a) != len(b) or len(a[0]) != len(b[0]):
        raise ValueError("Matrices must have the same dimensions")
    return [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]

def matrix_subtract(a, b):
    """Subtract matrix b from matrix a."""
    _validate(a, "a"); _validate(b, "b")
    if len(a) != len(b) or len(a[0]) != len(b[0]):
        raise ValueError("Matrices must have the same dimensions")
    return [[a[i][j] - b[i][j] for j in range(len(a[0]))] for i in range(len(a))]

def matrix_multiply(a, b):
    """Multiply matrix a by matrix b."""
    _validate(a, "a"); _validate(b, "b")
    if len(a[0]) != len(b):
        raise ValueError("Columns of a must equal rows of b")
    result = []
    for i in range(len(a)):
        row = []
        for j in range(len(b[0])):
            row.append(sum(a[i][k] * b[k][j] for k in range(len(b))))
        result.append(row)
    return result

def matrix_transpose(a):
    """Return the transpose of matrix a."""
    _validate(a, "a")
    return [list(row) for row in zip(*a)]
