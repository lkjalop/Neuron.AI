import asyncio, sys, os
os.environ['NEON_DATABASE_URL']='postgres://example'
from storage.migrations import apply_migrations
class MockPostgres:
    def __init__(self):
        self.executed=[]; self._migrations=set()
    async def execute(self, sql,*a):
        self.executed.append((sql.strip(),a))
        if sql.lower().startswith('insert into schema_migrations'):
            self._migrations.add(a[0])
    async def fetch(self, sql,*a):
        self.executed.append((sql.strip(),a))
        if sql.lower().startswith('select id from schema_migrations'):
            return [(m,) for m in sorted(self._migrations)]
        return []
mp=MockPostgres()
sys.modules['storage.postgres']=mp
async def run():
    await apply_migrations()
    mp.executed.clear()
    await apply_migrations()
    print('SECOND RUN:')
    for sql,_ in mp.executed:
        print(sql)
asyncio.run(run())