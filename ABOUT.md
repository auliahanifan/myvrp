# 🚚 VRP Solver - Vehicle Routing Problem untuk Segarloka

Aplikasi web untuk optimasi routing pengiriman sayur Segarloka ke customer FnB menggunakan ojek online (Gojek/Grab) dengan constraint time windows, capacity, dan priority orders.

---

## 🎯 Problem Statement

**Segarloka** adalah perusahaan e-commerce yang menjual sayur-sayuran untuk industri FnB (Food & Beverage). Setiap hari, Segarloka harus mengirim puluhan hingga ratusan order ke berbagai customer dengan:
- **Time windows ketat** - Customer menerima barang pada jam tertentu (misal: 04:00-05:00)
- **Beragam lokasi** - Tersebar di Jakarta, Tangerang, dan sekitarnya
- **Berbagai volume order** - Dari 1.5 kg hingga 200+ kg per order
- **Metode delivery** - Menggunakan ojek online (Gojek/Grab) dengan berbagai jenis kendaraan

**Challenge:** Tim operasional Segarloka saat ini mengatur routing secara manual, memakan waktu lama dan tidak optimal dari segi cost dan efisiensi.

**Solution:** Aplikasi VRP Solver yang secara otomatis membuat routing optimal berdasarkan input CSV order harian, dengan output yang dapat diedit oleh tim ops.

---

## 👥 Target User

**Tim Operasional Segarloka** - Staff ops yang setiap hari mengatur pengiriman sayur ke puluhan customer FnB.

---

## 📋 Features

### Core Features
✅ **Multi-Vehicle Types** - Dinamis berdasarkan konfigurasi YAML (bisa tambah/ubah jenis kendaraan)
✅ **Unlimited Vehicle Fleet** - Otomatis menambah kendaraan jika capacity tidak cukup (karena pakai ojek online)
✅ **Time Windows Constraint** - HARUS memenuhi time window delivery customer
✅ **Service Time** - Unload barang 15 menit per lokasi, berangkat 30 menit sebelum delivery time
✅ **Real Distance** - Menggunakan Google Maps Distance Matrix API untuk jarak akurat
✅ **Priority Orders** - Highlight order dengan `is_priority=true` dengan warna berbeda
✅ **Dynamic Optimization Strategy** - User bisa pilih via radio button:
  - Minimize jumlah kendaraan (cost lebih tinggi, driver lebih sedikit)
  - Minimize total cost (pakai lebih banyak kendaraan, cost lebih rendah)
  - Balanced (balance antara jumlah kendaraan dan cost)

### Input/Output
📥 **Input:**
- CSV file order harian dengan format: `sale_order_id`, `delivery_date`, `delivery_time`, `load_weight_in_kg`, `partner_id`, `display_name`, `alamat`, `zip`, `partner_latitude`, `partner_longitude`, `kota`, `kecamatan`, `kelurahan`, `is_priority`
- YAML file vehicle config (static, hardcoded di repo)
- Depot location (hardcoded, single depot untuk sekarang)

📤 **Output:**
- Excel file dengan routing result yang **dapat diedit** oleh tim ops
- Hasil routing disimpan dengan timestamp untuk historical tracking

### Technology
🖥️ **Interface:** Streamlit atau Gradio (web app, hosted)
🗺️ **Maps API:** Google Maps Distance Matrix API (no visualization untuk hemat cost)
💾 **Storage:** Excel files dengan timestamp untuk historical routing results
🧮 **Solver:** OR-Tools VRP solver (Python)

---

## 🚀 Workflow

1. **Upload CSV** - Tim ops upload file CSV order harian
2. **Select Strategy** - Pilih optimization strategy (minimize vehicles / minimize cost / balanced)
3. **Generate Routes** - Sistem compute optimal routing dengan OR-Tools
4. **Review & Edit** - Tim ops review hasil routing di Excel, bisa edit manual jika perlu
5. **Save Result** - Hasil routing disimpan dengan timestamp untuk tracking

---

## 📊 Business Rules

### Time Windows
- **Delivery time:** Sesuai `delivery_time` di CSV (contoh: 04:00-05:00, 12:00-15:00)
- **Departure time:** 30 menit sebelum delivery time (jika delivery 12:00-15:00, berangkat jam 11:30)
- **Service time:** 15 menit per lokasi untuk unload barang
- **Constraint:** Time window HARUS dipenuhi (hard constraint)

### Vehicle Capacity
- Sepeda Motor: 80 kg @ Rp 2,000/km
- Mobil: 150 kg @ Rp 3,500/km
- Minitruck: 250 kg @ Rp 5,000/km
- Jika capacity tidak cukup → sistem **otomatis menambah kendaraan** (unlimited, karena pakai ojek online)

### Priority Orders
- Order dengan `is_priority=true` akan di-highlight dengan warna berbeda di result
- Prioritas hanya untuk visual highlight, tidak mengubah optimasi (tim ops bisa edit manual)

### Depot
- Single depot (lokasi hardcoded)
- Semua kendaraan start dan end di depot

---

## 🔧 Technical Specifications

### Input Format (CSV)
```csv
sale_order_id,delivery_date,delivery_time,load_weight_in_kg,partner_id,display_name,alamat,zip,partner_latitude,partner_longitude,kota,kecamatan,kelurahan,is_priority
157394,2025-10-08T04:00:00,04:00-05:00,48.65,7083,Baku Sayang Senopati,"Jl. Ciranjang No.11,",12180,-6.23762,106.81096,JAKARTA SELATAN,KEBAYORAN BARU,RAWA BARAT,false
```

### Vehicle Config (YAML)
```yaml
vehicle:
  name: "Sepeda Motor"
  capacity: 80
  cost_per_km: 2000

vehicle:
  name: "Mobil"
  capacity: 150
  cost_per_km: 3500

vehicle:
  name: "Minitruck"
  capacity: 250
  cost_per_km: 5000
```

### Output Format (Excel)

**Sheet 1: "Routes by Vehicle"**

Format Excel dengan grouping/outline yang collapsible (pakai Excel outline feature):

```
Column A: Vehicle/Driver Name (grouped)
Column B: Delivery Time Window
Column C: Customer Name
Column D: Address
Column E: Rate/Cost (Rp)
Column F: Total Weight (kg)
Column G: Estimated Arrival Time
Column H: Departure Time
Column I: Distance from Previous (km)
Column J: Cumulative Weight (kg)
Column K: Route Sequence
Column L: Lat/Long
Column M: Notes
```

**Struktur dengan Excel Grouping:**
```
[-] ALI (Sepeda Motor) - Total: Rp 140,000 | 134.25 kg
    04.00.00  Ayam Bakar Assalam      Jl. ...    20,000   14 kg    03:45   04:00   5.2 km   14 kg      1
    04.00.00  Nouval Catering          Jl. ...    25,000   7.5 kg   04:20   04:35   3.1 km   21.5 kg    2
    05.00.00  Sambel Geprek           Jl. ...    25,000   12 kg    05:10   05:25   4.8 km   33.5 kg    3

[-] ARIS (Mobil) - Total: Rp 100,000 | 91.7 kg
    04.00.00  Bu Lely                  Jl. ...    25,000   11.5 kg  03:45   04:00   6.1 km   11.5 kg    1
    05.00.00  Lembur Kuring           Jl. ...    25,000   19 kg    05:15   05:30   7.3 km   30.5 kg    2
```

**Features:**
- ✅ **Collapsible grouping** - Pakai Excel outline (tombol [-] untuk collapse/expand per driver)
- ✅ **Subtotal rows** - Setiap vehicle group punya subtotal (cost + weight)
- ✅ **Color coding** - Priority orders di-highlight kuning/merah
- ✅ **Editable** - Ops bisa edit, drag-drop customer antar driver
- ✅ **Sequence numbers** - Urutan delivery jelas per vehicle

**Sheet 2: "Summary"**
```
Total Vehicles Used: 8
Total Distance: 245.7 km
Total Cost: Rp 892,500
Total Orders Delivered: 135
Optimization Strategy: Minimize Cost
Depot Location: [Coordinates]
Generated At: 2025-10-08 14:30:00
```

**Filename:** `routing_result_2025-10-08_14-30-00.xlsx`

---

## 📈 Success Metrics

- ⏱️ **Time saving** - Routing time dari 1-2 jam manual menjadi < 5 menit
- 💰 **Cost reduction** - 15-30% cost saving dari optimal routing
- 🎯 **Constraint satisfaction** - 100% time windows terpenuhi
- 👥 **User adoption** - Tim ops Segarloka pakai daily untuk routing

---

## 🛠️ Development Stack

- **Backend:** Python 3.10+
- **Optimization:** OR-Tools (Google's VRP solver)
- **Web Framework:** Streamlit / Gradio
- **Maps API:** Google Maps Distance Matrix API
- **Data Processing:** Pandas, NumPy
- **Output:** openpyxl (Excel generation)
- **Deployment:** Cloud hosting (Streamlit Cloud / Hugging Face Spaces / Railway)

---

## 📝 Future Enhancements (V2)

- Multiple depot support
- Driver shift constraints (max 8 jam kerja)
- Real-time tracking integration dengan Gojek/Grab API
- Dashboard analytics (vehicle utilization, cost trends, on-time delivery rate)
- Mobile app untuk driver dengan turn-by-turn navigation
- Dynamic re-routing jika ada order baru mid-day  
