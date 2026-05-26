"""
Migration: Create eudr_exporter_submissions and eudr_importer_submissions tables.
Run once on the server: python migrate_eudr_portal_tables.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

DDL = [
    # ── Exporter submissions ──
    """
    CREATE TABLE IF NOT EXISTS eudr_exporter_submissions (
        id                  VARCHAR(36)  PRIMARY KEY,
        reference_number    VARCHAR(50)  NOT NULL UNIQUE,
        status              VARCHAR(20)  NOT NULL DEFAULT 'submitted',
        full_name           VARCHAR(200),
        email               VARCHAR(200),
        phone               VARCHAR(50),
        national_id         VARCHAR(100),
        country_of_residence VARCHAR(100),
        company_name        VARCHAR(300),
        business_reg_number VARCHAR(100),
        consignment_ref     VARCHAR(100),
        coffee_variety      VARCHAR(50),
        quantity_kg         VARCHAR(50),
        harvest_year        VARCHAR(10),
        origin_country      VARCHAR(100),
        destination_country VARCHAR(100),
        form_data           JSONB,
        documents           JSONB DEFAULT '[]'::jsonb,
        ip_address          VARCHAR(50),
        submitted_at        TIMESTAMP    NOT NULL DEFAULT NOW(),
        updated_at          TIMESTAMP    NOT NULL DEFAULT NOW()
    );
    """,

    # Indexes for exporter
    "CREATE INDEX IF NOT EXISTS ix_eudr_exp_email         ON eudr_exporter_submissions (email);",
    "CREATE INDEX IF NOT EXISTS ix_eudr_exp_company       ON eudr_exporter_submissions (company_name);",
    "CREATE INDEX IF NOT EXISTS ix_eudr_exp_consignment   ON eudr_exporter_submissions (consignment_ref);",
    "CREATE INDEX IF NOT EXISTS ix_eudr_exp_submitted_at  ON eudr_exporter_submissions (submitted_at DESC);",

    # ── Importer submissions ──
    """
    CREATE TABLE IF NOT EXISTS eudr_importer_submissions (
        id                  VARCHAR(36)  PRIMARY KEY,
        reference_number    VARCHAR(50)  NOT NULL UNIQUE,
        status              VARCHAR(20)  NOT NULL DEFAULT 'submitted',
        full_name           VARCHAR(200),
        email               VARCHAR(200),
        phone               VARCHAR(50),
        eu_member_state     VARCHAR(100),
        company_name        VARCHAR(300),
        eori_number         VARCHAR(100),
        exporter_name       VARCHAR(300),
        consignment_ref     VARCHAR(100),
        risk_conclusion     VARCHAR(50),
        form_data           JSONB,
        documents           JSONB DEFAULT '[]'::jsonb,
        ip_address          VARCHAR(50),
        submitted_at        TIMESTAMP    NOT NULL DEFAULT NOW(),
        updated_at          TIMESTAMP    NOT NULL DEFAULT NOW()
    );
    """,

    # Indexes for importer
    "CREATE INDEX IF NOT EXISTS ix_eudr_imp_email         ON eudr_importer_submissions (email);",
    "CREATE INDEX IF NOT EXISTS ix_eudr_imp_company       ON eudr_importer_submissions (company_name);",
    "CREATE INDEX IF NOT EXISTS ix_eudr_imp_eori          ON eudr_importer_submissions (eori_number);",
    "CREATE INDEX IF NOT EXISTS ix_eudr_imp_consignment   ON eudr_importer_submissions (consignment_ref);",
    "CREATE INDEX IF NOT EXISTS ix_eudr_imp_submitted_at  ON eudr_importer_submissions (submitted_at DESC);",

    # Auto-update updated_at trigger
    """
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
    $$ language 'plpgsql';
    """,
    """
    DO $$ BEGIN
        CREATE TRIGGER trg_eudr_exp_updated_at
            BEFORE UPDATE ON eudr_exporter_submissions
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """,
    """
    DO $$ BEGIN
        CREATE TRIGGER trg_eudr_imp_updated_at
            BEFORE UPDATE ON eudr_importer_submissions
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """,
]


async def main():
    engine = create_async_engine(settings.database.async_url, echo=True)
    async with engine.begin() as conn:
        for stmt in DDL:
            stmt = stmt.strip()
            if not stmt:
                continue
            try:
                await conn.exec_driver_sql(stmt)
                first_line = stmt.splitlines()[0][:80]
                print(f"OK: {first_line}")
            except Exception as e:
                print(f"SKIP ({e}): {stmt[:60]}")
    await engine.dispose()
    print("\nMigration complete.")


if __name__ == "__main__":
    asyncio.run(main())
