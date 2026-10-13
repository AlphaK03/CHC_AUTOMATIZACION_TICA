"""Sesión local para comprobar el enlace Base BLs → motor original → SQLite/CSV."""
class Session:
    async def query(self, record):
        return {'status':'success','columns':['BL','Aduana','manifiesto','bls'],
                'rows':[[record['BL original'],'013',record['IDManifiesto'],record['BL original']]]}
    async def close(self):
        pass
