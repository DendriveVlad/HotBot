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
    def select(self, table, data="", *columns):
        self.__reload()
        cols = []
        if columns:
            for column in columns:
                cols.append(eval(f"self.{table}.columns.{column}"))

        else:
            cols.append(eval(f"self.{table}"))
        if data:
            where = (eval(f"self.{table}.columns.{data}"))
            query = sql.select(cols).where(where)
        else:
            query = sql.select(cols)

        outputs = []
        if not columns:
            columns = [c.key for c in eval(f"self.{table}.columns")]
        for d in self.db.execute(query).fetchall():
            out = {}
            for column in range(len(d)):
                out[columns[column]] = d[column]
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
    # db.update("users", f"user_id == 280536559403532290", challenge_progress=5)
    print(db.select("users", f"user_id == 280536559403532290"))
    a = []
    for i in db.select("users"):
        if i["user_id"] in a:
            db.delete("users", f"user_id == {i['user_id']}")
            print(1)
        a.append(i["user_id"])
