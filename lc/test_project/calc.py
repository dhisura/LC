def add(x, y):
    """
    Add Function
    Parameters:
    x (int/float): First number
    y (int/float): Second number
    Returns:
    int/float: Sum of x and y
    """
    return x + y

def subtract(x, y):
    """
    Subtract Function
    Parameters:
    x (int/float): First number
    y (int/float): Second number
    Returns:
    int/float: Difference of x and y
    """
    return x - y

def multiply(x, y):
    """
    Multiply Function
    Parameters:
    x (int/float): First number
    y (int/float): Second number
    Returns:
    int/float: Product of x and y
    """
    return x * y

def divide(x, y):
    """
    Divide Function
    Parameters:
    x (int/float): First number
    y (int/float): Second number
    Returns:
    float: Quotient of x and y, or None if y is 0
    """
    if y == 0:
        return None
    return x / y
