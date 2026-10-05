import random
import string

def generate_password(length=8, include_uppercase=True, include_lowercase=True, include_numbers=True, include_symbols=True):
    """
    Generates a password with the specified length and character sets.

    :param length: Length of the password (default is 8)
    :param include_uppercase: Boolean indicating whether to include uppercase letters (default is True)
    :param include_lowercase: Boolean indicating whether to include lowercase letters (default is True)
    :param include_numbers: Boolean indicating whether to include numbers (default is True)
    :param include_symbols: Boolean indicating whether to include symbols (default is True)
    :return: Generated password
    """
    if not include_uppercase and not include_lowercase and not include_numbers and not include_symbols:
        raise ValueError("At least one character set must be included.")

    characters = ''
    if include_uppercase:
        characters += string.ascii_uppercase
    if include_lowercase:
        characters += string.ascii_lowercase
    if include_numbers:
        characters += string.digits
    if include_symbols:
        characters += string.punctuation

    if not characters:
        raise ValueError("No character sets selected. At least one must be included.")

    password = ''.join(random.choice(characters) for _ in range(length))
    return password
