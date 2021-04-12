from .utils import collect_attr_from_applications
import aiosqlite
from .dependency_resolver import check_dependencies
from datetime import datetime


async def is_table_present(con, table_name):
    cur = await con.execute(
        """ select count(1)  from sqlite_master where name=? and type= 'table'; """,
        [
            table_name,
        ],
    )
    res = await cur.fetchone()
    return res[0] > 0


class SqliteMigrator:
    def __init__(self, dburl, applist):
        self.dburl = dburl
        self.applist = applist
        self.pool = None

    async def create_migrations_table(self, con):
        await con.execute(
            """
                create table kcore_migrations (
                id  INTEGER PRIMARY KEY,
                migration_id  INTEGER,
                name TEXT,
                executed INTEGER DEFAULT 0
                );"""
        )
        await con.commit()

    async def make_sure_migrations_table_present(self, con):
        need_to_create_table = not await is_table_present(con, "kcore_migrations")
        if need_to_create_table:
            await self.create_migrations_table(con)

    async def get_current_status_from_db(self, con):
        cursor = await con.execute(
            """
            select * from kcore_migrations
        """
        )
        rows = await cursor.fetchall()
        return rows

    async def setup(self, con):
        await self.make_sure_migrations_table_present(con)

    async def check_migration_already_run(self, con, migration_name):
        cursor = await con.execute(
            """select executed from kcore_migrations where name = ?""",
            [migration_name],
        )
        executed = await cursor.fetchone()
        return True if executed[0] == 1 else False

    async def create_migration_in_table(self, con, migration_name):
        cursor = await con.execute(
            "select 1 from kcore_migrations where name=?",
            [migration_name],
        )
        already_exists = await cursor.fetchone()
        if not already_exists:
            await con.execute(
                """
                insert into kcore_migrations(name) values(?)
            """,
                [migration_name],
            )
            await con.commit()
            print("created mig")
            return None

    async def mark_migration_executed(self, con, migration_name):
        await con.execute(
            """
            update kcore_migrations set executed=? where name=?
        """,
            [True, migration_name],
        )
        await con.commit()
        return None

    async def mark_migration_notexecuted(self, con, migration_name):
        await con.execute(
            """
            update kcore_migrations set executed=? where name=?
        """,
            [False, migration_name],
        )
        await con.commit()
        return None

    async def run_migration(self, con, migration):
        await migration.forward(con, ctx={})
        await self.mark_migration_executed(con, migration.name)

    async def run_migrations(self, con, migration_path, app_migrations):
        inapp = {m.name: m for m in app_migrations}
        for migration_name in migration_path:
            print("running", migration_name)
            breakpoint()
            await self.create_migration_in_table(con, migration_name)
            migration_run = await self.check_migration_already_run(con, migration_name)
            if not migration_run:
                await self.run_migration(con, inapp[migration_name])
        await con.commit()

    async def migrate(self):
        async with aiosqlite.connect(self.dburl) as con:
            # check if migration history table exists
            await self.setup(con)
            list_of_lists = collect_attr_from_applications(
                self.applist, "schema", "migrations"
            )
            app_migrations = []
            for appmigs in list_of_lists:
                for mig in appmigs:
                    app_migrations.append(mig)
            path = check_dependencies(app_migrations, show_graph=True)
            await self.run_migrations(con, path, app_migrations)

    async def show_migrations(self):
        async with aiosqlite.connect(self.dburl) as con:
            res = await self.get_current_status_from_db(con)
            if res:
                for m in res:
                    ex = "executed" if m["executed"] else "not run"
                    print(f" {m['migration_id']} {m['name']} {ex}")
            else:
                print("no migrations found")

    async def run(self, operation):
        if operation == "run":
            await self.migrate()
        if operation == "show":
            await self.show_migrations()

    async def reset_db(
        self,
    ):
        async with aiosqlite.connect(self.dburl) as con:
            await self.setup(con)
            list_of_lists = collect_attr_from_applications(
                self.applist, "schema", "migrations"
            )
            app_migrations = []
            for appmigs in list_of_lists:
                for mig in appmigs:
                    app_migrations.append(mig)
            res = await self.get_current_status_from_db(con)
            migrations_run = [
                migration_action["name"]
                for migration_action in sorted(res, key=lambda x: x["id"], reverse=True)
            ]
            migrations_in_app = {mig.name: mig for mig in app_migrations}
            for mig in migrations_run:
                print("remove", mig)
                code_mig = migrations_in_app[mig]
                try:
                    await code_mig.backward(con, {})
                except Exception:
                    pass
                await self.mark_migration_notexecuted(con, mig)
