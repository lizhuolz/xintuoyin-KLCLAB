from ..providers.sql_provider import get_sql_provider


class UserService:
    @staticmethod
    def get_current_user():
        provider = get_sql_provider()
        return provider.get_current_user()
