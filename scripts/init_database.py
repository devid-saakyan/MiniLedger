import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.database import init_db, close_db


async def main():
    try:
        from infrastructure import models
        await init_db()
        print("✅ Database initialized successfully!")
        print("✅ All tables created!")
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())

