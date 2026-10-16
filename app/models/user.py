# REVIEW: Re-export user model for backward compatibility with modular app design.
from models import User as UserModel

User = UserModel

__all__ = ["User"]