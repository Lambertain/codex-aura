from config import DATABASE_URL, DEBUG


def get_db_url():
    return DATABASE_URL


def is_debug():
    return DEBUG