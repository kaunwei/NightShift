import unittest
from src.greeting import hello


class TestGreeting(unittest.TestCase):
    def test_hello_standard_name(self):
        self.assertEqual(hello("World"), "Hello, World!")

    def test_hello_custom_name(self):
        self.assertEqual(hello("Alice"), "Hello, Alice!")
        self.assertEqual(hello("Bob"), "Hello, Bob!")

    def test_hello_empty_string(self):
        self.assertEqual(hello(""), "Hello, !")


if __name__ == "__main__":
    unittest.main()
