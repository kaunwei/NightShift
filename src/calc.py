import math


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

    def square_root(self, x: float) -> float:
        if x < 0:
            raise ValueError("Cannot calculate square root of negative number")
        return float(math.sqrt(x))

    def cube(self, x: float) -> float:
        return float(x ** 3)


if __name__ == "__main__":
    calc = Calculator()
    print("=== Calculator Live Demo (Cumulative Verified Features) ===")
    print(f"  2 + 3    = {calc.add(2, 3)}")
    print(f"  10 - 4   = {calc.subtract(10, 4)}")
    print(f"  3 * 7    = {calc.multiply(3, 7)}")
    print(f"  15 / 3   = {calc.divide(15, 3)}")
    print(f"  2 ^ 8    = {calc.power(2, 8)}")
    print(f"  10 % 3   = {calc.modulo(10, 3)}")
    print(f"  25 / 200 = {calc.percentage(25, 200)}%")
    print(f"  sqrt(16) = {calc.square_root(16)}")
    print(f"  cube(3)  = {calc.cube(3)}")

