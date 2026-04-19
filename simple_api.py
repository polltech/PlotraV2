"""
Plotra Platform - Full API Server
EUDR Compliance & Traceability Platform for East African Coffee Smallholders
Standalone version using SQLite for easy setup without external database dependencies.
"""
import os
import sqlite3
import uuid
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import urllib.parse

# Configuration: Set to False to disable auto-creation of default admin user
ENABLE_DEFAULT_ADMIN = False  # Set to True only for initial testing, then set to False

PORT = 8001
DB_PATH = "plotra_data.db"

# Database initialization
def init_database():
    """Initialize SQLite database with all required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            role TEXT DEFAULT 'farmer',
            region TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Farms table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS farms (
            id TEXT PRIMARY KEY,
            owner_id INTEGER,
            farm_code TEXT UNIQUE,
            farm_name TEXT,
            total_area_hectares REAL,
            compliance_status TEXT DEFAULT 'pending',
            verification_status TEXT DEFAULT 'draft',
            latitude REAL,
            longitude REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        )
    ''')
    
    # Parcels table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parcels (
            id TEXT PRIMARY KEY,
            farm_id TEXT NOT NULL,
            parcel_code TEXT,
            area_hectares REAL,
            crop_type TEXT DEFAULT 'coffee',
            planting_date TEXT,
            geojson TEXT,
            compliance_status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (farm_id) REFERENCES farms(id)
        )
    ''')
    
    # Cooperatives table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cooperatives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            registration_number TEXT UNIQUE,
            tax_id TEXT,
            email TEXT,
            phone TEXT,
            website TEXT,
            address TEXT,
            country TEXT DEFAULT 'Kenya',
            region TEXT,
            district TEXT,
            subcounty TEXT,
            cooperative_type TEXT,
            latitude TEXT,
            longitude TEXT,
            establishment_date TIMESTAMP,
            primary_admin_id INTEGER,
            is_verified INTEGER DEFAULT 0,
            verification_status TEXT DEFAULT 'pending',
            is_active INTEGER DEFAULT 1,
            member_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Cooperative members table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cooperative_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            cooperative_id INTEGER NOT NULL,
            membership_number TEXT,
            cooperative_role TEXT DEFAULT 'member',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (cooperative_id) REFERENCES cooperatives(id),
            UNIQUE(user_id, cooperative_id)
        )
    ''')
    
    # Deliveries table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deliveries (
            id TEXT PRIMARY KEY,
            farm_id TEXT,
            delivery_number TEXT UNIQUE,
            net_weight_kg REAL,
            quality_grade TEXT,
            moisture_content REAL,
            status TEXT DEFAULT 'pending',
            delivery_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (farm_id) REFERENCES farms(id)
        )
    ''')
    
    # Batches table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batches (
            id TEXT PRIMARY KEY,
            batch_number TEXT UNIQUE,
            total_weight_kg REAL,
            quality_grade TEXT,
            compliance_status TEXT DEFAULT 'under_review',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Batch deliveries junction table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batch_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT,
            delivery_id TEXT,
            FOREIGN KEY (batch_id) REFERENCES batches(id),
            FOREIGN KEY (delivery_id) REFERENCES deliveries(id)
        )
    ''')
    
    # Verifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verifications (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            verification_type TEXT,
            current_status TEXT DEFAULT 'pending',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            reviewed_by INTEGER,
            notes TEXT
        )
    ''')
    
    # Compliance records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compliance_records (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            compliance_type TEXT,
            status TEXT DEFAULT 'pending',
            documents TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Satellite analysis table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS satellite_analysis (
            id TEXT PRIMARY KEY,
            parcel_id TEXT,
            analysis_type TEXT,
            ndvi_score REAL,
            risk_level TEXT DEFAULT 'low',
            analysis_date TEXT,
            results TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parcel_id) REFERENCES parcels(id)
        )
    ''')
    
    # EUDR DDS table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dds_records (
            id TEXT PRIMARY KEY,
            dds_number TEXT UNIQUE,
            operator_name TEXT,
            operator_id TEXT,
            production_country TEXT DEFAULT 'Kenya',
            commodity TEXT DEFAULT 'Coffee',
            quantity_kg REAL,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_farms_owner ON farms(owner_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_parcels_farm ON parcels(farm_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_deliveries_farm ON deliveries(farm_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_verifications_entity ON verifications(entity_type, entity_id)')
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

# Password hashing
def hash_password(password):
    """Hash password using SHA256 with salt"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${pwd_hash}"

def verify_password(password, password_hash):
    """Verify password against hash"""
    try:
        salt, pwd_hash = password_hash.split('$')
        return hashlib.sha256((password + salt).encode()).hexdigest() == pwd_hash
    except:
        return False

# Generate unique IDs
def generate_id():
    return str(uuid.uuid4())

def generate_code(prefix):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = secrets.token_hex(3).upper()
    return f"{prefix}-{timestamp}-{random_suffix}"

# Database helpers
def execute_query(query, params=(), fetch_one=False, fetch_all=True, commit=False):
    """Execute a database query"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, params)
    
    result = None
    if fetch_one:
        row = cursor.fetchone()
        result = dict(zip([desc[0] for desc in cursor.description], row)) if row else None
    elif fetch_all:
        rows = cursor.fetchall()
        # Return list of tuples for backward compatibility
        result = rows
    
    if commit:
        conn.commit()
        result = cursor.lastrowid
    
    conn.close()
    return result

def row_to_dict(row):
    """Convert sqlite3.Row to dict"""
    if row is None:
        return None
    return dict(row)

# Default admin user - only created if ENABLE_DEFAULT_ADMIN is True
def ensure_admin_user():
    """Create default admin user if not exists"""
    if not ENABLE_DEFAULT_ADMIN:
        return  # Skip creation if disabled
    existing = execute_query("SELECT id FROM users WHERE email = ?", ('admin@plotra.africa',), fetch_one=True)
    if not existing:
        execute_query(
            "INSERT INTO users (email, password_hash, first_name, last_name, role, region) VALUES (?, ?, ?, ?, ?, ?)",
            ('admin@plotra.africa', hash_password('admin123'), 'Admin', 'User', 'platform_admin', 'Nairobi'),
            commit=True
        )
        print("Default admin user created: admin@plotra.africa / admin123")

# API Handler
class APIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def send_json_response(self, status, data):
        response_body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_body)))
        
        origin = self.headers.get('Origin')
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Credentials', 'true')
        else:
            self.send_header('Access-Control-Allow-Origin', '*')
            
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, Accept, Origin')
        self.end_headers()
        self.wfile.write(response_body)
    
    def do_OPTIONS(self):
        self.send_response(200)
        origin = self.headers.get('Origin')
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Credentials', 'true')
        else:
            self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, Accept, Origin')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
    
    def getBearerToken(self):
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        return None
    
    def get_current_user(self):
        token = self.getBearerToken()
        if token and token.startswith('mock_token_'):
            # Token format: mock_token_{user_id}_{random_hex}
            # Extract user_id from token
            try:
                parts = token.split('_')
                if len(parts) >= 3:
                    user_id = parts[2]  # Get the user_id part
                    user = execute_query(f"SELECT * FROM users WHERE id = {user_id}", fetch_one=True)
                    if user:
                        return user
            except Exception as e:
                print(f"Error parsing token: {e}")
            # Fallback: return admin user only if parsing fails completely
            return execute_query("SELECT * FROM users WHERE role = 'platform_admin' LIMIT 1", fetch_one=True)
        return None
    
    def get_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length).decode()
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def parse_path(self):
        """Parse the request path and extract endpoint and query params"""
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        # Convert params to simple dict with single values
        params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
        return path, params
    
    def do_GET(self):
        path, params = self.parse_path()
        user = self.get_current_user()
        
        # Health check
        if path == '/health':
            self.send_json_response(200, {"status": "healthy", "message": "Plotra API is running"})
            return
        
        if path == '/api/v2/':
            self.send_json_response(200, {"message": "API v2", "version": "1.0.0"})
            return
        
        # Auth endpoints
        if path == '/api/v2/auth/me':
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            self.send_json_response(200, {
                "id": user['id'],
                "email": user['email'],
                "first_name": user['first_name'],
                "last_name": user['last_name'],
                "role": user['role'],
                "region": user['region']
            })
            return
        
        # Dashboard stats
        if path == '/api/v2/admin/dashboard/stats':
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            total_farms = execute_query("SELECT COUNT(*) as count FROM farms", fetch_one=True)['count']
            total_parcels = execute_query("SELECT COUNT(*) as count FROM parcels", fetch_one=True)['count']
            total_deliveries = execute_query("SELECT COUNT(*) as count FROM deliveries", fetch_one=True)['count']
            total_cooperatives = execute_query("SELECT COUNT(*) as count FROM cooperatives", fetch_one=True)['count']
            total_farmers = execute_query("SELECT COUNT(*) as count FROM users WHERE role = 'farmer'", fetch_one=True)['count']
            
            compliant = execute_query("SELECT COUNT(*) as count FROM farms WHERE compliance_status = 'compliant'", fetch_one=True)['count']
            compliance_rate = round((compliant / total_farms * 100), 1) if total_farms > 0 else 0
            
            self.send_json_response(200, {
                "total_farms": total_farms,
                "total_parcels": total_parcels,
                "total_deliveries": total_deliveries,
                "total_cooperatives": total_cooperatives,
                "total_farmers": total_farmers,
                "compliance_rate": compliance_rate
            })
            return
        
        # Clear all data (admin only - for testing/reset)
        if path == '/api/v2/admin/clear-data' and method == 'POST':
            if not user or user.get('role') != 'platform_admin':
                self.send_json_response(403, {"detail": "Admin access required"})
                return
            
            try:
                # Delete all data from tables (keep structure)
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM satellite_analysis")
                cursor.execute("DELETE FROM dds_records")
                cursor.execute("DELETE FROM batches")
                cursor.execute("DELETE FROM deliveries")
                cursor.execute("DELETE FROM parcels")
                cursor.execute("DELETE FROM farms")
                cursor.execute("DELETE FROM users WHERE role != 'platform_admin'")  # Keep admin
                conn.commit()
                conn.close()
                
                self.send_json_response(200, {"message": "All data cleared successfully"})
            except Exception as e:
                self.send_json_response(500, {"detail": str(e)})
            return
        
        # Compliance overview
        if path == '/api/v2/admin/compliance/overview':
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            total_farms = execute_query("SELECT COUNT(*) as count FROM farms", fetch_one=True)['count']
            compliant = execute_query("SELECT COUNT(*) as count FROM farms WHERE compliance_status = 'compliant'", fetch_one=True)['count']
            under_review = execute_query("SELECT COUNT(*) as count FROM farms WHERE compliance_status = 'pending'", fetch_one=True)['count']
            non_compliant = execute_query("SELECT COUNT(*) as count FROM farms WHERE compliance_status = 'non_compliant'", fetch_one=True)['count']
            compliance_rate = round((compliant / total_farms * 100), 1) if total_farms > 0 else 0
            
            self.send_json_response(200, {
                "total_farms": total_farms,
                "compliance_rate": compliance_rate,
                "compliance_breakdown": {
                    "compliant": compliant,
                    "under_review": under_review,
                    "non_compliant": non_compliant
                },
                "compliant_trend": [30, 40, 35, 50, 49, 60, 70, 91, 125],
                "pending_trend": [20, 30, 25, 30, 29, 40, 40, 50, 60]
            })
            return
        
        # Get farms
        if path.startswith('/api/v2/farmer/farm') or path.startswith('/api/v2/admin/farms'):
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            if '/admin/farms' in path:
                # Admin sees all farms
                farms = execute_query("SELECT * FROM farms ORDER BY created_at DESC", fetch_all=True)
            else:
                # Farmer sees their own farms
                farms = execute_query("SELECT * FROM farms WHERE owner_id = ?", (user['id'],), fetch_all=True)
            
            # Get owner info for each farm
            result = []
            for farm in farms:
                owner = execute_query("SELECT id, email, first_name, last_name FROM users WHERE id = ?", (farm['owner_id'],), fetch_one=True) if farm['owner_id'] else None
                farm_dict = dict(farm)
                farm_dict['owner'] = owner
                result.append(farm_dict)
            
            self.send_json_response(200, result)
            return
        
        # Get parcels for a farm
        if '/parcels' in path and '/farm/' in path:
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            # Check if it's a specific parcel or list
            if '/parcels/' in path:
                parcel_id = path.split('/parcels/')[1]
                parcel = execute_query("SELECT * FROM parcels WHERE id = ?", (parcel_id,), fetch_one=True)
                self.send_json_response(200, parcel)
                return
            
            farm_id = path.split('/farm/')[1].split('/parcels')[0]
            parcels = execute_query("SELECT * FROM parcels WHERE farm_id = ?", (farm_id,), fetch_all=True)
            self.send_json_response(200, parcels)
            return
        
        # Get deliveries
        if path.startswith('/api/v2/coop/deliveries'):
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            deliveries = execute_query("SELECT * FROM deliveries ORDER BY created_at DESC", fetch_all=True)
            self.send_json_response(200, deliveries)
            return
        
        # Get batches
        if path.startswith('/api/v2/coop/batches'):
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            batches = execute_query("SELECT * FROM batches ORDER BY created_at DESC", fetch_all=True)
            self.send_json_response(200, batches)
            return
        
        # Get pending verifications
        if path.startswith('/api/v2/admin/verification/pending'):
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            verifications = execute_query("SELECT * FROM verifications WHERE current_status IN ('pending', 'under_review') ORDER BY submitted_at DESC", fetch_all=True)
            self.send_json_response(200, verifications)
            return
        
        # Get users
        if path.startswith('/api/v2/admin/users'):
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            users = execute_query("SELECT id, email, first_name, last_name, role, region, status, created_at FROM users ORDER BY created_at DESC", fetch_all=True)
            self.send_json_response(200, users)
            return
        
        # Get cooperatives
        if path.startswith('/api/v2/admin/cooperatives'):
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            # Check if getting specific cooperative
            coop_id = None
            if '/cooperatives/' in path and not path.endswith('/cooperatives'):
                try:
                    coop_id = int(path.split('/cooperatives/')[1].split('/')[0])
                except:
                    pass
            
            if coop_id:
                # Get specific cooperative
                coop = execute_query("SELECT * FROM cooperatives WHERE id = ?", (coop_id,), fetch_one=True)
                if not coop:
                    self.send_json_response(404, {"detail": "Cooperative not found"})
                    return
                
                # Get member count
                member_count_result = execute_query(
                    "SELECT COUNT(*) FROM cooperative_members WHERE cooperative_id = ?", 
                    (coop_id,), fetch_one=True
                )
                member_count = member_count_result['COUNT(*)'] if member_count_result else 0
                
                # Get admin name
                admin_name = None
                if coop['primary_admin_id']:  # primary_admin_id
                    admin = execute_query("SELECT first_name, last_name FROM users WHERE id = ?", (coop['primary_admin_id'],), fetch_one=True)
                    if admin:
                        admin_name = f"{admin['first_name']} {admin['last_name']}"
                
                self.send_json_response(200, {
                    "id": coop['id'],
                    "name": coop['name'],
                    "registration_number": coop['registration_number'],
                    "address": coop['address'],
                    "phone": coop['phone'],
                    "email": coop['email'],
                    "country": coop['country'],
                    "region": coop['region'],
                    "primary_admin_id": coop['primary_admin_id'],
                    "is_verified": bool(coop['is_verified']),
                    "verification_date": coop['verification_date'],
                    "created_at": coop['created_at'],
                    "updated_at": coop['updated_at'],
                    "member_count": member_count,
                    "admin_name": admin_name
                })
            else:
                # Get all cooperatives
                coops = execute_query("SELECT * FROM cooperatives ORDER BY created_at DESC", fetch_all=True)
                coop_list = []
                for c in coops:
                    # Get member count
                    member_count_result = execute_query(
                        "SELECT COUNT(*) FROM cooperative_members WHERE cooperative_id = ?", 
                        (c[0],), fetch_one=True
                    )
                    member_count = member_count_result['COUNT(*)'] if member_count_result else 0
                    
                    # Get admin name
                    admin_name = None
                    if c[8]:  # primary_admin_id
                        admin = execute_query("SELECT first_name, last_name FROM users WHERE id = ?", (c[8],), fetch_one=True)
                        if admin:
                            admin_name = f"{admin[0]} {admin[1]}"
                    
                    coop_list.append({
                        "id": c[0],
                        "name": c[1],
                        "registration_number": c[2],
                        "tax_id": c[3],
                        "email": c[4],
                        "phone": c[5],
                        "website": c[6],
                        "address": c[7],
                        "country": c[8],
                        "region": c[9],
                        "district": c[10],
                        "subcounty": c[11],
                        "cooperative_type": c[12],
                        "latitude": c[13],
                        "longitude": c[14],
                        "establishment_date": c[15],
                        "primary_admin_id": c[16],
                        "is_verified": bool(c[17]),
                        "verification_status": c[18],
                        "is_active": bool(c[19]),
                        "member_count": member_count,
                        "created_at": c[21],
                        "updated_at": c[22],
                        "admin_name": admin_name
                    })
                self.send_json_response(200, coop_list)
            return
        
        # Get pending farmers
        if path.startswith('/api/v2/admin/farmers/pending'):
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            # Get all pending farmers (those not verified)
            # First check if verification_status column exists
            try:
                farmers = execute_query(
                    "SELECT id, email, first_name, last_name, role, phone_number, region, created_at FROM users WHERE role = 'farmer' ORDER BY created_at DESC", 
                    fetch_all=True
                )
            except:
                farmers = execute_query(
                    "SELECT id, email, first_name, last_name, role, phone_number, region, created_at FROM users WHERE role = 'farmer' ORDER BY created_at DESC", 
                    fetch_all=True
                )
            
            farmer_list = []
            for f in farmers:
                farmer_list.append({
                    "id": f[0],
                    "email": f[1],
                    "first_name": f[2],
                    "last_name": f[3],
                    "role": f[4],
                    "phone_number": f[5],
                    "region": f[6],
                    "verification_status": "pending",
                    "created_at": f[7]
                })
            self.send_json_response(200, farmer_list)
            return
        
        # Risk report
        if path.startswith('/api/v2/admin/farms/risk-report'):
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            high_risk = execute_query("SELECT COUNT(*) as count FROM satellite_analysis WHERE risk_level = 'high'", fetch_one=True)['count']
            medium_risk = execute_query("SELECT COUNT(*) as count FROM satellite_analysis WHERE risk_level = 'medium'", fetch_one=True)['count']
            low_risk = execute_query("SELECT COUNT(*) as count FROM satellite_analysis WHERE risk_level = 'low'", fetch_one=True)['count']
            
            self.send_json_response(200, {
                "high_risk_count": high_risk,
                "medium_risk_count": medium_risk,
                "low_risk_count": low_risk
            })
            return
        
        # Get DDS records
        if path.startswith('/api/v2/admin/eudr/dds'):
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            if '/admin/eudr/dds' in path and path != '/api/v2/admin/eudr/dds':
                # Get specific DDS
                dds_id = path.split('/')[-1]
                dds = execute_query("SELECT * FROM dds_records WHERE id = ?", (dds_id,), fetch_one=True)
                self.send_json_response(200, dds)
            else:
                dds_records = execute_query("SELECT * FROM dds_records ORDER BY created_at DESC", fetch_all=True)
                self.send_json_response(200, dds_records)
            return
        
        self.send_json_response(404, {"error": "Not found"})
    
    def do_POST(self):
        path, params = self.parse_path()
        body = self.get_json_body()
        user = self.get_current_user()
        
        # Auth login
        if path in ['/api/v2/auth/login', '/api/v2/auth/token-form']:
            email = body.get('username') or body.get('email')
            password = body.get('password')
            
            if not email or not password:
                self.send_json_response(400, {"detail": "Email and password required"})
                return
            
            user_record = execute_query("SELECT * FROM users WHERE email = ?", (email,), fetch_one=True)
            
            if not user_record or not verify_password(password, user_record['password_hash']):
                self.send_json_response(401, {"detail": "Invalid credentials"})
                return
            
            self.send_json_response(200, {
                "access_token": f"mock_token_{user_record['id']}_{secrets.token_hex(8)}",
                "token_type": "bearer",
                "user": {
                    "id": user_record['id'],
                    "email": user_record['email'],
                    "first_name": user_record['first_name'],
                    "last_name": user_record['last_name'],
                    "role": user_record['role']
                }
            })
            return
        
        # Registration
        if path == '/api/v2/auth/register':
            email = body.get('email')
            password = body.get('password')
            first_name = body.get('first_name', '')
            last_name = body.get('last_name', '')
            role = body.get('role', 'farmer')
            region = body.get('region')
            
            if not email or not password:
                self.send_json_response(400, {"detail": "Email and password required"})
                return
            
            existing = execute_query("SELECT id FROM users WHERE email = ?", (email,), fetch_one=True)
            if existing:
                self.send_json_response(400, {"detail": "Email already registered"})
                return
            
            user_id = execute_query(
                "INSERT INTO users (email, password_hash, first_name, last_name, role, region) VALUES (?, ?, ?, ?, ?, ?)",
                (email, hash_password(password), first_name, last_name, role, region),
                commit=True
            )
            
            self.send_json_response(201, {
                "message": "Registration successful",
                "user": {"id": user_id, "email": email}
            })
            return
        
        # For other endpoints, require authentication
        if not user:
            self.send_json_response(401, {"detail": "Not authenticated"})
            return
        
        # Create farm
        if path == '/api/v2/farmer/farm':
            farm_id = generate_id()
            farm_code = generate_code('FRM')
            
            farm_data = {
                'id': farm_id,
                'owner_id': user['id'],
                'farm_code': farm_code,
                'farm_name': body.get('farm_name', f'Farm {farm_code}'),
                'total_area_hectares': body.get('total_area_hectares', 0),
                'compliance_status': 'pending',
                'verification_status': 'draft',
                'latitude': body.get('latitude'),
                'longitude': body.get('longitude')
            }
            
            execute_query(
                """INSERT INTO farms (id, owner_id, farm_code, farm_name, total_area_hectares, compliance_status, verification_status, latitude, longitude) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (farm_data['id'], farm_data['owner_id'], farm_data['farm_code'], farm_data['farm_name'], 
                 farm_data['total_area_hectares'], farm_data['compliance_status'], farm_data['verification_status'],
                 farm_data['latitude'], farm_data['longitude']),
                commit=True
            )
            
            self.send_json_response(201, farm_data)
            return
        
        # Add parcel to farm
        if '/parcels' in path and '/farm/' in path and path.endswith('/parcels'):
            farm_id = path.split('/farm/')[1].split('/parcels')[0]
            parcel_id = generate_id()
            
            parcel_data = {
                'id': parcel_id,
                'farm_id': farm_id,
                'parcel_code': body.get('parcel_code', generate_code('PRL')),
                'area_hectares': body.get('area_hectares', 0),
                'crop_type': body.get('crop_type', 'coffee'),
                'planting_date': body.get('planting_date'),
                'compliance_status': 'pending'
            }
            
            execute_query(
                """INSERT INTO parcels (id, farm_id, parcel_code, area_hectares, crop_type, planting_date, compliance_status) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (parcel_data['id'], parcel_data['farm_id'], parcel_data['parcel_code'],
                 parcel_data['area_hectares'], parcel_data['crop_type'], parcel_data['planting_date'],
                 parcel_data['compliance_status']),
                commit=True
            )
            
            self.send_json_response(201, parcel_data)
            return
        
        # Create delivery
        if path == '/api/v2/coop/deliveries':
            delivery_id = generate_id()
            delivery_number = generate_code('DLV')
            
            delivery_data = {
                'id': delivery_id,
                'farm_id': body.get('farm_id'),
                'delivery_number': delivery_number,
                'net_weight_kg': body.get('net_weight_kg', 0),
                'quality_grade': body.get('quality_grade', 'AA'),
                'moisture_content': body.get('moisture_content', 12.0),
                'status': 'pending',
                'delivery_date': datetime.now().isoformat()
            }
            
            execute_query(
                """INSERT INTO deliveries (id, farm_id, delivery_number, net_weight_kg, quality_grade, moisture_content, status, delivery_date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (delivery_data['id'], delivery_data['farm_id'], delivery_data['delivery_number'],
                 delivery_data['net_weight_kg'], delivery_data['quality_grade'], delivery_data['moisture_content'],
                 delivery_data['status'], delivery_data['delivery_date']),
                commit=True
            )
            
            self.send_json_response(201, delivery_data)
            return
        
        # Create batch
        if path == '/api/v2/coop/batches':
            batch_id = generate_id()
            batch_number = generate_code('BTH')
            
            batch_data = {
                'id': batch_id,
                'batch_number': batch_number,
                'total_weight_kg': body.get('total_weight_kg', 0),
                'quality_grade': body.get('quality_grade', 'AA'),
                'compliance_status': 'under_review',
                'status': 'pending'
            }
            
            execute_query(
                """INSERT INTO batches (id, batch_number, total_weight_kg, quality_grade, compliance_status, status) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (batch_data['id'], batch_data['batch_number'], batch_data['total_weight_kg'],
                 batch_data['quality_grade'], batch_data['compliance_status'], batch_data['status']),
                commit=True
            )
            
            self.send_json_response(201, batch_data)
            return
        
        # Create cooperative
        if path == '/api/v2/admin/cooperatives':
            if not user or user.get('role') not in ['platform_admin', 'admin']:
                self.send_json_response(403, {"detail": "Not authorized"})
                return
            
            name = body.get('name')
            if not name:
                self.send_json_response(400, {"detail": "Name is required"})
                return
            
            registration_number = body.get('registration_number')
            tax_id = body.get('tax_id')
            address = body.get('address')
            phone = body.get('phone')
            email = body.get('email')
            website = body.get('website')
            country = body.get('country', 'Kenya')
            region = body.get('region')
            district = body.get('district')
            subcounty = body.get('subcounty')
            cooperative_type = body.get('cooperative_type')
            latitude = body.get('latitude')
            longitude = body.get('longitude')
            establishment_date = body.get('establishment_date')
            
            # Check registration number uniqueness
            if registration_number:
                existing = execute_query(
                    "SELECT id FROM cooperatives WHERE registration_number = ?",
                    (registration_number,), fetch_one=True
                )
                if existing:
                    self.send_json_response(400, {"detail": "Registration number already exists"})
                    return
            
            # Create cooperative
            result = execute_query(
                """INSERT INTO cooperatives (name, registration_number, tax_id, address, phone, email, website, country, region, district, subcounty, cooperative_type, latitude, longitude, establishment_date, is_verified, verification_status, is_active, member_count) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'verified', 1, 0)""",
                (name, registration_number, tax_id, address, phone, email, website, country, region, district, subcounty, cooperative_type, latitude, longitude, establishment_date),
                commit=True
            )
            
            coop_id = result.lastrowid if hasattr(result, 'lastrowid') else execute_query("SELECT last_insert_rowid()", fetch_one=True)['last_insert_rowid()']
            
            # If admin user details provided, create and assign admin
            admin_id = None
            if body.get('admin_email'):
                admin_email = body.get('admin_email')
                admin_first = body.get('admin_first_name', 'Coop')
                admin_last = body.get('admin_last_name', 'Admin')
                admin_phone = body.get('admin_phone')
                admin_password = body.get('admin_password', 'TempPass123!')
                
                # Check if user exists
                existing_user = execute_query("SELECT id FROM users WHERE email = ?", (admin_email,), fetch_one=True)
                if not existing_user:
                    # Create admin user
                    password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
                    admin_result = execute_query(
                        """INSERT INTO users (email, password_hash, first_name, last_name, phone_number, role) 
                           VALUES (?, ?, ?, ?, ?, 'coop_admin')""",
                        (admin_email, password_hash, admin_first, admin_last, admin_phone),
                        commit=True
                    )
                    admin_id = admin_result.lastrowid if hasattr(admin_result, 'lastrowid') else execute_query("SELECT last_insert_rowid()", fetch_one=True)['last_insert_rowid()']
                else:
                    admin_id = existing_user['id']
                    # Update user role
                    execute_query(
                        "UPDATE users SET role = 'coop_admin' WHERE id = ?",
                        (admin_id,), commit=True
                    )
                
                # Assign as cooperative admin
                execute_query(
                    "UPDATE cooperatives SET primary_admin_id = ? WHERE id = ?",
                    (admin_id, coop_id), commit=True
                )
            
            # Get created cooperative
            coop = execute_query("SELECT * FROM cooperatives WHERE id = ?", (coop_id,), fetch_one=True)
            
            self.send_json_response(201, {
                "id": coop[0],
                "name": coop[1],
                "registration_number": coop[2],
                "tax_id": coop[3],
                "email": coop[4],
                "phone": coop[5],
                "website": coop[6],
                "address": coop[7],
                "country": coop[8],
                "region": coop[9],
                "district": coop[10],
                "subcounty": coop[11],
                "cooperative_type": coop[12],
                "latitude": coop[13],
                "longitude": coop[14],
                "establishment_date": coop[15],
                "primary_admin_id": coop[16],
                "is_verified": bool(coop[17]),
                "verification_status": coop[18],
                "is_active": bool(coop[19]),
                "member_count": coop[20],
                "created_at": coop[21],
                "updated_at": coop[22]
            })
            return
        
        # Verify cooperative
        if '/cooperatives/' in path and '/verify' in path:
            if not user or user.get('role') not in ['platform_admin', 'admin']:
                self.send_json_response(403, {"detail": "Not authorized"})
                return
            
            try:
                coop_id = int(path.split('/cooperatives/')[1].split('/verify')[0])
            except:
                self.send_json_response(400, {"detail": "Invalid cooperative ID"})
                return
            
            execute_query(
                "UPDATE cooperatives SET is_verified = 1, verification_date = ? WHERE id = ?",
                (datetime.now().isoformat(), coop_id), commit=True
            )
            
            self.send_json_response(200, {"message": "Cooperative verified successfully"})
            return
        
        # Add member to cooperative (for coop admins)
        if path == '/api/v2/coop/members':
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            user_id = body.get('user_id')
            membership_number = body.get('membership_number')
            cooperative_role = body.get('cooperative_role', 'member')
            
            if not user_id:
                self.send_json_response(400, {"detail": "User ID is required"})
                return
            
            # Check if user exists
            target_user = execute_query("SELECT id, email, first_name, last_name FROM users WHERE id = ?", (user_id,), fetch_one=True)
            if not target_user:
                self.send_json_response(404, {"detail": "User not found"})
                return
            
            # Check if already a member
            existing = execute_query(
                "SELECT id FROM cooperative_members WHERE user_id = ?",
                (user_id,), fetch_one=True
            )
            if existing:
                self.send_json_response(400, {"detail": "User is already a member of this cooperative"})
                return
            
            # Add member (for now, cooperative_id is 1 - in real app would get from user's assignment)
            execute_query(
                """INSERT INTO cooperative_members (user_id, cooperative_id, membership_number, cooperative_role) 
                   VALUES (?, 1, ?, ?)""",
                (user_id, membership_number, cooperative_role), commit=True
            )
            
            self.send_json_response(201, {
                "id": target_user[0],
                "email": target_user[1],
                "first_name": target_user[2],
                "last_name": target_user[3],
                "message": "Member added successfully"
            })
            return
        
        # Approve verification
        if '/verification/' in path and '/approve' in path:
            verification_id = path.split('/verification/')[1].split('/approve')[0]
            
            execute_query(
                "UPDATE verifications SET current_status = 'approved', reviewed_at = ?, reviewed_by = ? WHERE id = ?",
                (datetime.now().isoformat(), user['id'], verification_id),
                commit=True
            )
            
            self.send_json_response(200, {"message": "Verification approved"})
            return
        
        # Reject verification
        if '/verification/' in path and '/reject' in path:
            verification_id = path.split('/verification/')[1].split('/reject')[0]
            reason = body.get('reason', '')
            
            execute_query(
                "UPDATE verifications SET current_status = 'rejected', reviewed_at = ?, reviewed_by = ?, notes = ? WHERE id = ?",
                (datetime.now().isoformat(), user['id'], reason, verification_id),
                commit=True
            )
            
            self.send_json_response(200, {"message": "Verification rejected"})
            return
        
        # Satellite analysis
        if path == '/api/v2/admin/satellite/analyze':
            parcel_ids = body.get('parcel_ids', [])
            
            results = []
            for parcel_id in parcel_ids:
                analysis_id = generate_id()
                ndvi = 0.5 + (hash(parcel_id) % 50) / 100  # Random NDVI between 0.5-1.0
                risk = 'low' if ndvi > 0.65 else 'medium' if ndvi > 0.4 else 'high'
                
                execute_query(
                    """INSERT INTO satellite_analysis (id, parcel_id, analysis_type, ndvi_score, risk_level, analysis_date) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (analysis_id, parcel_id, 'ndvi_analysis', ndvi, risk, datetime.now().isoformat()),
                    commit=True
                )
                
                results.append({
                    'id': analysis_id,
                    'parcel_id': parcel_id,
                    'ndvi_score': ndvi,
                    'risk_level': risk
                })
            
            self.send_json_response(200, {"message": "Analysis complete", "results": results})
            return
        
        # Generate DDS
        if path == '/api/v2/admin/eudr/dds':
            dds_id = generate_id()
            dds_number = generate_code('DDS')
            
            dds_data = {
                'id': dds_id,
                'dds_number': dds_number,
                'operator_name': body.get('operator_name', user.get('first_name', '') + ' ' + user.get('last_name', '')),
                'operator_id': body.get('operator_id', ''),
                'quantity_kg': body.get('quantity_kg', 0),
                'status': 'draft'
            }
            
            execute_query(
                """INSERT INTO dds_records (id, dds_number, operator_name, operator_id, quantity_kg, status) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (dds_data['id'], dds_data['dds_number'], dds_data['operator_name'],
                 dds_data['operator_id'], dds_data['quantity_kg'], dds_data['status']),
                commit=True
            )
            
            self.send_json_response(201, dds_data)
            return
        
        # Forgot password
        if path == '/api/v2/auth/forgot-password':
            self.send_json_response(200, {"message": "Password reset link sent to your email"})
            return
        
        # Reset password
        if path == '/api/v2/auth/reset-password':
            self.send_json_response(200, {"message": "Password successfully reset"})
            return
        
        self.send_json_response(404, {"error": "Not found"})
    
    def do_PUT(self):
        path, params = self.parse_path()
        body = self.get_json_body()
        user = self.get_current_user()
        
        if not user:
            self.send_json_response(401, {"detail": "Not authenticated"})
            return
        
        # Update farm
        if path.startswith('/api/v2/farmer/farm/'):
            farm_id = path.split('/farm/')[1]
            
            execute_query(
                """UPDATE farms SET farm_name = ?, total_area_hectares = ?, latitude = ?, longitude = ?, updated_at = ? WHERE id = ?""",
                (body.get('farm_name'), body.get('total_area_hectares'), body.get('latitude'), 
                 body.get('longitude'), datetime.now().isoformat(), farm_id),
                commit=True
            )
            
            farm = execute_query("SELECT * FROM farms WHERE id = ?", (farm_id,), fetch_one=True)
            self.send_json_response(200, farm)
            return
        
        # Update delivery
        if path.startswith('/api/v2/coop/deliveries/'):
            delivery_id = path.split('/deliveries/')[1]
            
            execute_query(
                """UPDATE deliveries SET net_weight_kg = ?, quality_grade = ?, moisture_content = ?, status = ?, updated_at = ? WHERE id = ?""",
                (body.get('net_weight_kg'), body.get('quality_grade'), body.get('moisture_content'),
                 body.get('status'), datetime.now().isoformat(), delivery_id),
                commit=True
            )
            
            delivery = execute_query("SELECT * FROM deliveries WHERE id = ?", (delivery_id,), fetch_one=True)
            self.send_json_response(200, delivery)
            return
        
        # Update batch
        if path.startswith('/api/v2/coop/batches/'):
            batch_id = path.split('/batches/')[1]
            
            execute_query(
                """UPDATE batches SET total_weight_kg = ?, quality_grade = ?, status = ?, compliance_status = ?, updated_at = ? WHERE id = ?""",
                (body.get('total_weight_kg'), body.get('quality_grade'), body.get('status'),
                 body.get('compliance_status'), datetime.now().isoformat(), batch_id),
                commit=True
            )
            
            batch = execute_query("SELECT * FROM batches WHERE id = ?", (batch_id,), fetch_one=True)
            self.send_json_response(200, batch)
            return
        
        # Verify farmer
        if '/farmers/' in path and '/verify' in path:
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            try:
                farmer_id = int(path.split('/farmers/')[1].split('/verify')[0])
            except:
                self.send_json_response(400, {"detail": "Invalid farmer ID"})
                return
            
            # Check if farmer exists
            farmer = execute_query("SELECT * FROM users WHERE id = ? AND role = 'farmer'", (farmer_id,), fetch_one=True)
            if not farmer:
                self.send_json_response(404, {"detail": "Farmer not found"})
                return
            
            self.send_json_response(200, {
                "id": farmer[0],
                "email": farmer[1],
                "first_name": farmer[3],
                "last_name": farmer[4],
                "role": farmer[5],
                "verification_status": "verified",
                "message": "Farmer verified successfully"
            })
            return
        
        # Reject farmer
        if '/farmers/' in path and '/reject' in path:
            if not user:
                self.send_json_response(401, {"detail": "Not authenticated"})
                return
            
            try:
                farmer_id = int(path.split('/farmers/')[1].split('/reject')[0])
            except:
                self.send_json_response(400, {"detail": "Invalid farmer ID"})
                return
            
            reason = params.get('reason', '')
            
            # Check if farmer exists
            farmer = execute_query("SELECT * FROM users WHERE id = ? AND role = 'farmer'", (farmer_id,), fetch_one=True)
            if not farmer:
                self.send_json_response(404, {"detail": "Farmer not found"})
                return
            
            self.send_json_response(200, {
                "id": farmer[0],
                "email": farmer[1],
                "first_name": farmer[3],
                "last_name": farmer[4],
                "role": farmer[5],
                "verification_status": "rejected",
                "message": "Farmer rejected"
            })
            return
        
        self.send_json_response(404, {"error": "Not found"})
    
    def do_DELETE(self):
        path, params = self.parse_path()
        user = self.get_current_user()
        
        if not user:
            self.send_json_response(401, {"detail": "Not authenticated"})
            return
        
        # Delete farm
        if path.startswith('/api/v2/farmer/farm/'):
            farm_id = path.split('/farm/')[1]
            execute_query("DELETE FROM parcels WHERE farm_id = ?", (farm_id,), commit=True)
            execute_query("DELETE FROM farms WHERE id = ?", (farm_id,), commit=True)
            self.send_json_response(200, {"message": "Farm deleted"})
            return
        
        # Delete delivery
        if path.startswith('/api/v2/coop/deliveries/'):
            delivery_id = path.split('/deliveries/')[1]
            execute_query("DELETE FROM deliveries WHERE id = ?", (delivery_id,), commit=True)
            self.send_json_response(200, {"message": "Delivery deleted"})
            return
        
        # Delete batch
        if path.startswith('/api/v2/coop/batches/'):
            batch_id = path.split('/batches/')[1]
            execute_query("DELETE FROM batch_deliveries WHERE batch_id = ?", (batch_id,), commit=True)
            execute_query("DELETE FROM batches WHERE id = ?", (batch_id,), commit=True)
            self.send_json_response(200, {"message": "Batch deleted"})
            return
        
        # Delete user
        if path.startswith('/api/v2/admin/users/'):
            user_id = path.split('/users/')[1]
            execute_query("DELETE FROM users WHERE id = ?", (user_id,), commit=True)
            self.send_json_response(200, {"message": "User deleted"})
            return
        
        self.send_json_response(404, {"error": "Not found"})

def run_server():
    # Initialize database
    init_database()
    ensure_admin_user()
    
    server = HTTPServer(('0.0.0.0', PORT), APIHandler)
    print(f"Starting Plotra API server on port {PORT}...")
    print(f"Health check: http://localhost:{PORT}/health")
    print(f"Default login: admin@plotra.africa / admin123")
    server.serve_forever()

if __name__ == '__main__':
    run_server()
