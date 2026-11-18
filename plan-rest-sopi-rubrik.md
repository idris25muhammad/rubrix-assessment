# Plan Integrasi REST API ProdiSync ke RubriX (`plan-rest-sopi-rubrik.md`)

Dokumen ini merinci rencana arsitektur, alur pengguna, pemetaan skema data, dan *task breakdown* untuk mengintegrasikan **ProdiSync REST API v1 (Read-Only)** ke dalam aplikasi **RubriX** agar data **Master SO-PI** dan **pembuatan rubrik awal mata kuliah** selalu konsisten dengan RPS yang telah disetujui di ProdiSync.

---

## 1. Tujuan & Latar Belakang

Saat ini di RubriX:
1. **Data SO-PI** dikelola secara manual melalui halaman *Manage SO-PI* (`/sopi`) atau di-*seed* dari file statis `static/data/so-pi.json`.
2. **Pembuatan Rubrik Awal** dilakukan dengan mengetik manual di *5-Step Wizard* (`+ Create Rubric`) atau mengunggah file JSON hasil ekspor manual dari ProdiSync (`Upload Course JSON`).

Dengan tersedianya **ProdiSync REST API v1**:
- **Single Source of Truth:** Data SO, PI, Proficiency Level IABEE (1–5), daftar Mata Kuliah, CPL/CLO, bobot instrumen asesmen, dan kriteria rubrik dapat ditarik langsung dari ProdiSync secara *real-time* maupun tersinkronisasi ke database lokal RubriX.
- **Konsistensi Pembuatan Rubrik Awal:** Dosen/KPS tidak perlu lagi mengunduh-unggah file JSON manual atau mengetik ulang CPL & SO-PI. Cukup memilih Mata Kuliah dari katalog ProdiSync, dan wizard pembuatan rubrik akan otomatis terisi (*pre-filled*) dengan data RPS resmi, lalu dosen tinggal memverifikasi/melengkapi pemetaan sub-komponen ke CPL–PI (`cpl_pis`).

---

## 2. Spesifikasi & Hasil Uji Endpoint ProdiSync API v1

- **Base URL:** `https://rks.polibatam.ac.id/prodisync/prodisync/api/v1`
- **Autentikasi:** Header `X-API-Key: <PRODISYNC_API_KEY>` (hanya menerima metode `GET`).

### 2.1 Ringkasan Endpoint & Struktur Respons Nyata
Berdasarkan hasil inspeksi langsung ke server ProdiSync:

| Endpoint | Kegunaan di RubriX | Catatan Struktur Payload (`data` & `meta`) |
|---|---|---|
| `GET /ping` | Cek kesehatan koneksi & validitas API Key | `{"status": "ok", "client": "Aplikasi Rubrix", "api_version": "v1"}` |
| `GET /prodi` | Daftar prodi yang tersedia di ProdiSync & Tahun Ajaran aktif | `data`: `[{kode: "RKS", nama: "...", jenjang: "D4"}, ...]`<br>`meta.tahun_ajaran_aktif`: `{label: "2026/2027 Ganjil", tahun: "2026/2027", semester: "Ganjil"}` |
| `GET /proficiency-levels` | Sinkronisasi level 1–5 IABEE | `data`: `[{level: 1, label: "to have experienced..."}, ...]` |
| `GET /prodi/{prodi}/so-pi` | Sinkronisasi master SO & PI beserta levelnya per prodi | `data.student_outcomes`: `[{so_code, description, is_active, performance_indicators: [{pi_code, description, level, level_label}]}]` |
| `GET /prodi/{prodi}/matakuliah` | Katalog mata kuliah & ringkasan status RPS untuk dropdown/pencarian MK | Mendukung query `?rps_status=approved\|all`, `?ta=...`, `?semester=...`.<br>`data`: `[{kode, nama, sks, semester, kurikulum, rps: {status, tahun_ajaran, clo_count, so_codes, pi_codes}}]` |
| `GET /prodi/{prodi}/matakuliah/{kode_mk}/rubrik` | Mengambil payload rubrik lengkap 1 MK untuk *pre-fill* pembuatan rubrik awal | `data`: `{course_code, course_name, sks, semester, study_program, is_pbl, target_attainment, categories: [...], cpls: [...]}` |
| `GET /prodi/{prodi}/rubrik-courses` | *Bulk fetch* seluruh MK yang memiliki RPS `approved` beserta payload rubriknya | `data`: Array objek rubrik lengkap (format identik dengan `/matakuliah/{kode_mk}/rubrik`). |

---

## 3. Pemetaan Skema Data (ProdiSync API $\leftrightarrow$ RubriX)

Terdapat beberapa perbedaan penamaan *field* dan kode antara ProdiSync API dan database RubriX yang harus dinormalisasi pada *service layer*:

### 3.1 Normalisasi Kode Program Studi
Di RubriX (`modules/so_pi.py`), kode prodi menggunakan awalan jenjang untuk sebagian prodi, sedangkan di ProdiSync menggunakan kode singkat:
- `RKS` (RubriX) $\leftrightarrow$ `RKS` (ProdiSync)
- `D4-TP` (RubriX) $\leftrightarrow$ `TP` (ProdiSync)
- `D4-TRM` (RubriX) $\leftrightarrow$ `TRM` (ProdiSync)
- *(dan pemetaan fallback otomatis untuk `D3-TI` $\leftrightarrow$ `TI`, `D4-TRPL` $\leftrightarrow$ `TRPL`, `D3-TG` $\leftrightarrow$ `TG`, `D4-ANIM` $\leftrightarrow$ `ANIM`, `S2-TK` $\leftrightarrow$ `MSTK`/`S2-TK`)*.

### 3.2 Normalisasi Payload SO-PI (`/prodi/{kode}/so-pi`)
| Field ProdiSync API | Field Model / JSON RubriX (`So`, `Pi`) | Aturan Transformasi |
|---|---|---|
| `so.so_code` | `So.so_code` | String langsung (mis. `"SO1"`) |
| `so.description` | `So.so_description` | Map `description` $\rightarrow$ `so_description` |
| `pi.pi_code` | `Pi.pi_code` | String langsung (mis. `"PI-01.1"`) |
| `pi.description` | `Pi.pi_description` | Map `description` $\rightarrow$ `pi_description` |
| `pi.level` | `Pi.proficiency_level` | Map `level` (int 1–5) $\rightarrow$ `proficiency_level` |

### 3.3 Normalisasi Payload Rubrik MK (`/matakuliah/{kode_mk}/rubrik`)
Struktur `data` dari endpoint `/rubrik` dan `/rubrik-courses` **sudah 95% kompatibel** dengan format JSON internal RubriX (seperti `RKS-532_21.json`), dengan detail penting berikut:
1. **Field `cpls[]` di ProdiSync memiliki metadata tambahan yang sangat membantu:**
   - `code`, `description`, `proficiency_level`, `so_codes` (sudah sama).
   - `pi_codes`: daftar PI yang ditetapkan pada CPL tersebut di RPS (mis. `["PI-09.4"]`).
   - `so_pi_pairs`: `[{"so_code": "SO9", "pi_code": "PI-09.4", "level": 3}]`.
   - `assessment_rubric`: dapat berupa objek `{"PI-01.2": {"1": "...", ...}}` **atau `null`** (mis. pada `MKU004`).
   - **Solusi Konsistensi di RubriX:** Saat ini wizard RubriX (`openWizardFromUpload` di `templates/index.html`) membaca daftar PI yang diizinkan untuk suatu CPL dari `Object.keys(cpl.assessment_rubric)`. Jika `assessment_rubric` bernilai `null`, wizard menampilkan error *"PI untuk CPLx belum tersedia di JSON"*. Dengan adanya `so_pi_pairs` dan `pi_codes` dari API ProdiSync, kita harus memperbarui logika wizard & `rubric_builder.py` agar membaca daftar PI valid sebuah CPL dari `so_pi_pairs` / `pi_codes` / `assessment_rubric`.
2. **Field `components[].cpl_pis` dari ProdiSync bernilai `[]` (kosong):**
   - Seperti pada alur *Upload JSON*, ProdiSync menyediakan kategori (`partisipatif`, `tugas`, `kuis`, `ats`, `aas`, `proyek`), nama sub-komponen, bobot (`weight`), dan 5 level `criteria`, tetapi `cpl_pis` masih `[]`.
   - Oleh karena itu, pembuatan rubrik awal dari API akan memuat seluruh data MK ke dalam **Wizard (mode *From ProdiSync*)** sehingga informasi MK, CPL, SO, PI, bobot, dan kriteria sudah terisi penuh & *locked/consistent* dengan RPS, lalu dosen langsung diarahkan untuk memetakan sub-komponen ke CPL–PI pada Step 3 sebelum menyimpan rubrik.
3. **Edge Case `sks: 0`:**
   - Beberapa MK di API (mis. `RKS-405`) memiliki `sks: 0`. Validasi/input SKS di wizard perlu menangani nilai `0` atau membiarkan dosen/KPS menyesuaikan SKS jika bernilai `0` di API.

---

## 4. Rancangan Fitur & Alur Pengguna (UX Flow)

### 4.1 Sinkronisasi Master SO-PI dari ProdiSync (Mode Read-Only di `/sopi`)
1. **Halaman Manage SO-PI (`/sopi`) Menjadi Read-Only (Single Source of Truth = ProdiSync):**
   - Untuk menjaga agar data SO, PI, dan Proficiency Level di RubriX **100% selalu konsisten dengan ProdiSync** dan tidak diubah sepihak oleh KPS/Admin di RubriX, fitur manual **Add / Edit / Delete SO & PI** serta **Edit Proficiency Levels** di halaman `/sopi` **dinonaktifkan (Read-Only)**.
   - Endpoint mutasi manual (`POST /sopi/api/so`, `PUT/DELETE /sopi/api/so/<id>`, `POST /sopi/api/pi`, `PUT/DELETE /sopi/api/pi/<id>`, `PUT /sopi/api/levels`) diblokir untuk modifikasi manual (mengembalikan `403 Forbidden` dengan pesan agar perubahan dilakukan di ProdiSync lalu disinkronkan).
   - Sebagai gantinya, halaman `/sopi` menampilkan daftar SO, PI, dan Proficiency Levels secara *read-only* disertai tombol utama **"Sync dari ProdiSync"** (beserta informasi status koneksi & waktu sinkronisasi terakhir).
2. **Mekanisme Tombol "Sync dari ProdiSync" di `/sopi`:**
   - Admin dan KPS dapat menekan tombol **Sync dari ProdiSync** untuk prodi yang sedang dipilih.
   - Sistem memanggil `GET /proficiency-levels` dan `GET /prodi/{prodi}/so-pi`.
   - **Strategi Upsert Aman (Non-Destructive):**
     - Mengupdate `ProficiencyLevel` (level 1–5).
     - Untuk setiap SO dari API: jika `so_code` sudah ada di DB untuk prodi tersebut, update `so_description` dan `sort_order`; jika belum ada, buat baris `So` baru.
     - Untuk setiap PI di bawah SO tersebut: jika `pi_code` sudah ada, update `pi_description`, `proficiency_level`, dan `sort_order`; jika belum ada, buat baris `Pi` baru.
     - SO/PI lama yang tidak lagi ada di API ProdiSync akan dihapus jika belum dipakai oleh course mana pun; namun jika masih direferensikan oleh course yang sedang berjalan di RubriX, baris tersebut dipertahankan (dilaporkan sebagai *warning/kept* di ringkasan sinkronisasi agar histori nilai/course tidak rusak).
3. **Auto-Sync / Fallback saat Pembuatan Rubrik:**
   - Apabila prodi belum memiliki data SO-PI di database lokal saat wizard dibuka, atau setiap kali menarik rubrik MK dari ProdiSync, sistem otomatis melakukan sinkronisasi SO-PI prodi tersebut di latar belakang.

### 4.2 Pembuatan Rubrik Awal dari ProdiSync (Konsistensi Data RPS)
Ada **dua cara** yang disediakan bagi Dosen / KPS / Admin di halaman Dashboard (`/dashboard`):

1. **Cara 1 — Tombol / Tab "Ambil dari ProdiSync" (Recommended Workflow):**
   - Di sebelah tombol `+ Create Rubric` dan `Upload Course JSON`, ditambahkan tombol **`Ambil dari ProdiSync`** (atau integrasi langsung di Step 1 Wizard `+ Create Rubric` melalui fitur *"Pilih MK dari ProdiSync"*).
   - Ketika diklik, muncul modal **Katalog Mata Kuliah ProdiSync**:
     - Filter **Program Studi** (otomatis terisi prodi user untuk KPS/Dosen, bisa diganti), **Tahun Ajaran** (default TA aktif dari `/prodi`, mis. `2026/2027 Ganjil`), dan **Pencarian Kode/Nama MK**.
     - Menampilkan daftar MK yang memiliki RPS (`approved`) dari endpoint `/prodi/{kode}/matakuliah` atau `/rubrik-courses`, lengkap dengan *badge* jumlah CPL, SKS, semester, dan indikator apakah MK tersebut sudah ada di RubriX untuk semester tersebut.
   - Saat user memilih salah satu MK dan klik **"Gunakan untuk Buat Rubrik"**:
     - Backend menarik data terbaru SO-PI prodi terkait (memastikan SO & PI ter-upsert di DB lokal) dan menarik `GET /prodi/{kode}/matakuliah/{kode_mk}/rubrik`.
     - Frontend membuka **Wizard Pembuatan Rubrik** dengan seluruh data dari ProdiSync (`course_code`, `course_name`, `sks`, `semester`, `study_program`, `is_pbl`, `target_attainment`, `cpls` beserta `so_codes` & `pi_codes`, serta `categories`, `components`, `weight`, dan `criteria`).
     - Field identitas MK & daftar CPL/SO yang berasal dari RPS dikunci (*read-only* seperti mode upload JSON) agar **100% konsisten dengan ProdiSync**, sementara dosen diarahkan ke **Step 3 (Komponen & Pemetaan CPL/PI)** untuk memetakan sub-komponen ke CPL & PI yang diizinkan oleh RPS tersebut, meninjau bobot (Step 4) serta kriteria (Step 5), lalu menyimpan Course.

2. **Cara 2 — Pembuatan Manual (`+ Create Rubric`) & Upload JSON Tetap Dipertahankan:**
   - Untuk program studi yang belum datanya masuk ke ProdiSync (atau pembuatan rubrik eksperimental/non-RPS), tombol `+ Create Rubric` manual dan `Upload Course JSON` tetap berfungsi seperti semula.

---

## 5. Task Breakdown Implementasi

### Fase 1: Konfigurasi & Klien REST API ProdiSync (`modules/prodisync.py`)
- [x] **Task 1.1 — Konfigurasi Environment (`.env`, `.env.example`, `config.py`):**
  - Tambahkan variabel konfigurasi di `config.py`:
    - `PRODISYNC_BASE_URL = os.environ.get("RKS_PRODISYNC_BASE_URL", "https://rks.polibatam.ac.id/prodisync/prodisync/api/v1")`
    - `PRODISYNC_API_KEY = os.environ.get("RKS_PRODISYNC_API_KEY", "")`
    - `PRODISYNC_TIMEOUT = int(os.environ.get("RKS_PRODISYNC_TIMEOUT", 15))`
  - Simpan API key `psk_78f3c7e6_9slkgYimf2VVcY2KNHrxPRdxUKKtxmFC9bp6jSaxaVU` ke `.env` lokal dan dokumentasikan format placeholder-nya di `.env.example`.
- [x] **Task 1.2 — Pembuatan Service Client `modules/prodisync.py`:**
  - Gunakan `urllib.request` / `urllib.parse` (stdlib Python) sehingga tidak menambah *dependency* eksternal yang rawan konflik, dilengkapi penanganan error HTTP, timeout, dan decoding JSON (`ProdiSyncError`).
  - Buat peta konversi kode prodi RubriX $\leftrightarrow$ ProdiSync (`RUBRIX_TO_PRODISYNC_PRODI` dan `PRODISYNC_TO_RUBRIX_PRODI`, misalnya `D4-TP` $\leftrightarrow$ `TP`, `D4-TRM` $\leftrightarrow$ `TRM`, `RKS` $\leftrightarrow$ `RKS`).
  - Implementasikan fungsi-fungsi klien:
    - `ping()` $\rightarrow$ `GET /ping`
    - `fetch_prodi_list()` $\rightarrow$ `GET /prodi` (mengembalikan daftar prodi & `tahun_ajaran_aktif`)
    - `fetch_proficiency_levels()` $\rightarrow$ `GET /proficiency-levels`
    - `fetch_so_pi(study_program)` $\rightarrow$ `GET /prodi/{kode}/so-pi`
    - `fetch_matakuliah(study_program, rps_status="approved", ta=None, semester=None)` $\rightarrow$ `GET /prodi/{kode}/matakuliah`
    - `fetch_matakuliah_rubrik(study_program, kode_mk, ta=None)` $\rightarrow$ `GET /prodi/{kode}/matakuliah/{kode_mk}/rubrik`
    - `fetch_rubrik_courses(study_program, rps_status="approved", ta=None, semester=None)` $\rightarrow$ `GET /prodi/{kode}/rubrik-courses`

### Fase 2: Sinkronisasi Master SO-PI & Proficiency Levels
- [x] **Task 2.1 — Fungsi Upsert SO-PI di `modules/so_pi.py` (atau `modules/prodisync.py`):**
  - Buat fungsi `sync_so_pi_from_prodisync(study_program)`:
    1. Ambil data `/prodi/{kode}/so-pi` dari ProdiSync.
    2. Upsert `ProficiencyLevel` 1–5 jika ada di payload.
    3. Upsert daftar `So` dan `Pi` untuk `study_program` (gunakan kode prodi RubriX di tabel `so_pis.study_program` agar konsisten dengan data user & course di RubriX).
    4. Jika ada SO/PI di DB lokal yang tidak ada di API: cek `so_references` / `pi_references`. Jika tidak dipakai oleh course mana pun, hapus; jika masih dipakai, pertahankan dan catat di laporan hasil sync.
    5. Kembalikan ringkasan: `{so_created, so_updated, pi_created, pi_updated, kept_referenced}`.
- [x] **Task 2.2 — Endpoint Backend Sinkronisasi & Kunci Read-Only SO-PI (`modules/blueprints/sopi.py`):**
  - Tambahkan endpoint `POST /sopi/api/sync`:
    - Menerima `{"study_program": "RKS"}`.
    - Memeriksa hak akses dengan `_require_admin_or_kps()` dan `_check_program()`.
    - Memanggil `sync_so_pi_from_prodisync(program)` dan mengembalikan statistik hasil sinkronisasi beserta data SO-PI terbaru.
  - Tambahkan endpoint `GET /sopi/api/prodisync-status` untuk mengecek koneksi `/ping` dan daftar prodi yang terdaftar di ProdiSync (`/prodi`).
  - Kunci endpoint mutasi manual (`POST/PUT/DELETE` pada `/sopi/api/so`, `/sopi/api/pi`, dan `PUT /sopi/api/levels`) menjadi *read-only* (kembalikan respons `403` bahwa data SO-PI dikelola terpusat di ProdiSync dan hanya dapat diperbarui melalui sinkronisasi).
- [x] **Task 2.3 — UI Read-Only & Tombol Sync di Halaman Manage SO-PI (`templates/sopi.html`):**
  - Ubah halaman `/sopi` menjadi **Read-Only**: sembunyikan/hapus tombol `Add SO`, `+ Tambah PI`, ikon `Edit` / `Delete` pada SO & PI, serta ubah modal `Proficiency Levels` menjadi tampilan *read-only* (tanpa tombol Save).
  - Tambahkan banner informasi bahwa sumber data SO-PI terhubung dengan **ProdiSync** dan tambahkan tombol utama **"Sync dari ProdiSync"** di `.head-actions`.
  - Tampilkan indikator *loading* saat proses tarik data berlangsung dan notifikasi *toast* berisi hasil sinkronisasi (mis. *"Sinkronisasi RKS berhasil: 11 SO, 55 PI disinkronkan dari ProdiSync"*).

### Fase 3: Normalisasi & Backend Pembuatan Rubrik Awal dari ProdiSync
- [x] **Task 3.1 — Normalisasi Payload Rubrik MK ProdiSync (`normalize_prodisync_rubrik`):**
  - Buat fungsi normalisasi di `modules/prodisync.py` yang mengubah payload `GET /prodi/{kode}/matakuliah/{kode_mk}/rubrik` menjadi struktur standar wizard RubriX:
    - Konversi `study_program` ke kode prodi standar RubriX.
    - Pastikan `sks` minimal bernilai `1` (atau pertahankan nilai asli dengan fallback default `3` jika `0` di wizard agar tidak gagal validasi).
    - Pada setiap item `cpls`:
      - Jika `assessment_rubric` bernilai `null` atau kosong, tetapi `pi_codes` atau `so_pi_pairs` tersedia, bangun peta PI yang valid (`allowed_pis` atau struktur `assessment_rubric` placeholder berbasis `pi_codes`) sehingga wizard Step 3 tetap membatasi pilihan PI hanya pada PI yang ditetapkan RPS untuk CPL tersebut!
      - Pertahankan `so_pi_pairs` dan `pi_codes` pada objek CPL.
- [x] **Task 3.2 — Update Validasi CPL–PI di `modules/rubric_builder.py` & `modules/validation.py`:**
  - Perbarui `build_rubric_from_wizard()` dan `validate_course_json()` agar selain memeriksa `cpl.get("assessment_rubric")`, juga mengenali `cpl.get("pi_codes")` dan `cpl.get("so_pi_pairs")` saat memvalidasi bahwa seluruh PI dari RPS telah dipetakan ke komponen rubrik.
- [x] **Task 3.3 — Endpoint Proxy Katalog & Detail Rubrik ProdiSync (`modules/blueprints/courses.py`):**
  - `GET /api/prodisync/courses`:
    - Query params: `program` (default prodi user atau `RKS`), `ta` (opsional), `semester` (opsional), `rps_status` (default `approved`).
    - Memanggil `fetch_matakuliah()` (atau `fetch_rubrik_courses()`), lalu menandai setiap MK dengan flag `already_exists` (apakah `Course` dengan `course_code` dan `semester` / `tahun_ajaran` tersebut sudah ada di DB RubriX, beserta `existing_course_id` dan `owner_name`).
  - `GET /api/prodisync/courses/<kode_mk>/rubrik`:
    - Query params: `program`, `ta` (opsional).
    - Otomatis menjalankan `sync_so_pi_from_prodisync(program)` terlebih dahulu apabila SO-PI prodi tersebut belum ada atau ada kode SO/PI baru di MK tersebut, sehingga tidak akan terjadi error *"kode PI tidak sesuai dengan master SO-PI"*.
    - Memanggil `fetch_matakuliah_rubrik(program, kode_mk, ta)` dan mengembalikan payload yang sudah dinormalisasi siap pakai untuk wizard.

### Fase 4: Integrasi UI Pembuatan Rubrik Awal di Dashboard (`templates/index.html`)
- [x] **Task 4.1 — Modal & Tombol "Ambil dari ProdiSync" di Dashboard:**
  - Tambahkan tombol **"Ambil dari ProdiSync"** di bagian header halaman Courses (`/dashboard`) serta tautan pintas di dalam Step 1 Wizard.
  - Buat modal `#prodisync-modal` yang berisi:
    - Pilihan **Program Studi**, informasi **Tahun Ajaran Aktif**, dan kotak pencarian kode/nama MK.
    - Tabel / daftar mata kuliah dari ProdiSync yang berstatus RPS `approved` (menampilkan Kode MK, Nama MK, SKS, Semester/TA, jumlah CPL, chip SO-PI).
    - Jika MK belum ada di RubriX: tombol **"Buat Rubrik"** (memuat payload rubrik MK dari `/api/prodisync/courses/<kode_mk>/rubrik` lalu membuka Wizard).
    - Jika MK sudah ada di RubriX pada semester tersebut: badge **"Sudah Ada"** (dengan opsi membuka/mengedit course yang sudah ada jika user berhak).
- [x] **Task 4.2 — Penyesuaian Wizard untuk Mode ProdiSync (`openWizardFromProdiSync`):**
  - Gunakan alur yang serupa dengan `openWizardFromUpload(data)` namun dioptimalkan untuk data ProdiSync:
    - Step 1 (Course Info) & Step 2 (CPL & SO) otomatis terisi dari data RPS ProdiSync dan bersifat *read-only* (kecuali *Target Attainment* atau jika SKS dari API bernilai `0` maka input SKS dibuka agar dosen bisa mengisi SKS yang benar).
    - Di Step 3 (Komponen & Pemetaan CPL/PI), perbarui `renderPiOptions()` agar mendukung daftar PI dari `cpl.pi_codes` / `cpl.so_pi_pairs` selain `cpl.assessment_rubric`. Dengan demikian, untuk MK seperti `MKU004` (yang `assessment_rubric`-nya `null` tetapi punya `pi_codes: ["PI-09.4"]`), checkbox PI tetap muncul secara akurat sesuai RPS!
    - Langsung arahkan fokus user ke **Step 3** (dengan navigasi tab Step 1–5 yang tetap bisa diklik untuk meninjau info MK, CPL, bobot, dan kriteria yang ditarik dari ProdiSync).

### Fase 5: Pengujian & Dokumentasi
- [x] **Task 5.1 — Unit & Integration Testing (`tests/`):**
  - Test koneksi & parser `modules/prodisync.py` (menggunakan mock response sesuai payload asli `/prodi`, `/so-pi`, `/matakuliah`, `/rubrik`).
  - Test `sync_so_pi_from_prodisync()` untuk memastikan *upsert* SO & PI berjalan idempoten dan tidak merusak relasi course yang sudah ada.
  - Test alur pembuatan course dari payload ProdiSync baik untuk MK dengan `assessment_rubric` terisi (`RKS-532`) maupun MK dengan `assessment_rubric: null` tetapi memiliki `pi_codes` (`MKU004`) serta MK dengan `sks: 0` (`RKS-405`).
- [x] **Task 5.2 — Update Dokumentasi (`rubric-project.md` & `.env.example`):**
  - Dokumentasikan variabel environment ProdiSync API dan endpoint baru (`/sopi/api/sync`, `/api/prodisync/courses`, `/api/prodisync/courses/<kode>/rubrik`).

---

## 6. Diagram Alur Pembuatan Rubrik Awal (ProdiSync $\rightarrow$ RubriX)

```
[Dosen / KPS]
     │
     ▼  Klik "Ambil dari ProdiSync" di Dashboard
[Modal Katalog MK ProdiSync]
     │  GET /api/prodisync/courses?program=RKS
     │  (Fetch GET /prodi/RKS/matakuliah dari ProdiSync + cek status di DB RubriX)
     ▼
[Pilih MK (mis. RKS-532 / MKU004)]
     │  GET /api/prodisync/courses/RKS-532/rubrik?program=RKS
     ├──► 1. Auto-sync Master SO-PI prodi RKS (GET /prodi/RKS/so-pi -> Upsert DB RubriX)
     └──► 2. Ambil & Normalisasi Rubrik MK (GET /prodi/RKS/matakuliah/RKS-532/rubrik)
     ▼
[Wizard Create Rubric (Pre-filled & Konsisten dengan RPS)]
     ├── Step 1: Info MK (Kode, Nama, SKS, Semester, Prodi) -> Read-only (Konsisten RPS)
     ├── Step 2: Daftar CPL & Pemetaan SO -> Read-only (Konsisten RPS)
     ├── Step 3: Sub-Komponen Asesmen (dari RPS) -> Dosen memetakan tiap komponen ke CPL & PI RPS
     ├── Step 4: Bobot (%) & Status PBL (Pre-filled dari RPS, divalidasi total = 100%)
     └── Step 5: Kriteria Level 1-5 (Pre-filled dari RPS, dapat disesuaikan jika perlu)
     │
     ▼  Klik "+ Create Course" (POST /api/courses/create)
[Tersimpan di DB RubriX & Siap Digunakan untuk Manage Class / Penilaian]
```
