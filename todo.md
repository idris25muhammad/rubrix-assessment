# TODO — Perubahan Role, Assign Kelas, Soal Asesmen & Statistik

Referensi arsitektur: [rubric-project.md](rubric-project.md)

## Keputusan (hasil klarifikasi)

| Topik | Keputusan |
|---|---|
| Role final | `admin` (kajur, akses penuh), `kps` (pengganti `tim_kurikulum`, per prodi), `lecturer` (dosen) |
| Angkatan | Dari **prefix NIM**: digit ke-4–5 = tahun (`33123xxxx` → 2023) |
| Filter statistik | Bisa per **Angkatan** atau per **Tahun Ajaran** |
| Akun admin | `admin@polibatam.ac.id`, `kajur-if@polibatam.ac.id` (password default = email) |
| KPS & role admin | KPS **tidak boleh** membuat/mengubah user menjadi admin |
| Soal Asesmen | Disimpan **per kelas** (tombol di tiap baris kelas) |
| Dosen yang di-assign ke kelas | Hanya kelas itu: edit kelas, input nilai, import/export, portfolio kelasnya; rubrik read-only; **tidak bisa hapus** |
| Hak KPS | Lihat semua mata kuliah di prodinya + edit; hapus hanya jika dia pembuatnya; tetap kelola SO-PI prodi & user |
| Dropdown dosen di Add Class | Semua akun (dosen, kps, admin) |
| Data lama `shared_with` | Diabaikan, kolom dihapus lewat migrasi |

## Matriks Hak Akses

| Aksi | admin | kps (prodi sendiri) | dosen pembuat (owner course) | dosen yang di-assign ke kelas |
|---|---|---|---|---|
| Lihat mata kuliah | semua | semua di prodinya | miliknya | mata kuliah dari kelas yang di-assign |
| Edit mata kuliah / rubrik | ✅ | ✅ | ✅ | ❌ (read-only) |
| Hapus mata kuliah | ✅ | hanya jika pembuat | ✅ | ❌ |
| Tambah kelas + pilih dosen | ✅ | ✅ | ✅ | ❌ |
| Edit kelas / nilai / import-export / Soal Asesmen | ✅ | ✅ | ✅ | ✅ hanya kelasnya |
| Hapus kelas | ✅ | hanya jika pembuat course | ✅ | ❌ |
| Portfolio kelas | ✅ | ✅ | ✅ | ✅ hanya kelasnya |
| Portfolio gabungan (combined) | ✅ | ✅ | ✅ | ❌ |
| Kelola user | ✅ semua | ✅ (prodinya) | ❌ | ❌ |
| Kelola SO-PI | ✅ semua prodi | ✅ prodinya | ❌ | ❌ |
| Statistik | semua / filter prodi | prodinya | — | — |
| Kartu statistik dashboard | semua | prodinya | mata kuliah miliknya + kelas yang di-assign | (sama) |

> Aturan hapus: yang boleh menghapus rubrik/mata kuliah hanya **pembuat awal** (`courses.owner_id`) — kecuali admin.

---

## 1. Role & Akun

- [x] Ganti konstanta `ROLE_TIM_KURIKULUM` → `ROLE_KPS = "kps"`, tambah `ROLE_ADMIN = "admin"` di `modules/auth.py`.
- [x] Buat helper terpusat (mis. `modules/permissions.py`): `is_admin`, `is_kps`, `can_view_course`, `can_edit_course`, `can_delete_course`, `can_view_class`, `can_edit_class`, `can_delete_class`, `scoped_courses_query(user)`. Ganti semua cek `user["role"] == "tim_kurikulum"` di `courses.py`, `data.py`, `sopi.py`, `users.py`, `dashboard.py`.
- [x] `role_required` mendukung banyak role (mis. `@role_required(ROLE_ADMIN, ROLE_KPS)`).
- [x] Migrasi data: `UPDATE users SET role='kps' WHERE role='tim_kurikulum'`.
- [x] Seeder: tambah 2 akun role `admin` — `admin@polibatam.ac.id` dan `kajur-if@polibatam.ac.id` (password default = email).
- [x] Halaman Users: opsi role = admin / kps / dosen; field `study_program` wajib untuk kps, opsional untuk dosen, kosong untuk admin.
- [x] KPS **tidak boleh** membuat user admin, mengubah role menjadi admin, maupun mengedit/menghapus akun admin (enforce di backend + sembunyikan opsi di UI).
- [x] Update label UI ("Tim Kurikulum" → "KPS", tambah "Admin") di navbar/template.

## 2. Assign Dosen via Add Class (hapus fitur Assign/Share)

- [x] Model `Class`: tambah `lecturer_id` (FK → `users.id`, nullable). Kolom teks `lecturer` di-drop (atau diisi otomatis dari nama user untuk kompatibilitas tampilan) — putuskan saat implementasi.
- [x] Hapus `Course.shared_with` + `get_shared_with()` (migrasi drop column).
- [x] Hapus endpoint `PUT /api/courses/<id>/share`, field `can_share`/`shared` di response, tombol & modal Assign di dashboard (template + JS).
- [x] Endpoint baru `GET /api/users/lecturers` (semua akun: id, nama, role) untuk dropdown.
- [x] Modal Add/Edit Class: ganti input teks lecturer → dropdown pilih **1** dosen (searchable bila memungkinkan).
- [x] `POST/PUT` class: validasi `lecturer_id` ada di tabel users.

## 3. Scoping Dashboard & Akses Data

- [x] `scoped_courses_query(user)`:
  - admin → semua
  - kps → `Course.study_program == user.study_program`
  - dosen → `Course.owner_id == user.id` **ATAU** course yang punya kelas dengan `lecturer_id == user.id`
- [x] Tabel dashboard menampilkan rubrik buatan sendiri + mata kuliah dari kelas yang di-assign (beri badge "Ditugaskan" untuk yang bukan milik sendiri).
- [x] Tombol edit/hapus di tabel dashboard mengikuti matriks (pakai flag `can_edit`, `can_delete` dari API).
- [x] Halaman Manage Class: dosen yang di-assign hanya melihat kelas miliknya; tombol hapus disembunyikan; Combined Portfolio disembunyikan.
- [x] Endpoint class (`save`, `import`, `export`, `portfolio`, `PUT`, `DELETE`) memakai helper permission — enforce di backend, bukan hanya UI.
- [x] Rubrik course untuk dosen assigned = read-only (blokir `PUT /api/courses/<id>` & upload ulang).

## 4. Soal Asesmen (per kelas)

- [x] Model `Class`: tambah kolom `soal_ats_teori`, `soal_ats_praktikum`, `soal_aas_teori`, `soal_aas_praktikum` (String URL, nullable) — atau 1 kolom JSON `assessment_links`.
- [x] Endpoint `GET/PUT /api/classes/<id>/assessment-links` (permission = `can_edit_class`). Validasi format URL (http/https, opsional cek domain Google Drive).
- [x] UI `/courses/<id>/classes`: tombol **Soal Asesmen** di tiap baris kelas → modal 4 input link + tombol buka link (ikon external) jika terisi; indikator jumlah link terisi (mis. 2/4).

## 5. Statistik per Angkatan

- [x] Fungsi `angkatan_from_nim(nim)`: digit ke-4–5 NIM = 2 digit tahun → `2000 + yy` (contoh `33123xxxx` → 2023). NIM tidak valid → "Tidak diketahui". Sertakan unit test.
- [x] Sumber **Tahun Ajaran**: cek apakah sudah ada field tahun ajaran (course/class). Jika belum, tambah `classes.academic_year` (mis. `2025/2026`, dipilih saat Add/Edit Class) + migrasi.
- [x] Statistik mendukung **2 mode filter**: per **Angkatan** (dari prefix NIM, gabungan lintas semester/mata kuliah) **atau** per **Tahun Ajaran** (dari kelas). Pilihan mode lewat toggle, lalu dropdown nilainya (`all` default).
- [x] Refactor `get_prodi_semester_statistics` → fungsi umum yang menerima filter (`study_program`, `group_by` = angkatan/tahun_ajaran, nilai filter, semester opsional).
- [x] API `/api/statistics`: parameter `mode` (`angkatan` | `tahun_ajaran`), `value`, `study_program`.
  - kps → `study_program` dipaksa = prodinya
  - admin → boleh `all` atau prodi tertentu
- [x] Endpoint daftar filter: angkatan tersedia, tahun ajaran tersedia, daftar prodi (admin).
- [x] Halaman `statistics.html`: toggle Angkatan/Tahun Ajaran + dropdown nilai; dropdown Prodi hanya untuk admin; chart perbandingan antar angkatan / antar tahun ajaran.
- [x] Akses halaman statistik: `@role_required(ROLE_ADMIN, ROLE_KPS)`.

## 6. Statistik Dashboard (kartu ringkasan)

- [x] `/api/dashboard` memakai `scoped_courses_query(user)`:
  - admin → semua
  - kps → prodinya
  - dosen → mata kuliah miliknya + kelas yang di-assign (untuk mata kuliah assigned, hitung hanya kelasnya)

## 7. SO-PI

- [x] `sopi.py`: admin boleh kelola semua prodi (pilih prodi), kps hanya prodinya.

## 8. Migrasi, Seeder & Dokumentasi

- [x] `flask db migrate -m "roles admin/kps, class lecturer_id, assessment links, drop shared_with"` → review → `flask db upgrade` (uji di MySQL & SQLite).
- [x] Update seeder (admin, kajur-if, kps) dan data contoh kelas dengan `lecturer_id`.
- [x] Update `rubric-project.md` (roles, API, fitur baru).

## 9. Testing

- [x] Login sebagai admin / kps / dosen owner / dosen assigned — verifikasi setiap baris matriks hak akses (UI + panggilan API langsung harus 403 bila tidak berhak).
- [x] Dosen assigned tidak bisa hapus course/kelas maupun edit rubrik.
- [x] Statistik: filter angkatan & prodi benar; kps tidak bisa mengakses prodi lain via parameter.
- [x] Soal Asesmen: simpan/ubah/kosongkan link; validasi URL.

## Pertanyaan Terbuka

- Tidak ada (semua sudah dikonfirmasi).
