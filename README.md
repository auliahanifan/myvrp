# Segarloka Auto-Route Service

Segarloka Auto-Route Service adalah aplikasi internal untuk menyusun rute pengiriman secara otomatis. Sistem ini membaca order harian, konfigurasi armada, dan aturan operasional, lalu menghasilkan rencana pengiriman yang mempertimbangkan kapasitas kendaraan, time window, biaya perjalanan, prioritas order, serta skenario distribusi melalui depot dan hub.

Implementasi saat ini sudah melampaui solver VRP dasar. Repository ini berisi aplikasi Streamlit untuk tim operasi, solver OR-Tools untuk direct routing dan multi-trip, serta workflow multi-hub dengan blind van consolidation dan last-mile delivery dari hub.

## Fitur Saat Ini

- Web app berbasis Streamlit untuk upload order, konfigurasi routing, eksekusi solver, dan download hasil.
- Parsing order CSV dengan validasi field utama, koordinat, bobot, tanggal, jam kirim, dan flag prioritas.
- Parsing konfigurasi YAML untuk armada, toleransi time window, multi-trip, cache, dan multi-hub.
- Perhitungan distance matrix dan duration matrix via OSRM, dengan cache lokal dan fallback Haversine saat request gagal.
- Solver VRP berbasis OR-Tools untuk:
  - direct routing dari depot,
  - multi-trip routing,
  - multi-hub / two-tier routing,
  - dynamic source assignment,
  - blind van routing untuk konsolidasi ke hub.
- Tiga strategi optimasi: `minimize_vehicles`, `minimize_cost`, dan `balanced`.
- Output Excel, CSV, dan visualisasi peta untuk hasil routing.
- Test unit dan integration untuk parser, solver, multi-trip, smart routing, dan workflow end-to-end.

## Gambaran Arsitektur

Alur utama sistem:

1. User upload file order CSV dari web app.
2. Sistem memuat `conf.yaml` untuk armada, routing, hub, dan parameter solver.
3. Lokasi depot, hub, dan customer dikirim ke OSRM untuk membentuk matriks jarak dan durasi.
4. Order diklasifikasikan ke sumber pengiriman yang sesuai:
   - langsung dari depot,
   - via hub berdasarkan zone mapping,
   - atau dipindahkan secara dinamis jika lebih efisien.
5. Solver menjalankan optimasi sesuai mode routing yang aktif.
6. Hasil disajikan sebagai tabel, file ekspor, dan peta.

## Mode Routing yang Didukung

### 1. Direct Routing

Semua order dikirim langsung dari depot dengan constraint kapasitas, time window, dan biaya.

### 2. Multi-Trip Routing

Kendaraan yang sama dapat dipakai lebih dari satu trip dalam satu hari, mengikuti buffer time, clustering order, dan batas maksimum trip per kendaraan.

### 3. Multi-Hub / Two-Tier Routing

Sistem mendukung 0 sampai N hub.

- Zero hub mode: semua order berangkat dari depot.
- Single hub mode: blind van melakukan konsolidasi ke hub, lalu motor mengantar order dari hub.
- Multi-hub mode: blind van mengunjungi beberapa hub, lalu last-mile diselesaikan dari masing-masing source.

### 4. Dynamic Source Assignment

Order dapat tetap mengikuti aturan zona, atau dipindahkan ke source lain jika secara biaya/jarak/waktu lebih menguntungkan, tergantung mode `zone_based`, `dynamic`, atau `hybrid`.

## Constraint Operasional

Constraint yang terlihat aktif di codebase:

- kapasitas kendaraan,
- time window pengiriman,
- prioritas order,
- return-to-depot policy,
- multi-trip reuse,
- hub arrival deadline untuk blind van,
- soft handling untuk sebagian constraint melalui tolerance atau penalty config,
- opsi order tidak ter-assign bila constraint terlalu ketat.

## Struktur Project

```text
seg-vrp/
├── app.py
├── conf.yaml
├── src/
│   ├── models/
│   ├── output/
│   ├── solver/
│   ├── utils/
│   └── visualization/
├── tests/
│   ├── integration/
│   └── unit/
├── example/
├── results/
└── Dockerfile
```

Folder penting:

- `app.py`: entrypoint aplikasi Streamlit.
- `src/application/`: application service layer untuk orchestration upload, config, planning, history, results, dan map.
- `src/presentation/`: adapter Streamlit state dan view model ringan.
- `conf.yaml`: konfigurasi armada, routing, solver, cache, dan multi-hub.
- `src/solver/vrp_solver.py`: solver VRP dasar.
- `src/solver/multi_trip_solver.py`: logika multi-trip.
- `src/solver/two_tier_vrp_solver.py`: solver multi-hub / two-tier.
- `src/solver/dynamic_source_assigner.py`: assignment source dinamis.
- `src/solver/blind_van_router.py`: routing blind van untuk konsolidasi hub.
- `src/output/`: generator Excel dan CSV.
- `tests/`: unit test dan integration test.

## Input yang Diharapkan

### Order CSV

Field utama yang didukung parser:

- `sale_order_id`
- `delivery_date`
- `delivery_time`
- `load_weight_in_kg`
- `partner_id`
- `display_name`
- `alamat`
- `coordinates` atau pasangan `partner_latitude` + `partner_longitude`

Field tambahan yang juga didukung:

- `kelurahan`
- `kecamatan`
- `kota`
- `is_priority`

### Konfigurasi YAML

`conf.yaml` memuat:

- daftar kendaraan dan kapasitas,
- biaya per km,
- jumlah unit tetap / unlimited,
- konfigurasi return to depot,
- tolerance time window,
- multi-trip config,
- solver config,
- cache config,
- definisi hub dan source assignment.

## Menjalankan Aplikasi

Project ini menggunakan `uv`.

### 1. Install dependency

```bash
uv sync
```

Jika Anda perlu install dari `requirements.txt`:

```bash
uv pip install -r requirements.txt
```

### 2. Siapkan environment

```bash
cp .env.example .env
```

Environment variable yang dipakai untuk depot:

```env
DEPOT_LATITUDE=-6.2088
DEPOT_LONGITUDE=106.8456
DEPOT_NAME=Segarloka Warehouse
DEPOT_ADDRESS=Jakarta, Indonesia
```

### 3. Jalankan web app

```bash
uv run streamlit run app.py
```

Alternatif:

```bash
./run_app.sh
```

## Boundary Arsitektur

UI dan backend di repo ini tetap satu monolith, tetapi sekarang dipisahkan secara internal:

- `app.py` hanya menangani widget, layout, dan interaksi Streamlit
- `src/application/` menjadi source of truth untuk orchestration bisnis
- solver, parser, output generator, dan visualizer dipanggil melalui application service, bukan langsung dari UI

Tujuannya adalah mencegah perubahan parsial di satu sisi saja. Perubahan flow routing idealnya selalu menyentuh vertical slice lengkap: UI, service contract, orchestration, dan test.

## Menjalankan Test

```bash
uv run pytest
```

Contoh menjalankan subset test:

```bash
uv run pytest tests/unit
uv run pytest tests/integration
```

Catatan: sebagian integration test akan mencoba membentuk distance matrix dari layanan OSRM, sehingga hasilnya bergantung pada akses service tersebut.

## Output

Sistem saat ini dapat menghasilkan:

- Excel workbook berisi route detail dan summary,
- CSV output untuk route dan ringkasan,
- HTML map / visualisasi rute.

Hasil umumnya disimpan di folder `results/`.

## Docker

Untuk menjalankan via Docker:

```bash
PORT=8501 ./docker_run.sh
```

Script ini akan:

- build image,
- menyiapkan mount untuk `results`, `.cache`, `.streamlit`, dan `conf.yaml`,
- menjalankan aplikasi Streamlit dalam container.

## Teknologi Utama

- Python 3.9+
- OR-Tools
- Streamlit
- Pandas
- NumPy
- openpyxl
- PyYAML
- folium / streamlit-folium
- OSRM

## Status Dokumentasi

README ini mengikuti implementasi aktual di codebase saat ini. Beberapa dokumen lama di repository mungkin masih merefleksikan fase awal project dan belum sepenuhnya menggambarkan fitur yang sudah tersedia sekarang.

## License

Proprietary - Segarloka Internal Use Only
