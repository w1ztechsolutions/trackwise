"""Input validation helpers for authentication flows."""

import re


def validate_email(email: str) -> bool:
    pattern = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
    return bool(pattern.match(email))


def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < 12:
        return False, 'Password must be at least 12 characters long.'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter.'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter.'
    if not re.search(r'\d', password):
        return False, 'Password must contain at least one digit.'
    if not re.search(r'[!@#\$%^&*()_+\-=\[\]{};:\'"\|,.<>\/?]', password):
        return False, 'Password must contain at least one special character.'
    return True, ''
