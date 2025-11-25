"""Sample module for Tree-sitter analysis demo.

This module demonstrates various Python constructs that Tree-sitter can analyze:
- Classes and methods
- Functions with type hints
- Decorators (routes, fixtures, dataclasses)
- Imports
- Function calls
"""

import os
import sys
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class User:
    """A user in the system."""
    name: str
    email: str
    age: int = 0


class Calculator:
    """A simple calculator with basic operations."""

    def __init__(self):
        self.history = []

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        result = a + b
        self.history.append(f"add({a}, {b}) = {result}")
        return result

    def subtract(self, a: int, b: int) -> int:
        """Subtract b from a."""
        result = a - b
        self.history.append(f"subtract({a}, {b}) = {result}")
        return result

    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers."""
        result = a * b
        self.history.append(f"multiply({a}, {b}) = {result}")
        return result

    def divide(self, a: int, b: int) -> float:
        """Divide a by b."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        self.history.append(f"divide({a}, {b}) = {result}")
        return result

    def get_history(self) -> List[str]:
        """Return operation history."""
        return self.history.copy()


class AdvancedCalculator(Calculator):
    """Extended calculator with more operations."""

    def power(self, base: int, exp: int) -> int:
        """Raise base to the power of exp."""
        result = base ** exp
        self.history.append(f"power({base}, {exp}) = {result}")
        return result

    def factorial(self, n: int) -> int:
        """Calculate factorial of n."""
        if n < 0:
            raise ValueError("Factorial not defined for negative numbers")
        if n <= 1:
            return 1
        result = 1
        for i in range(2, n + 1):
            result *= i
        self.history.append(f"factorial({n}) = {result}")
        return result


def process_users(users: List[User]) -> dict:
    """Process a list of users and return statistics."""
    if not users:
        return {"count": 0, "avg_age": 0}

    total_age = sum(u.age for u in users)
    avg_age = total_age / len(users)

    return {
        "count": len(users),
        "avg_age": avg_age,
        "names": [u.name for u in users]
    }


def validate_email(email: str) -> bool:
    """Simple email validation."""
    if not email:
        return False
    if "@" not in email:
        return False
    parts = email.split("@")
    if len(parts) != 2:
        return False
    return len(parts[0]) > 0 and len(parts[1]) > 2


def main():
    """Main entry point."""
    # Create some users
    users = [
        User("Alice", "alice@example.com", 30),
        User("Bob", "bob@example.com", 25),
        User("Charlie", "charlie@example.com", 35),
    ]

    # Process users
    stats = process_users(users)
    print(f"User stats: {stats}")

    # Use calculator
    calc = AdvancedCalculator()
    result = calc.add(10, 5)
    result = calc.multiply(result, 2)
    result = calc.power(result, 2)
    print(f"Calculation result: {result}")
    print(f"History: {calc.get_history()}")


if __name__ == "__main__":
    main()
