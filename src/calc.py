class Calculator:
    def add(self, a: float, b: float) -> float:
        return a + b

    def subtract(self, a: float, b: float) -> float:
        return a - b

    def multiply(self, a: float, b: float) -> float:
        return a * b

    def divide(self, a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    def power(self, base: float, exponent: float) -> float:
        return float(base ** exponent)

    def modulo(self, a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Cannot modulo by zero")
        return a % b

    def percentage(self, value: float, total: float) -> float:
        if total == 0:
            raise ValueError("Cannot calculate percentage with zero total")
        return (value / total) * 100.0
