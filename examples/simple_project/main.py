from utils import is_debug
from services.user import create_user


if __name__ == "__main__":
    print("Debug mode:", is_debug())
    user = create_user("John")
    print("User created:", user.name)