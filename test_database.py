from database.service import DatabaseService

db = DatabaseService()

print("Sets:")

for s in db.get_sets():
    print(dict(s))

db.close()