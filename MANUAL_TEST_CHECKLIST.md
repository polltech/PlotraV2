# 🧪 MANUAL TEST EXECUTION CHECKLIST
## Complete verification of GPS Polygon Capture & DDS Generation

---

## BEFORE YOU START

**Ensure:**
- [x] Docker Desktop running
- [x] All 3 containers UP & HEALTHY (`docker compose ps`)
- [x] Backend port 8000 accessible
- [x] Dashboard port 8080 accessible
- [x] No errors in `docker logs plotra-backend`

---

## TEST 1: Farmer Registration & Login

**Steps:**
1. Open browser → http://localhost:8080
2. Click **Sign Up** (or Register)
3. Fill:
   - Email: `test.farmer@example.com`
   - Password: `TestPass123!`
   - First/Last Name: `Test Farmer`
   - Phone: `+254712345678`
   - ID Number: `98765432`
   - Gender: Male/Female
   - Cooperative Membership: (leave blank or select if any)
   - Check consent box
4. Click **Create Account**
5. Login with same credentials

**Expected:**
- ✅ No validation errors
- ✅ Redirect to dashboard
- ✅ Sidebar shows "My Farms", "My Batches", etc.

---

## TEST 2: Create Farm with GPS Polygon Capture

**Steps:**
1. Dashboard → **My Farms** (sidebar)
2. Click **Add Farm** button (top right)
3. **Tab 1 – Farmer Identity:**
   - Fill all required fields (should be pre-filled from registration)
   - Check all checkboxes
   - Click **Next Step**
4. **Tab 2 – Farm Basics:**
   - Farm Name: `Test Farm 1`
   - Location: `Kiambu County` (or any)
   - Approx Size: `2.5` (ha)
   - Land Ownership: `Freehold`
   - Farming Method: `Organic`
   - Coffee Variety: `SL28, SL34` (comma-separated)
   - Expected Annual Yield: `1500` (bags)
   - Click **Next Step**
5. **Tab 3 – GPS Polygon Capture:**
   - See map with "Click Start Capture to begin"
   - Click **Start Capture**
   - Browser asks GPS permission → **Allow**
   - Wait for GPS fix (accuracy < 20m ideal)
   - Click **Add Point** at each corner (minimum 4 points)
   - Observe:
     - ✅ Polygon draws on map connecting points
     - ✅ "Points: X" counter increments
     - ✅ "Area: Y.YY ha" updates automatically
   - Click **Finish**
   - Verify **captureInstructions** says: *"Polygon captured with X points"*
6. **Tab 4 – Additional Info** (optional, skip)
7. **Tab 5 – Review & Submit:**
   - Verify summary shows farm name, area, point count
   - Click **Submit Farm**

**Expected:**
- ✅ Success toast: "Farm created successfully"
- ✅ Modal closes
- ✅ Farm appears in **My Farms** table with:
  - Farm Name: `Test Farm 1`
  - Area: `2.50 ha` (or captured area)
  - Status: `PENDING` (not `DRAFT` anymore)
  - Actions: **View**, **Delete**

**Verify in backend logs:**
```bash
docker logs plotra-backend --tail 20
# Should show POST /farmer/farm → 201 Created
```

---

## TEST 3: Verify Farm Boundary in Details

**Steps:**
1. In **My Farms** table, click **View** for `Test Farm 1`
2. Modal opens → **Farm Details**
3. Check:
   - ✅ Farm information correct
   - ✅ Map displays captured polygon (blue shape)
   - ✅ Area matches captured value
   - ✅ Status badge: `PENDING`

**Optional:**
- Click **Capture Boundary** → opens Farm Capture modal
- Verify you can recapture (remove old, draw new)

**Expected:**
- ✅ Boundary visible
- ✅ Coordinates stored in DB

---

## TEST 4: Admin DDS Generation

**Prerequisites:** Have at least 1 farm with GPS polygon (from Test 2)

1. Logout (top right)
2. Login as **admin** (credentials set in `.env` or first-user auto-admin)
   - Email: `admin@plotra.com` (check your seed data)
   - Password: (check seed or `.env`)
3. Sidebar → **Verification EUDR**
4. Verify page loads with **DDS table** (empty initially)
5. Click **Generate DDS** (top right)

**Form Fill:**
- **Operator Information:**
  - Operator Name: `Test Coffee Exporters Ltd`
  - Operator ID: `KE123456789`
  - Contact Name: `Jane Admin`
  - Contact Email: `admin@testcoffee.co.ke`
  - Contact Address: `123 Coffee Road, Nairobi, Kenya`
- **Commodity Information:**
  - Commodity Type: `Coffee` ✓ (default)
  - HS Code: `090111` ✓ (default)
  - Production Country: `Kenya` ✓ (default)
  - Quantity: `5000`
  - Unit: `kg`
- **Supplier Information:** (optional)
- **First Placement:**
  - Country: `Germany`
  - Date: (pick any future or past date)
- **Associated Farms:**
  - Hold **Ctrl** and select `Test Farm 1` from dropdown

6. Click **Generate DDS**

**Expected:**
- ✅ Green toast: "DDS generated successfully"
- ✅ Modal closes
- ✅ DDS table now shows 1 row:
  - DDS Number: `DDS-20250423-XXXXXX` (format: DDS-YYYYMMDD-HEX8)
  - Operator: `Test Coffee Exporters Ltd`
  - Commodity: `Coffee`
  - Quantity: `5000 kg`
  - Risk Level: `LOW` (green badge)
  - Status: `draft` (blue/grey badge)
  - Date: today's date
  - Actions: **Export** button

**If dropdown empty:** Farm doesn't have centroid → check admin get_farms fix.

---

## TEST 5: View DDS Details

**Steps:**
1. In DDS table, click the **DDS Number** link (first column)
2. Modal opens: **DDS Details**

**Verify content displayed:**
- ✅ DDS Number, Version
- ✅ Operator name + ID
- ✅ Contact info (name, email, address)
- ✅ Commodity: Coffee, HS 090111, Kenya, 5000 kg
- ✅ Supplier (if provided)
- ✅ First Placement country + date
- ✅ Risk Level badge: `LOW`
- ✅ Submission Status: `draft`
- ✅ Created date
- ✅ **Farm Coordinates section** → lists farm(s) with lat/lon
- ✅ **Mitigation Measures** → list of measures (should have ≥3 items)
- ✅ **Evidence References** → list of evidence strings

**Click Export XML:**
- ✅ File downloads as `dds_<numeric_id>.xml`
- ✅ Open file → is valid XML with `<DueDiligenceStatement>` root

**Sample check:**
```xml
<Header>
  <DDSNumber>DDS-20250423-ABC12345</DDSNumber>
  <OperatorName>Test Coffee Exporters Ltd</OperatorName>
  ...
</Header>
<Commodity>
  <Type>Coffee</Type>
  <CountryOfOrigin>Kenya</CountryOfOrigin>
  ...
</Commodity>
<RiskAssessment>
  <OverallRisk>low</OverallRisk>
</RiskAssessment>
<Farms>
  <Farm>
    <FarmID>...</FarmID>
    <Coordinates>
      <Latitude>-1.234567</Latitude>
      <Longitude>36.890123</Longitude>
    </Coordinates>
  </Farm>
</Farms>
```

---

## TEST 6: API Debug (Optional)

**Health:**
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

**Swagger UI:**
- Visit http://localhost:8000/docs
- Expand any endpoint (e.g., `GET /api/v2/farmer/farm`)
- Click **Try it out** → Execute
- Should return JSON (401 if no auth, or 200 with auth)

**DDS List API (as admin):**
```bash
# First get token via login endpoint
TOKEN=$(curl -s -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@plotra.com","password":"yourpass"}' | jq -r .access_token)

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v2/admin/eudr/dds | jq
```

---

## ✅ TEST RESULT CHECKLIST

| Test | Expected | Pass/Fail |
|------|----------|-----------|
| Farmer registration/login | No errors, dashboard loads | [ ] |
| Add Farm modal opens | Map loads, steps visible | [ ] |
| GPS Start Capture | GPS permission prompt | [ ] |
| Add Point (4+) | Points count increases, polygon draws | [ ] |
| Finish Capture | Area calculated, instructions updated | [ ] |
| Submit Farm | Success toast, farm appears in list | [ ] |
| View Farm details | Polygon visible on map | [ ] |
| Admin login | Access Verification EUDR page | [ ] |
| Generate DDS form loads | Farm dropdown populated | [ ] |
| Submit DDS | Success, appears in table | [ ] |
| DDS Number format | `DDS-YYYYMMDD-HEX8` | [ ] |
| Risk Level | `LOW` (Kenya standard risk) | [ ] |
| View DDS modal | All fields populated | [ ] |
| Export DDS | XML downloads and is well-formed | [ ] |
| No backend errors | `docker logs` clean | [ ] |
| No JS console errors | Browser DevTools Console empty | [ ] |

---

## 🐛 COMMON ISSUES & FIXES

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| GPS "Start Capture" does nothing | Browser blocked geolocation (non-HTTPS) | Use `http://localhost:8080` (localhost exempt) |
| Farm not in DDS dropdown | Farm missing `centroid_lat/lon` | Ensure GPS capture completed; or admin edit farm to set coords |
| DDS generation 500 error | `DueDiligenceStatement` import missing | `backend/app/api/v2/admin.py:577` has `from app.models.compliance import DueDiligenceStatement` |
| DDS table empty after gen | Frontend used `response.dds` but endpoint returns `{dds:[...]}` | Fixed in `app.js:4815` — uses `response.dds || []` |
| Export XML blank | Endpoint `/admin/eudr/export/xml/{id}` returns 404 | Check DDS id exists; backend route at `admin.py:1797+` |
| Docker container exits | Port conflict (8000/8080/5432 in use) | Stop conflicting services or change ports in `docker-compose.yml` |
| Backend 500 on startup | `.env` missing required vars | Copy `.env.example` → `.env` and fill in secrets |

---

## 📊 ENVIRONMENT VARIABLES REQUIRED

Minimal for testing:
```bash
PLOTRA_APP__SECRET_KEY=dev-secret-key-change-in-prod-32chars
PLOTRA_DATABASE__HOST=postgres
PLOTRA_DATABASE__PORT=5432
PLOTRA_DATABASE__USERNAME=postgres
PLOTRA_DATABASE__PASSWORD=postgres
PLOTRA_DATABASE__NAME=plotra_db
```
(Docker compose already sets these; only needed if running locally without compose)

---

## 🎉 EXPECTED OUTCOME

After completing all tests, you should have:

- ✅ 1 farm with verified GPS polygon
- ✅ 1 Due Diligence Statement (DDS) generated with:
  - Real farm data (coordinates, area, variety)
  - Operator details from form
  - Auto-calculated risk (LOW for Kenya coffee)
  - Mitigation measures
  - Valid EU TRACES XML export
- ✅ Zero errors in browser console or backend logs
- ✅ All modals functional

---

**Ready to execute? Open http://localhost:8080 and begin Test 1.**
