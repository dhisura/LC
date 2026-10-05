import unittest
from password_gen import generate_password

class TestPasswordGenerator(unittest.TestCase):
    def test_password_length(self):
        """Test that the password has the correct length."""
        password = generate_password(length=12)
        self.assertEqual(len(password), 12)

    def test_include_uppercase(self):
        """Test that uppercase letters are included in the password."""
        password = generate_password(include_uppercase=True)
        self.assertIn(random.choice(string.ascii_uppercase), password)

    def test_include_symbols(self):
        """Test that symbols are included in the password."""
        password = generate_password(include_symbols=True)
        self.assertIn(random.choice(string.punctuation), password)

if __name__ == '__main__':
    unittest.main()
