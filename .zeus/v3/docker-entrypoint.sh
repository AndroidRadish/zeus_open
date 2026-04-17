#!/bin/sh
set -e

DB_URL="${ZEUS_DATABASE_URL:-sqlite+aiosqlite:////app/.zeus/v3/state.db}"

# Ensure schema exists before writing meta
python -c "
import asyncio
from db.engine import make_async_engine
from db.models import Base
engine = make_async_engine('$DB_URL')
async def ensure():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
asyncio.run(ensure())
"

if [ "$ZEUS_MODE" = "scheduler" ]; then
    python -c "
import asyncio
from store.sqlite_store import SQLiteStateStore
store = SQLiteStateStore('$DB_URL')
async def init():
    await store.set_meta('scheduler_target_state', 'running')
    await store.close()
asyncio.run(init())
"
elif [ "$ZEUS_MODE" = "worker" ]; then
    python -c "
import asyncio
from store.sqlite_store import SQLiteStateStore
store = SQLiteStateStore('$DB_URL')
async def init():
    await store.set_meta('worker_target_count', ${ZEUS_MAX_WORKERS:-3})
    await store.close()
asyncio.run(init())
"
fi

exec python /app/.zeus/v3/scripts/run.py "$@"
