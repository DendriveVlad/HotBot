from time import time

import sqlalchemy as sql
from sqlalchemy.engine.url import URL

from config import DATABASE


class DB:
    def __init__(self):
        self.engine = sql.create_engine(URL(**DATABASE))  # Запуск движка для MySQL
        self.db = self.engine.connect()  # Подключение к базе.
        self.md = sql.MetaData()  # Метаданные
        self.private_voices = sql.Table('private_voices', self.md, autoload=True, autoload_with=self.engine)
        self.users = sql.Table('users', self.md, autoload=True, autoload_with=self.engine)
        self.info = sql.Table('info', self.md, autoload=True, autoload_with=self.engine)
        self.games = sql.Table('games', self.md, autoload=True, autoload_with=self.engine)
        self.last_start = int(time())

    # date(where): "name == value" or "", column: (name1, name2...) or name
    def select(self, table, data="", *column):
        self.__reload()
        cols = []
        if column:
            for i in column:
                cols.append(eval(f"self.{table}.columns.{i}"))

        else:
            cols.append(eval(f"self.{table}"))
        if data:
            where = (eval(f"self.{table}.columns.{data}"))
            query = sql.select(cols).where(where)
        else:
            query = sql.select(cols)

        outputs = []
        if not column:
            column = [c.key for c in eval(f"self.{table}.columns")]
        for d in self.db.execute(query).fetchall():
            out = {}
            for i in range(len(d)):
                out[column[i]] = d[i]
            outputs.append(out)
        if len(outputs) == 1:
            return outputs[0]
        return outputs if outputs else None

    # date: {"name": value, ...}
    def insert(self, table, **data):
        self.__reload()
        self.db.execute(sql.insert(eval(f"self.{table}")).values(data))

    # date: "name == value"
    def delete(self, table, date):
        self.__reload()
        query = sql.delete(eval(f"self.{table}"))
        self.db.execute(query.where(eval(f"self.{table}.columns.{date}")))

    # where = "name == value", date: {"name": value, ...}
    def update(self, table, where, **date):
        self.__reload()
        query = sql.update(eval(f"self.{table}")).values(date)
        self.db.execute(query.where(eval(f"self.{table}.columns.{where}")))

    def __close(self):
        self.db.close()
        self.engine.dispose()

    def __reload(self):
        if int(time()) - self.last_start >= 600:
            self.__close()
            self.__init__()


if __name__ == "__main__":
    db = DB()
    db.delete("games", "game_cost == 0")
    print(db.select("games"))

