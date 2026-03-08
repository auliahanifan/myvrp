# Background Project Segarloka Auto-Route Service

Dokumen ini adalah draft latar belakang project yang disusun berdasarkan codebase saat ini. Isinya sengaja ditulis dalam bahasa bisnis-operasional, bukan sebagai dokumentasi teknis detail, supaya mudah dipakai sebagai bahan pengantar dan nanti bisa disesuaikan lagi.

## Ringkasan Singkat

Project ini dibuat untuk mengotomatisasi proses penyusunan rute pengiriman Segarloka. Saat ini proses routing dipahami sebagai pekerjaan operasional yang sebelumnya banyak dilakukan secara manual, sementara kebutuhan lapangan sudah cukup kompleks: ada banyak order harian, variasi kapasitas kendaraan, target waktu kirim, prioritas order tertentu, serta kebutuhan distribusi dari depot dan hub. Sistem ini hadir untuk membantu tim operasi membuat keputusan routing yang lebih cepat, lebih konsisten, dan lebih terukur.

## Latar Belakang Bisnis

Segarloka menjalankan distribusi produk segar dengan karakter operasional yang sensitif terhadap waktu. Order harus sampai sesuai jadwal, kapasitas kendaraan tidak boleh terlampaui, dan biaya pengiriman tetap perlu dijaga. Dalam kondisi seperti ini, routing manual cenderung menimbulkan beberapa masalah:

- penyusunan rute memakan waktu lama setiap hari,
- hasil routing sangat bergantung pada pengalaman individu operator,
- sulit menjaga konsistensi ketika jumlah order meningkat,
- keputusan penggunaan kendaraan tidak selalu optimal,
- evaluasi hasil routing menjadi sulit karena tidak ada dasar perhitungan yang seragam.

Codebase ini menunjukkan bahwa project dirancang untuk menjawab masalah tersebut dengan mengubah data order dan konfigurasi armada menjadi rencana pengiriman yang bisa langsung dipakai tim operasi.

## Tujuan Project

Secara praktis, tujuan project ini adalah:

- mengurangi pekerjaan manual dalam penyusunan rute harian,
- membantu alokasi order ke kendaraan yang sesuai kapasitas dan karakter pengiriman,
- menjaga kepatuhan terhadap time window pengiriman,
- mendukung prioritas order tertentu,
- menurunkan biaya dan inefisiensi perjalanan,
- menyediakan output rute yang lebih mudah dibaca dan dieksekusi oleh tim operasional.

## Gambaran Solusi yang Dibangun

Berdasarkan struktur aplikasi saat ini, solusi yang dibangun bukan hanya solver VRP sederhana, tetapi sebuah alur routing operasional yang cukup lengkap.

Alur besarnya sebagai berikut:

1. Tim operasi mengunggah data order harian dalam format CSV.
2. Sistem membaca konfigurasi kendaraan dan aturan routing dari file konfigurasi YAML.
3. Sistem membentuk matriks jarak dan durasi perjalanan menggunakan OSRM.
4. Order diklasifikasikan apakah dikirim langsung dari depot atau melalui hub tertentu.
5. Solver menjalankan optimasi rute dengan mempertimbangkan constraint operasional.
6. Hasil routing disajikan dalam bentuk Excel, CSV, dan visualisasi peta.

Dengan kata lain, project ini berperan sebagai decision-support tool untuk operasi pengiriman, bukan sekadar library algoritma.

## Karakter Operasional yang Tercermin di Codebase

Beberapa kebutuhan bisnis yang terlihat jelas dari codebase:

### 1. Order memiliki batas waktu pengiriman

Model order mendukung `delivery_time` dalam bentuk jam tunggal maupun rentang waktu. Ini menandakan bahwa ketepatan waktu adalah constraint inti, bukan tambahan opsional.

### 2. Kapasitas kendaraan menjadi constraint utama

Setiap kendaraan memiliki kapasitas muatan dan biaya per kilometer. Solver dibangun untuk memastikan penugasan order tidak melebihi kapasitas tersebut.

### 3. Tidak semua order diperlakukan sama

Ada konsep `priority order`, artinya sistem perlu memberi perhatian khusus pada order tertentu yang lebih sensitif atau lebih penting bagi operasi.

### 4. Armada bersifat heterogen

Konfigurasi kendaraan memperlihatkan adanya beberapa tipe armada, misalnya Blind Van, City Car, dan Sepeda Motor, masing-masing dengan kapasitas, biaya, dan jumlah unit yang berbeda.

### 5. Operasi pengiriman tidak selalu single-trip

Codebase sudah mendukung `multiple trips`, yang berarti satu kendaraan fisik bisa dipakai lebih dari sekali dalam satu hari bila jadwal dan kapasitas memungkinkan.

### 6. Model distribusi sudah berkembang ke skema multi-hub

Sistem tidak hanya berasumsi semua order berangkat dari satu depot. Ada dukungan untuk:

- pengiriman langsung dari depot,
- konsolidasi barang ke hub dengan Blind Van,
- pengiriman last-mile dari hub dengan motor,
- pemetaan area tertentu ke hub tertentu,
- fallback ke hub terdekat atau assignment dinamis berdasarkan biaya.

Ini menunjukkan bahwa project sudah mengarah ke model distribusi dua tingkat atau multi-source routing.

## Nilai yang Ingin Dicapai

Jika sistem ini berjalan sesuai tujuan, manfaat yang ingin dicapai antara lain:

- proses planning harian menjadi lebih cepat,
- penggunaan kendaraan menjadi lebih efisien,
- beban kerja operator berkurang,
- keputusan routing menjadi lebih objektif dan repeatable,
- operasional lebih siap menghadapi pertumbuhan order,
- hasil routing lebih mudah diaudit dan dievaluasi.

## Bentuk Produk Saat Ini

Berdasarkan `app.py`, project ini sudah memiliki antarmuka berbasis Streamlit. Artinya pengguna non-teknis dari tim operasi diarahkan untuk memakai sistem melalui web interface, bukan melalui command line langsung.

Dari codebase juga terlihat bahwa sistem saat ini sudah mencakup:

- parser input CSV order,
- parser konfigurasi YAML kendaraan dan hub,
- kalkulasi distance matrix berbasis OSRM dengan cache,
- solver VRP berbasis OR-Tools,
- skenario routing direct, multi-trip, dan multi-hub,
- generator output Excel dan CSV,
- visualisasi peta hasil routing,
- test unit dan integration untuk memvalidasi alur utama.

## Catatan Penting dari Kondisi Codebase

Ada indikasi bahwa dokumentasi lama di repository belum sepenuhnya mengikuti perkembangan implementasi terbaru. README masih banyak bercerita tentang fase awal solver VRP, sementara codebase dan test sudah menunjukkan kemampuan yang lebih maju seperti multi-hub routing, dynamic source assignment, dan multi-trip. Karena itu, background project yang lebih akurat sebaiknya mengikuti implementasi aktual yang sudah ada di source code.

## Narasi Singkat yang Bisa Dipakai

Segarloka Auto-Route Service adalah sistem internal untuk membantu tim operasi menyusun rute pengiriman secara otomatis. Project ini dibangun karena proses routing manual semakin sulit dipertahankan ketika jumlah order, variasi armada, batas waktu pengiriman, dan kompleksitas area layanan terus meningkat. Melalui kombinasi data order, konfigurasi kendaraan, perhitungan jarak berbasis OSRM, dan optimasi rute menggunakan OR-Tools, sistem ini menghasilkan rencana pengiriman yang lebih cepat disusun, lebih konsisten, dan lebih relevan dengan kondisi operasional di lapangan. Seiring perkembangan kebutuhan, sistem ini juga sudah mengakomodasi skenario distribusi yang lebih kompleks seperti penggunaan hub, pengiriman bertingkat, dan pemakaian kendaraan multi-trip dalam satu hari.

## Asumsi Penulisan Draft Ini

Beberapa kalimat dalam dokumen ini ditarik dari kombinasi source code, konfigurasi, dan test, sehingga ada bagian yang bersifat inferensi wajar, bukan statement bisnis resmi. Poin-poin yang kemungkinan perlu Anda sesuaikan nanti:

- istilah resmi untuk tim pengguna sistem,
- definisi KPI utama project,
- alasan bisnis utama penggunaan hub,
- target efisiensi yang ingin dikejar,
- batasan operasional yang berlaku di lapangan tetapi belum tertulis di codebase.
