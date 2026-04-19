"""
Plotra Platform - Sample Seed Data
Generates test data for development and testing
"""
import uuid
import hashlib
from datetime import datetime, timedelta
import random
from app.models import *

# Sample data for development
SAMPLE_FARMERS = [
    {
        "email": "farmer1@plotra.africa",
        "first_name": "John",
        "last_name": "Mwangi",
        "phone": "+254712345678",
        "national_id": "12345678",
        "county": "Central",
        "district": "Nyeri",
        "coffee_varieties": ["SL28", "SL34"],
        "years_farming": 15,
    },
    {
        "email": "farmer2@plotra.africa",
        "first_name": "Mary",
        "last_name": "Wanjiku",
        "phone": "+254723456789",
        "national_id": "23456789",
        "county": "Eastern",
        "district": "Embu",
        "coffee_varieties": ["Ruiru11", "Batian"],
        "years_farming": 10,
    },
]

SAMPLE_COOPERATIVE = {
    "name": "Nyeri Coffee Farmers Cooperative",
    "registration_number": "COOP/2020/001",
    "email": "info@nyericoop.africa",
    "phone": "+254700000000",
    "county": "Central",
    "district": "Nyeri",
}

# Helper functions
def generate_uuid():
    return str(uuid.uuid4())

import bcrypt
def hash_password(password: str = "password123") -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def generate_sample_parcel(farm_id: str, parcel_num: int) -> dict:
    """Generate sample GPS polygon for a parcel"""
    # Sample coordinates for Nyeri area
    base_lat = -0.4197 + random.uniform(-0.01, 0.01)
    base_lon = 36.9570 + random.uniform(-0.01, 0.01)
    
    # Generate polygon points
    points = []
    for i in range(6):  # Hexagon
        angle = i * 60
        lat_offset = 0.002 * random.uniform(0.5, 1.5) * (1 if i % 2 == 0 else 0.8)
        lon_offset = 0.002 * random.uniform(0.5, 1.5)
        points.append([
            round(base_lon + lon_offset * (i % 3 - 1), 6),
            round(base_lat + lat_offset, 6)
        ])
    
    # Close the polygon
    points.append(points[0])
    
    return {
        "parcel_number": str(parcel_num),
        "parcel_name": f"Parcel {parcel_num}",
        "boundary_geojson": {
            "type": "Polygon",
            "coordinates": [points]
        },
        "area_hectares": round(random.uniform(0.5, 3.0), 2),
        "gps_accuracy_meters": round(random.uniform(3, 10), 1),
        "land_use_type": "agroforestry",
        "coffee_area_hectares": round(random.uniform(0.3, 2.0), 2),
    }

# Main seed function
async def seed_database(db_session):
    """Seed the database with sample data"""
    from app.models.user import User, UserRole, UserStatus, Cooperative, CooperativeMember
    from app.models.farm import Farm, LandParcel, LandDocument, DocumentType, OwnershipType
    from app.models.traceability import Delivery, Batch, ProcessingMethod
    from app.models.satellite import SatelliteObservation, SatelliteProvider
    from app.models.payments import IncentiveRule
    from app.models.sustainability import IncentiveClaim, IncentiveType
    
    print("Seeding database...")
    
     # Create admin user
    admin_user = User(
        email="admin@plotra.africa",
        password_hash=hash_password("password123"),
        first_name="Admin",
        last_name="User",
        phone="+254700000001",
        national_id="99999999",
        role=UserRole.PLOTRA_ADMIN,
        status=UserStatus.ACTIVE,
    )
    db_session.add(admin_user)
    await db_session.flush()
    
    # Create cooperative
    cooperative = Cooperative(
        name=SAMPLE_COOPERATIVE["name"],
        registration_number=SAMPLE_COOPERATIVE["registration_number"],
        email=SAMPLE_COOPERATIVE["email"],
        phone=SAMPLE_COOPERATIVE["phone"],
        county=SAMPLE_COOPERATIVE["county"],
        district=SAMPLE_COOPERATIVE["district"],
    )
    db_session.add(cooperative)
    await db_session.flush()
    
    # Create farmers
    for farmer_data in SAMPLE_FARMERS:
        # Create user
        user = User(
            email=farmer_data["email"],
            password_hash=hash_password(),
            first_name=farmer_data["first_name"],
            last_name=farmer_data["last_name"],
            phone=farmer_data["phone"],
            national_id=farmer_data["national_id"],
            county=farmer_data["county"],
            district=farmer_data["district"],
            role=UserRole.FARMER,
            status=UserStatus.ACTIVE,
        )
        db_session.add(user)
        await db_session.flush()
        
        # Create membership
        membership = CooperativeMember(
            user_id=user.id,
            cooperative_id=cooperative.id,
            membership_number=f"MBR/{cooperative.id[:8]}/{user.id[:4]}",
            is_active=True,
        )
        db_session.add(membership)
        
        # Create farm
        farm = Farm(
            owner_id=user.id,
            cooperative_id=cooperative.id,
            farm_name=f"{farmer_data['first_name']}'s Farm",
            farm_code=f"FRM/{user.id[:8]}",
            coffee_varieties=farmer_data["coffee_varieties"],
            years_farming=farmer_data["years_farming"],
            total_area_hectares=2.5,
            coffee_area_hectares=1.5,
        )
        db_session.add(farm)
        await db_session.flush()
        
        # Create parcels with sustainability data
        for i in range(1, random.randint(2, 4)):
            parcel_data = generate_sample_parcel(farm.id, i)
            parcel = LandParcel(
                farm_id=farm.id,
                **parcel_data,
                shade_tree_count=random.randint(50, 200),  # Number of shade trees
                biomass_tons=random.uniform(10, 50),  # Biomass in tons
                ndvi_baseline=random.uniform(0.5, 0.9),  # NDVI baseline for soil health
                canopy_density=random.uniform(0.6, 0.95),  # Canopy density
            )
            db_session.add(parcel)
            await db_session.flush()
            
            # Create practice logs for each parcel
            from app.models.traceability import PracticeLog
            practice_types = ["pruning", "fertilizing", "intercropping", "shade_management", "harvesting"]
            for j in range(random.randint(2, 5)):
                practice = PracticeLog(
                    parcel_id=parcel.id,
                    practice_type=random.choice(practice_types),
                    practice_date=datetime.now() - timedelta(days=random.randint(1, 90)),
                    description=f"Performed {random.choice(practice_types)} on parcel {i}",
                    is_organic=random.randint(0, 1),
                    labor_hours=random.uniform(2, 8),
                )
                db_session.add(practice)
            
            # Create biomass ledger entries
            from app.models.sustainability import BiomassLedger
            for quarter in range(1, 5):
                ledger = BiomassLedger(
                    parcel_id=parcel.id,
                    quarter=quarter,
                    year=datetime.now().year,
                    period_start=datetime(datetime.now().year, (quarter-1)*3+1, 1),
                    period_end=datetime(datetime.now().year, quarter*3, 28),
                    biomass_tons=random.uniform(10, 50),
                    biomass_source="satellite",
                    carbon_tons_co2=random.uniform(5, 25),
                    is_verified=True,
                )
                db_session.add(ledger)
        
         # Create document
        doc = LandDocument(
            farm_id=farm.id,
            document_type=DocumentType.CUSTOMARY_RIGHTS,
            title="Customary Land Rights Certificate",
            ownership_type=OwnershipType.CUSTOMARY,
            file_name="customary-rights-certificate.pdf",
        )
        db_session.add(doc)
        
        # Create payment escrow records for each farmer
        from app.models.payments import PaymentEscrow, PayoutStatus, IncentiveType
        
        # Regular payout
        payout = PaymentEscrow(
            reference_number=f"PAY/{generate_uuid()[:8]}",
            payer_id=str(cooperative.id),
            payer_name=SAMPLE_COOPERATIVE["name"],
            payee_id=str(user.id),
            payee_name=f"{farmer_data['first_name']} {farmer_data['last_name']}",
            amount=random.uniform(1000, 5000),
            status=PayoutStatus.RELEASED,
            conditions={"delivery_verified": True, "quality_checked": True},
            conditions_met={"delivery_verified": True, "quality_checked": True},
            payment_method="mpesa",
            payment_reference=f"MPESA/{random.randint(100000, 999999)}",
            transaction_id=f"TRX/{generate_uuid()[:12]}",
            description="Coffee delivery payout",
            created_at=datetime.now() - timedelta(days=random.randint(1, 30))
        )
        db_session.add(payout)
        
        # Conditional incentive
        incentive = PaymentEscrow(
            reference_number=f"INC/{generate_uuid()[:8]}",
            payer_id=str(cooperative.id),
            payer_name=SAMPLE_COOPERATIVE["name"],
            payee_id=str(user.id),
            payee_name=f"{farmer_data['first_name']} {farmer_data['last_name']}",
            amount=random.uniform(500, 2000),
            status=PayoutStatus.CONDITIONAL,
            conditions={"sustainability_score": 80, "eudr_compliant": True},
            conditions_met={"sustainability_score": 75, "eudr_compliant": True},
            payment_method="mpesa",
            description="Sustainability incentive",
            created_at=datetime.now() - timedelta(days=random.randint(1, 14))
        )
        db_session.add(incentive)
        
        # Create incentive claims for farmers
        from app.models.sustainability import IncentiveClaim, IncentiveRule, IncentiveType
        
        # Create some incentive rules first
        incentive_rules = [
            {
                "rule_code": "SUSTAINABILITY_BONUS",
                "rule_name": "Sustainability Bonus",
                "incentive_type": IncentiveType.SUSTAINABILITY_BONUS,
                "percentage_rate": 10.0,
            },
            {
                "rule_code": "GENDER_INCENTIVE",
                "rule_name": "Women Farmer Bonus",
                "incentive_type": IncentiveType.GENDER_INCENTIVE,
                "percentage_rate": 15.0,
            },
        ]
        
        for rule_data in incentive_rules:
            rule = IncentiveRule(
                rule_code=rule_data["rule_code"],
                rule_name=rule_data["rule_name"],
                incentive_type=rule_data["incentive_type"],
                calculation_type="percentage",
                conditions={},
                percentage_rate=rule_data["percentage_rate"],
                is_active=True,
            )
            db_session.add(rule)
        
        await db_session.flush()
        
        # Create incentive claims for each farmer
        rules_result = await db_session.execute(
            select(IncentiveRule).where(IncentiveRule.is_active == True)
        )
        rules = rules_result.scalars().all()
        
        for farmer_data in SAMPLE_FARMERS:
            farmer_result = await db_session.execute(
                select(User).where(User.email == farmer_data["email"])
            )
            farmer = farmer_result.scalar_one_or_none()
            
            if farmer and rules:
                for rule in rules:
                    claim = IncentiveClaim(
                        farmer_id=farmer.id,
                        rule_id=rule.id,
                        claim_number=f"CLM/{generate_uuid()[:8]}",
                        base_amount=random.uniform(1000, 5000),
                        bonus_amount=random.uniform(100, 500),
                        total_amount=random.uniform(1100, 5500),
                        currency="KES",
                        status=random.choice(["approved", "paid"]),
                        notes=f"{rule.rule_name} claim",
                    )
                    db_session.add(claim)
    
    # Create some cooperative-level payments
    for i in range(3):
        coop_payment = PaymentEscrow(
            reference_number=f"COOP/{generate_uuid()[:8]}",
            payer_id="123456789",
            payer_name="Plotra Platform",
            payee_id=str(cooperative.id),
            payee_name=SAMPLE_COOPERATIVE["name"],
            amount=random.uniform(10000, 50000),
            status=random.choice([PayoutStatus.RELEASED, PayoutStatus.PENDING]),
            conditions={"batch_processed": True},
            conditions_met={"batch_processed": True},
            payment_method="bank",
            payment_reference=f"BANK/{random.randint(1000000000, 9999999999)}",
            transaction_id=f"TRX/{generate_uuid()[:12]}",
            description="Cooperative bulk payment",
            created_at=datetime.now() - timedelta(days=random.randint(1, 60))
        )
        db_session.add(coop_payment)
    
    await db_session.commit()
    print("Database seeded successfully!")

if __name__ == "__main__":
    import asyncio
    from app.core.database import engine, async_session_factory
    from app.core.config import settings
    from app.models.base import Base
    
    async def main():
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Seed data
        async with async_session_factory() as session:
            await seed_database(session)
    
    asyncio.run(main())
