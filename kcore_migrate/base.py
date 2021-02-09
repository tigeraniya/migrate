import attr

class Migration:
    def __init__(self,identifier,depends_on=None):
        self.identifier = identifier
        self.depends_on = set() if not depends_on else set(depends_on)

    @property
    def name(self):
        return self.identifier

    async def forward(self, con,ctx=None):
        pass

    async def backward(self, con, ctx=None):
        pass

@attr.s
class MigrationStatus:
    executed = attr.ib()