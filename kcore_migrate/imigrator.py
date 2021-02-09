from .utils import collect_attr_from_applications

class IMigrator(object):
    def __init__(self, backend):
        self.backend = backend
    
    async def run(self, operation):
        if operation == 'run':
            await self.migrate()
        if operation == 'show':
            await self.show_migrations()

    async def show_migrations(self):
        res = await self.backend.get_current_migration_status()
        if res:
            for m in res:
                ex = 'executed' if m['executed'] else 'not run'
                print(f" {m['migration_id']} {m['name']} {ex}")
        else:
            print("no migrations found")