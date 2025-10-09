# 📋 Development Plan - VRP Solver untuk Segarloka

## 🎯 Project Overview
Build a web-based VRP (Vehicle Routing Problem) solver untuk optimasi routing pengiriman sayur Segarloka dengan constraint time windows, capacity, dan priority orders.

---

## 📦 Phase 1: Core Backend & VRP Solver

### 1.1 Project Setup
- [x] Initialize Python project (pyproject.toml)
- [x] Setup dependencies (OR-Tools, Pandas, NumPy, openpyxl)
- [x] Create folder structure:
  ```
  src/
    ├── models/          # Data models
    ├── solver/          # VRP solver logic
    ├── utils/           # Helpers (CSV parser, distance matrix, etc)
    ├── output/          # Excel generator
    └── config/          # Config files
  example/
    ├── example_input.csv
    └── example_input_vehicle.yaml
  results/               # Output Excel files
  tests/                 # Unit tests
  ```

### 1.2 Data Models
- [x] Create `Order` model (from CSV columns)
- [x] Create `Vehicle` model (from YAML config)
- [x] Create `Route` model (untuk hasil routing)
- [x] Create `Location` model (depot + customer locations)

### 1.3 Input Parsers
- [x] CSV parser untuk order data
  - Parse columns: sale_order_id, delivery_date, delivery_time, load_weight_in_kg, partner_id, display_name, alamat, coordinates, is_priority
  - Validation: check required fields, valid coordinates, valid time windows
- [x] YAML parser untuk vehicle config
  - Parse vehicle types: name, capacity, cost_per_km
  - Validation: positive capacity & cost

### 1.4 Google Maps Integration
- [x] Setup Google Maps Distance Matrix API client
- [x] Create distance matrix calculator
  - Input: list of locations (depot + customers)
  - Output: distance matrix (km) dan duration matrix (minutes)
- [x] Add caching untuk API calls (untuk hemat quota)
- [x] Error handling (API limit, invalid coordinates, etc)

### 1.5 VRP Solver (OR-Tools)
- [x] Setup OR-Tools CVRPTW (Capacitated VRP with Time Windows)
- [x] Implement constraints:
  - **Capacity constraint**: Vehicle max capacity tidak boleh terlampaui
  - **Time window constraint**: HARD constraint, HARUS dipenuhi
  - **Service time**: 15 menit per lokasi untuk unload
  - **Departure time**: 30 menit sebelum earliest delivery time
  - **Depot constraint**: Semua vehicle start dan end di depot
- [x] Implement 3 optimization strategies:
  - **Minimize vehicles**: Minimize jumlah kendaraan yang dipakai
  - **Minimize cost**: Minimize total cost (distance * cost_per_km)
  - **Balanced**: Balance antara jumlah vehicle dan cost
- [x] Handle unlimited vehicle fleet (auto-add vehicle jika capacity tidak cukup)
- [x] Solution output: routes per vehicle dengan urutan customer

---

## 📊 Phase 2: Output Generator

### 2.1 Excel Output Generator
- [ ] Generate Excel dengan 2 sheets:

  **Sheet 1: "Routes by Vehicle"**
  - [ ] Columns: Vehicle Name, Delivery Time, Customer, Address, Rate, Weight, Arrival Time, Departure Time, Distance, Cumulative Weight, Sequence, Lat/Long, Notes
  - [ ] Group by vehicle (dengan Excel outline/grouping feature)
  - [ ] Subtotal rows per vehicle (total cost, total weight)
  - [ ] Color coding untuk priority orders (kuning/merah)
  - [ ] Format currency untuk cost (Rp xxx,xxx)
  - [ ] Format time (HH:MM)

  **Sheet 2: "Summary"**
  - [ ] Total vehicles used
  - [ ] Total distance (km)
  - [ ] Total cost (Rp)
  - [ ] Total orders delivered
  - [ ] Optimization strategy used
  - [ ] Depot location
  - [ ] Generated timestamp

- [ ] Filename dengan timestamp: `routing_result_YYYY-MM-DD_HH-MM-SS.xlsx`
- [ ] Save to `results/` folder untuk historical tracking

---

## 🖥️ Phase 3: Web Interface (Streamlit)

### 3.1 UI Components
- [ ] **Upload Section**
  - CSV file uploader
  - Preview uploaded data (show first 10 rows)
  - Validation feedback (error messages jika ada invalid data)

- [ ] **Configuration Section**
  - Radio button untuk optimization strategy:
    - ⚙️ Minimize Vehicles
    - 💰 Minimize Cost
    - ⚖️ Balanced
  - Input depot location (lat, long) - untuk sekarang hardcoded, tapi bisa editable
  - Display vehicle config (from YAML)

- [ ] **Processing Section**
  - "Generate Routes" button
  - Progress bar/spinner saat computing
  - Status messages (fetching distances, solving VRP, generating Excel, etc)

- [ ] **Results Section**
  - Display summary metrics (total vehicles, distance, cost)
  - Preview route results (table view)
  - Download button untuk Excel file
  - Link untuk view historical results

### 3.2 Historical Results Viewer
- [ ] List previous routing results (dari `results/` folder)
- [ ] Filter by date
- [ ] Download previous results

---

## 🧪 Phase 4: Testing & Validation

### 4.1 Unit Tests
- [ ] Test CSV parser dengan valid & invalid data
- [ ] Test YAML parser
- [ ] Test distance matrix calculator (mock API)
- [ ] Test VRP solver dengan sample data
- [ ] Test Excel generator output

### 4.2 Integration Tests
- [ ] End-to-end test: CSV input → VRP solver → Excel output
- [ ] Test all 3 optimization strategies
- [ ] Test dengan berbagai skenario:
  - Small dataset (10 orders)
  - Medium dataset (50 orders)
  - Large dataset (135 orders, seperti example)
  - Edge cases (1 order, semua orders di lokasi yang sama, dll)

### 4.3 Validation
- [ ] Validate time windows terpenuhi (HARUS 100%)
- [ ] Validate capacity tidak terlampaui
- [ ] Validate route sequence logical (tidak zigzag)
- [ ] Validate cost calculation correct

---

## 🚀 Phase 5: Deployment

### 5.1 Pre-deployment
- [ ] Add requirements.txt / poetry.lock
- [ ] Add .env untuk Google Maps API key
- [ ] Add .gitignore (results/, .env, __pycache__, etc)
- [ ] Add README.md dengan usage instructions
- [ ] Add example files untuk testing

### 5.2 Deployment Options
**Option 1: Streamlit Cloud** (Recommended untuk start)
- [ ] Push to GitHub
- [ ] Deploy ke Streamlit Cloud
- [ ] Set environment variables (Google Maps API key)
- [ ] Test deployed app

**Option 2: Railway / Render**
- [ ] Dockerfile (jika perlu)
- [ ] Deploy configuration
- [ ] Domain setup (optional)

### 5.3 User Onboarding
- [ ] Create user guide (cara upload CSV, pilih strategy, download result)
- [ ] Demo video / walkthrough
- [ ] Training untuk tim ops Segarloka

---

## 📝 Phase 6: Monitoring & Iteration

### 6.1 Monitoring
- [ ] Track API usage (Google Maps quota)
- [ ] Monitor app performance (processing time)
- [ ] Collect user feedback dari tim ops

### 6.2 Improvements
- [ ] Optimize solver performance (jika processing time > 1 menit)
- [ ] Add more validation & error handling
- [ ] UI/UX improvements based on user feedback
- [ ] Consider caching historical distance matrices

---

## 🔮 Future Enhancements (V2)

### Backlog
- [ ] Multiple depot support
- [ ] Driver shift constraints (max 8 jam kerja)
- [ ] Real-time tracking integration (Gojek/Grab API)
- [ ] Dashboard analytics (vehicle utilization, cost trends)
- [ ] Mobile app untuk driver (turn-by-turn navigation)
- [ ] Dynamic re-routing (jika ada order baru mid-day)
- [ ] Route optimization dengan traffic data
- [ ] Automated daily routing (scheduled jobs)

---

## 📊 Success Criteria

### MVP (Minimum Viable Product)
✅ Tim ops bisa upload CSV order harian
✅ App generate routing dalam < 5 menit
✅ Output Excel dengan format yang familiar & editable
✅ 100% time windows constraint terpenuhi
✅ Capacity constraint tidak terlampaui
✅ 3 optimization strategies available

### Production Ready
✅ Deployed & accessible via URL
✅ Stable (no crashes)
✅ Google Maps API integration working
✅ Historical results tracking
✅ User documentation complete
✅ Tim ops Segarloka sudah trained & actively using

---

## ⏱️ Timeline Estimation

| Phase | Estimated Time | Priority |
|-------|---------------|----------|
| Phase 1: Core Backend & VRP Solver | 3-4 days | 🔴 Critical |
| Phase 2: Output Generator | 1-2 days | 🔴 Critical |
| Phase 3: Web Interface | 2-3 days | 🔴 Critical |
| Phase 4: Testing & Validation | 2 days | 🟡 High |
| Phase 5: Deployment | 1 day | 🟡 High |
| Phase 6: Monitoring & Iteration | Ongoing | 🟢 Medium |

**Total MVP Timeline: ~10-12 days**

---

## 🎯 Next Steps

1. ✅ Complete ABOUT.md (requirements documentation) - DONE
2. ✅ Complete PLAN.md (this file) - DONE
3. ⏭️ **Start Phase 1.1**: Initialize project & setup dependencies
4. ⏭️ **Phase 1.2-1.3**: Build data models & parsers
5. ⏭️ **Phase 1.4**: Google Maps integration
6. ⏭️ **Phase 1.5**: VRP solver implementation (core logic)

---

## 📞 Stakeholders

- **Developer**: You (implementation)
- **End User**: Tim Operasional Segarloka
- **Business Owner**: Segarloka management

---

## 🔑 Key Technical Decisions

1. **Solver**: OR-Tools (Google's open-source VRP solver) - industry standard, powerful, well-documented
2. **Web Framework**: Streamlit - simple, fast to build, easy deployment
3. **Output Format**: Excel dengan grouping - familiar untuk ops, editable
4. **Maps API**: Google Maps Distance Matrix - accurate, reliable
5. **Storage**: File-based (Excel) - simple, no database needed untuk MVP
6. **Deployment**: Streamlit Cloud - free tier, easy setup

---

## 📚 References

- [OR-Tools VRP Documentation](https://developers.google.com/optimization/routing)
- [Google Maps Distance Matrix API](https://developers.google.com/maps/documentation/distance-matrix)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [openpyxl Documentation](https://openpyxl.readthedocs.io/)
