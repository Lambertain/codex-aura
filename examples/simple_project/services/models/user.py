from config import DATABASE_URL


class User:
    def __init__(self, name):
        self.name = name

    def get_db_url(self):
        return DATABASE_URL