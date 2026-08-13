from backend.database import engine, Base
from backend.models import domain
Base.metadata.create_all(bind=engine)
print("Migration completed.")
