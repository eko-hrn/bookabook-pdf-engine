# Bookabook PDF Engine

Sistem otomasi pemrosesan dan ekstraksi PDF buku anak beresolusi tinggi (300 DPI) menjadi halaman cropped JPEG siap cetak dan showcase interaktif web.

---

## Daftar Isi

- [Deskripsi Proyek](#deskripsi-proyek)
- [Arsitektur Sistem](#arsitektur-sistem)
- [Fitur Utama](#fitur-utama)
- [Prasyarat Sistem](#prasyarat-sistem)
- [Instalasi](#instalasi)
  - [1. Backend Setup (Python)](#1-backend-setup-python)
  - [2. Frontend Setup (React + Vite)](#2-frontend-setup-react--vite)
- [Konfigurasi Environment](#konfigurasi-environment)
- [Migrasi Database (Supabase PostgreSQL)](#migrasi-database-supabase-postgresql)
- [Menjalankan Aplikasi](#menjalankan-aplikasi)
- [Menjalankan Automated Tests](#menjalankan-automated-tests)
- [Keamanan & Manajemen Credential](#keamanan--manajemen-credential)
- [Struktur Direktori](#struktur-direktori)
- [Lisensi](#lisensi)

---

## Deskripsi Proyek

**Bookabook PDF Engine** dirancang khusus untuk memproses file PDF buku anak (baik spread maupun sheet imposition 4-up) secara deterministik tanpa distorsi geometri:
- Mengekstrak lembar cover spread menjadi **`COVER.jpg`** (sisi kanan spine) dan **`BACKCOVER.jpg`** (sisi kiri spine) dengan pemisahan spine otomatis tanpa memotong artwork utama.
- Membagi lembar imposition 4-up menjadi halaman interior berurutan: **`PAGE-01.jpg`** sampai **`PAGE-N.jpg`**.
- Menerapkan **kompresi adaptif JPEG 300 DPI** dengan batas ketat ukuran file:
  - `COVER.jpg`: Maksimal **400 KB** (409,600 bytes).
  - `PAGE-01.jpg` s/d `PAGE-N.jpg`: Maksimal **400 KB** (409,600 bytes) per halaman.
  - `BACKCOVER.jpg`: Maksimal **1 MB** (1,048,576 bytes) untuk mempertahankan ketajaman foto anak.
- Menyimpan metadata ke **Supabase PostgreSQL** dan binary JPG ke **Supabase Storage** (public bucket) dengan pengiriman langsung melalui public CDN ke browser frontend tanpa proxy backend.

---

## Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        USER BROWSER / CLIENT                            │
│  - React 18 + TypeScript + Vite + Tailwind CSS                          │
│  - Book Spread Viewer (Cover standalone, interior Q1+Q2 / Q3+Q4)        │
│  - Full Sheet Inspection, Thumbnail Navigation & ZIP Downloader         │
└──────────────┬──────────────────────────────────────────▲───────────────┘
               │                                          │
       REST API Requests                         Direct CDN Image Fetch
       (Metadata, Process, Save)                 (Supabase Storage Public URL)
               │                                          │
               ▼                                          │
┌──────────────────────────────────────────┐              │
│       FASTAPI BACKEND SERVICE            │              │
│  - Python 3.11 + PyMuPDF + Pillow        │              │
│  - Deterministic Layout Classifier       │              │
│  - Precise Spine Split & Crop Engine     │              │
│  - Adaptive JPEG Compressor (300 DPI)    │              │
│  - Storage Adapter Layer                 │              │
│    ├─ SupabaseStorageAdapter (Prod)      │              │
│    ├─ LocalStorageAdapter (Dev/Test)     │              │
│    └─ CloudflareR2Adapter (Future)       │              │
└──────────────┬───────────────────────────┘              │
               │                                          │
        Persist Metadata                           Upload JPG Artifacts
        via Session Pooler                         via Service Role Key
               │                                          │
               ▼                                          ▼
┌─────────────────────────────┐            ┌──────────────────────────────┐
│    SUPABASE POSTGRESQL      │            │       SUPABASE STORAGE       │
│  - Table: `books`           │            │  - Bucket: `bookabook-images`│
│  - Table: `book_pages`      │            │  - Public read CDN access    │
│  - Stored object_key & sha  │            │  - Zero local disk residue   │
└─────────────────────────────┘            └──────────────────────────────┘
```

---

## Fitur Utama

1. **Deterministic Layout Classification**: Otomatis mengenali layout `COVER_SPREAD`, `IMPOSITION_4UP`, dan `SINGLE_PAGE` berdasarkan spesifikasi `audit/Layout_Classifier_Specification_v1.3.4.md`.
2. **Pemisahan Spine Presisi**:
   - Cover depan diambil murni dari sisi kanan area spine.
   - Backcover diambil murni dari sisi kiri area spine.
   - Spine dieksklusi secara presisi sehingga tidak masuk ke crop cover maupun backcover.
3. **Adaptive JPEG Compression**:
   - Dimulai dari kualitas awal (Q95) pada resolusi **300 DPI RGB**.
   - Menurunkan kualitas secara adaptif jika ukuran file melebihi limit.
   - Memastikan ketajaman teks, ilustrasi, garis gambar, dan foto wajah anak tetap optimal.
4. **Dual Storage Architecture**:
   - `supabase`: Mengunggah ke Supabase Storage secara paralel/konkuren (8 worker). Browser mengambil gambar langsung dari CDN.
   - `local`: Penyimpanan filesystem lokal untuk pengembangan offline.
   - `r2`: Adapter siap pakai untuk migrasi Cloudflare R2 di masa depan.
5. **Showcase Catalog & Book Spread Viewer**:
   - Tampilan katalog `/books` responsif.
   - Reader `/books/:id` menampilkan Cover depan mandiri, spread interior dua halaman berdampingan (Q1+Q2 dan Q3+Q4), navigasi thumbnail horizontal, serta tombol unduh ZIP.

---

## Prasyarat Sistem

- **Python**: Versi `3.11` atau lebih baru.
- **Node.js**: Versi `18.0.0` atau lebih baru (`npm` v9+).
- **Git**: Versi 2.30+.
- **Akun Supabase**: Proyek Supabase dengan database PostgreSQL dan Storage bucket `bookabook-images`.

---

## Instalasi

### 1. Backend Setup (Python)

Clone repository dan buat virtual environment:

```bash
git clone https://github.com/eko-hrn/bookabook-pdf-engine.git
cd bookabook-pdf-engine

# Buat virtual environment
python -m venv .venv

# Aktivasi virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat
# Linux/macOS:
source .venv/bin/activate

# Install dependensi backend
pip install -r requirements.txt
```

### 2. Frontend Setup (React + Vite)

Buka direktori `frontend` dan pasang paket npm:

```bash
cd frontend
npm install
cd ..
```

---

## Konfigurasi Environment

### Backend `.env`
Salin template konfigurasi `.env.example` ke file `.env` di root project:

```bash
cp .env.example .env
```

Buka `.env` dan sesuaikan nilainya:

```ini
# Supabase PostgreSQL Database URL (Gunakan Session Pooler port 6543)
DATABASE_URL="postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require"

# Storage Backend
STORAGE_BACKEND="supabase"

# Supabase Storage Configuration
SUPABASE_URL="https://<project-ref>.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="eyJhbGciOi..."
SUPABASE_STORAGE_BUCKET="bookabook-images"

# Batas Upload & Target DPI
MAX_UPLOAD_SIZE_BYTES=524288000
PRODUCTION_EXPORT_DPI=300
```

> **PENTING**: Jangan pernah melakukan commit atau membagikan file `.env` yang memuat credential asli.

### Frontend `frontend/.env`
Salin template frontend:

```bash
cd frontend
cp .env.example .env
cd ..
```

Isi default pada `frontend/.env`:
```ini
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_MAX_UPLOAD_SIZE_BYTES=52428800
```

---

## Migrasi Database (Supabase PostgreSQL)

Skema database tersimpan di `migrations/001_create_books_tables.sql` yang membuat dua tabel:
- `books`: Menyimpan metadata katalog buku (judul, pengarang, tahun, sponsor, dsb).
- `book_pages`: Menyimpan informasi halaman, dimensi piksel, DPI, ukuran file, SHA-256, dan `object_key`.

Backend secara otomatis menjalankan migrasi ini secara idempoten saat startup melalui `_get_engine_singleton()`. Anda juga dapat menjalankannya langsung melalui SQL Editor di Supabase Dashboard:

1. Buka Supabase Dashboard > **SQL Editor**.
2. Buka file `migrations/001_create_books_tables.sql`.
3. Jalankan query untuk memastikan tabel `books` dan `book_pages` terbentuk.

---

## Menjalankan Aplikasi

### Menjalankan Backend API

Dari root direktori dengan `.venv` aktif:

```bash
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

- API Base URL: `http://127.0.0.1:8000`
- API Health Check: `http://127.0.0.1:8000/api/health`
- Swagger Interactive Docs: `http://127.0.0.1:8000/docs`

### Menjalankan Frontend Web

Buka terminal baru di direktori `frontend`:

```bash
cd frontend
npm run dev
```

- Web UI: `http://localhost:5173`
- Create Book: `http://localhost:5173/books/new`
- Showcase Catalog: `http://localhost:5173/books`

---

## Menjalankan Automated Tests

### 1. Backend Pytest
Menjalankan seluruh unit test, layout calculator, JPEG compressor, API endpoints, dan storage adapter:

```bash
pytest -v
```

### 2. Frontend Vitest
Menjalankan seluruh unit dan integration test frontend React:

```bash
cd frontend
npm test -- --run
```

### 3. Frontend Production Build Check
Memastikan TypeScript compilation dan Vite production bundle bebas error:

```bash
cd frontend
npm run build
```

---

## Keamanan & Manajemen Credential

1. **Prinsip Least-Privilege & Isolasi Key**:
   - `SUPABASE_SERVICE_ROLE_KEY` hanya tersimpan di backend `.env` untuk keperluan upload file ke Storage.
   - Frontend **tidak pernah** menerima atau mengekspos Service Role Key.
   - Frontend memuat gambar publik langsung via URL Supabase Storage CDN (`https://<project-ref>.supabase.co/storage/v1/object/public/bookabook-images/...`).
2. **Pengecualian Git (.gitignore)**:
   - File `.env` dan seluruh variannya diabaikan oleh Git.
   - File PDF produksi (`data/*.pdf`) dikecualikan dari Git tracking untuk mencegah kebocoran materi terbitan berukuran besar.
   - Seluruh direktori runtime lokal (`data/storage/`, `data/uploads/`, `data/previews/`, `data/*.db`) tidak dilacak oleh Git.
3. **Template Aman**:
   - File `.env.example` dan `frontend/.env.example` disediakan dengan seluruh nilai rahasia dalam keadaan string kosong (`""`) sebagai acuan konfigurasi.

---

## Struktur Direktori

```
bookabook-pdf-engine/
├── app/
│   ├── api/                  # FastAPI router, schemas, dependencies, service layer
│   ├── crop/                 # Geometry extractor, crop calculator, adaptive compressor
│   ├── db/                   # SQLAlchemy models, migrations runner, repository
│   └── storage/              # Storage adapters (Supabase Storage, Local, Cloudflare R2)
├── audit/                    # Spesifikasi klasifikasi layout & UI reference mockups
├── data/                     # Direktori runtime lokal (diabaikan oleh git)
├── frontend/
│   ├── src/                  # React components, pages, hooks, API client
│   ├── public/               # Static assets & icons
│   └── package.json          # Frontend dependencies & scripts
├── migrations/               # DDL SQL migration files (PostgreSQL)
├── tests/
│   ├── api/                  # API endpoints integration tests
│   ├── crop/                 # Cropping, calculator, compressor unit tests
│   ├── db/                   # Database repository tests
│   └── storage/              # Supabase Storage adapter tests
├── .env.example              # Template konfigurasi environment backend
├── .gitignore                # Aturan pengecualian Git
├── LICENSE                   # Lisensi MIT
├── requirements.txt          # Dependensi Python backend
└── README.md                 # Dokumentasi utama proyek
```

---

## Lisensi

Proyek ini dilisensikan di bawah [MIT License](LICENSE).

