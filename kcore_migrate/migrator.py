from asyncpg import connect, create_pool
from .utils import collect_attr_from_applications
from postgis.asyncpg import register as dbregister
from .dependency_resolver import check_dependencies
from datetime import datetime


async def is_table_present(con, table_name):
    res = await con.fetchval(
        """ select count(1) from pg_catalog.pg_tables where tablename=$1 """, table_name
    )
    return res > 0


class PostgresMigrator:
    def __init__(self, dburl, applist):
        self.dburl = dburl
        self.applist = applist
        self.pool = None

    async def create_migrations_table(self, con):
        await con.execute(
            """
            create table kcore_migrations (
              id  BIGSERIAL PRIMARY KEY,
              migration_id  BIGSERIAL,
              name VARCHAR,
              executed BOOLEAN DEFAULT FALSE
            );"""
        )

    async def make_sure_migrations_table_present(self, con):
        need_to_create_table = not await is_table_present(con, "kcore_migrations")
        if need_to_create_table:
            await self.create_migrations_table(con)

    async def get_current_status_from_db(self, con):
        return await con.fetch(
            """
            select * from kcore_migrations
        """
        )

    async def setup(self, con):
        await self.make_sure_migrations_table_present(con)

    async def check_migration_already_run(self, con, migration_name):
        return await con.fetchval(
            """select executed from kcore_migrations where name = $1""", migration_name
        )

    async def create_migration_in_table(self, con, migration_name):
        already_exists = await con.fetchval(
            "select 1 from kcore_migrations where name=$1", migration_name
        )
        if not already_exists:
            return await con.execute(
                """
                insert into kcore_migrations(name) values($1)
            """,
                migration_name,
            )

    async def mark_migration_executed(self, con, migration_name):
        return await con.execute(
            """
            update kcore_migrations set executed=$1 where name=$2
        """,
            True,
            migration_name,
        )

    async def mark_migration_notexecuted(self, con, migration_name):
        return await con.execute(
            """
            update kcore_migrations set executed=$1 where name=$2
        """,
            False,
            migration_name,
        )

    async def run_migration(self, con, migration):
        await migration.forward(con, ctx={})
        await self.mark_migration_executed(con, migration.name)

    async def run_migrations(self, con, migration_path, app_migrations):
        inapp = {m.name: m for m in app_migrations}
        for migration_name in migration_path:
            await self.create_migration_in_table(con, migration_name)
            migration_run = await self.check_migration_already_run(con, migration_name)
            if not migration_run:
                await self.run_migration(con, inapp[migration_name])

    async def migrate(self):
        self.pool = await create_pool(self.dburl, max_size=100, init=dbregister)

        # check if migration history table exists
        async with self.pool.acquire() as con:
            async with con.transaction():
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
        self.pool = await create_pool(self.dburl, max_size=100, init=dbregister)
        async with self.pool.acquire() as con:
            async with con.transaction():
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
        self.pool = await create_pool(self.dburl, max_size=100, init=dbregister)
        async with self.pool.acquire() as con:
            ncon = con
            await self.setup(ncon)
            list_of_lists = collect_attr_from_applications(
                self.applist, "schema", "migrations"
            )
            app_migrations = []
            for appmigs in list_of_lists:
                for mig in appmigs:
                    app_migrations.append(mig)
            res = await self.get_current_status_from_db(ncon)
            migrations_run = [
                migration_action["name"]
                for migration_action in sorted(res, key=lambda x: x["id"], reverse=True)
            ]
            migrations_in_app = {mig.name: mig for mig in app_migrations}
            for mig in migrations_run:
                print("remove", mig)
                code_mig = migrations_in_app[mig]
                try:
                    await code_mig.backward(ncon, {})
                except Exception:
                    pass
                await self.mark_migration_notexecuted(ncon, mig)
