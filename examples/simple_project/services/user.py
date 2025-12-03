from utils import get_db_url
from .models.user import User


def create_user(name):
    return User(name)


def get_user_db_url():
    return get_db_url()