"""
Migration: Create eudr_farming_analyses table.
Run on server: python scripts/migrate_eudr_farming_analysis.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import async_session_factory


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS eudr_farming_analyses (
    id                              VARCHAR(36)   PRIMARY KEY DEFAULT gen_random_uuid()::text,
    parcel_id                       VARCHAR(36)   NOT NULL REFERENCES land_parcels(id) ON DELETE CASCADE,
    farm_id                         VARCHAR(36)   NOT NULL REFERENCES farms(id) ON DELETE CASCADE,

    -- Farming start detection
    farming_start_month             VARCHAR(7)    NULL,
    farming_start_confidence        VARCHAR(10)   NULL,

    -- Land clearing event
    land_clearing_month             VARCHAR(7)    NULL,
    clearing_confidence             VARCHAR(10)   NULL,

    -- Deforestation / forest evidence
    forest_present_before_clearing  INTEGER       NOT NULL DEFAULT 0,
    pre_2020_farming_confirmed      INTEGER       NOT NULL DEFAULT 0,

    -- Hansen GFC data
    hansen_treecover2000            FLOAT         NULL,
    hansen_loss_year                INTEGER       NULL,
    hansen_was_forested             INTEGER       NULL,
    hansen_tile                     VARCHAR(20)   NULL,

    -- EUDR verdict
    eudr_status                     VARCHAR(30)   NULL,
    eudr_summary                    VARCHAR(500)  NULL,
    eudr_risk_flags                 JSONB         NULL,

    -- Data quality
    timeseries_months               INTEGER       NULL,
    cloud_gap_months                INTEGER       NULL,

    -- Monthly chart data (all indices per month)
    chart_data                      JSONB         NULL,

    -- BaseModel standard columns
    created_at                      TIMESTAMP     NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMP     NOT NULL DEFAULT NOW(),
    deleted_at                      TIMESTAMP     NULL,
    is_deleted                      INTEGER       NOT NULL DEFAULT 0,
    status                          VARCHAR(50)   DEFAULT 'active',
    notes                           TEXT          NULL,
    extra_metadata                  JSONB         NULL,
    audit_log                       JSONB         NULL,
    analysed_at                     TIMESTAMP     NULL,

    CONSTRAINT eudr_farming_analyses_uuid_format CHECK (length(id) = 36),
    CONSTRAINT eudr_farming_analyses_parcel_unique UNIQUE (parcel_id)
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_eudr_farming_parcel   ON eudr_farming_analyses (parcel_id);",
    "CREATE INDEX IF NOT EXISTS idx_eudr_farming_farm     ON eudr_farming_analyses (farm_id);",
    "CREATE INDEX IF NOT EXISTS idx_eudr_farming_status   ON eudr_farming_analyses (eudr_status);",
    "CREATE INDEX IF NOT EXISTS idx_eudr_farming_start    ON eudr_farming_analyses (farming_start_month);",
]

UPDATED_AT_TRIGGER = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'eudr_farming_analyses_updated_at'
    ) THEN
        CREATE TRIGGER eudr_farming_analyses_updated_at
        BEFORE UPDATE ON eudr_farming_analyses
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END
$$;
"""


async def migrate():
    async with async_session_factory() as db:
        print("Creating eudr_farming_analyses table...")
        await db.execute(text(CREATE_TABLE))

        for idx_sql in CREATE_INDEXES:
            await db.execute(text(idx_sql))
            print(f"  Index: {idx_sql[:60]}...")

        # Only add trigger if the update_updated_at_column() function exists
        try:
            await db.execute(text(UPDATED_AT_TRIGGER))
            print("  Trigger: updated_at auto-update attached.")
        except Exception as e:
            print(f"  Trigger skipped (function may not exist): {e}")

        await db.commit()
        print("Migration complete: eudr_farming_analyses table ready.")


if __name__ == "__main__":
    asyncio.run(migrate())
