# 📋 Form Data Peserta — Streamlit App

Aplikasi form pengumpulan data peserta berbasis Streamlit dengan integrasi **Google Sheets** dan **Google Drive**. Validasi file PNG ketat untuk Tanda Tangan digital.

---

## ✅ Fitur Utama

- Form data peserta lengkap (13 field)
- Validasi PNG ketat: ekstensi + MIME type + magic bytes
- Upload TTD ke Google Drive, nama file otomatis
- Simpan semua data ke Google Sheets dengan timestamp
- Link Drive TTD masuk otomatis ke kolom spreadsheet
- Proteksi double-submit dalam satu sesi
- Siap deploy ke Streamlit Cloud

---

## 📁 Struktur Project

```
project/
├── app.py                    # Aplikasi utama
├── requirements.txt          # Dependensi Python
├── .streamlit/
│   └── secrets.toml          # Kredensial (jangan di-commit!)
├── .gitignore
└── README.md
```

### `.gitignore` yang disarankan
```
.streamlit/secrets.toml
*.json
__pycache__/
.env
```

---

## 🔧 Setup Google Cloud (Langkah demi Langkah)

### 1. Buat Google Cloud Project

1. Buka [console.cloud.google.com](https://console.cloud.google.com)
2. Klik **"Select a project"** → **"New Project"**
3. Beri nama project (misal: `form-peserta`) → **Create**

---

### 2. Enable Google Sheets API & Google Drive API

1. Di Google Cloud Console, buka **"APIs & Services" → "Library"**
2. Cari **"Google Sheets API"** → klik → **Enable**
3. Cari **"Google Drive API"** → klik → **Enable**

---

### 3. Buat Service Account

1. Buka **"APIs & Services" → "Credentials"**
2. Klik **"+ Create Credentials" → "Service Account"**
3. Isi nama (misal: `streamlit-form`) → **Create and Continue**
4. Role: pilih **"Editor"** → **Continue** → **Done**
5. Klik service account yang baru dibuat
6. Tab **"Keys"** → **"Add Key" → "Create new key"**
7. Pilih format **JSON** → **Create**
8. File JSON otomatis terunduh — **simpan baik-baik, ini rahasia!**

---

### 4. Share Google Sheets ke Service Account

1. Buka file JSON service account → salin nilai `client_email`
   (contoh: `streamlit-form@nama-project.iam.gserviceaccount.com`)
2. Buka **Google Spreadsheet** Anda
3. Klik **Share** (pojok kanan atas)
4. Paste email service account → pilih role **"Editor"** → **Send**

> 💡 Buat tab baru di spreadsheet bernama **"Data Peserta"** (atau sesuai `sheet_name` di secrets.toml)

---

### 5. Share Folder Google Drive ke Service Account

1. Buka **Google Drive** → buat folder baru (misal: `TTD Peserta`)
2. Klik kanan folder → **Share**
3. Paste email service account → pilih role **"Editor"** → **Send**
4. Salin **ID folder** dari URL:
   ```
   https://drive.google.com/drive/folders/FOLDER_ID_INI
   ```

---

### 6. Siapkan secrets.toml

Buka file `service-account-key.json` yang diunduh, lalu isi `.streamlit/secrets.toml`:

```toml
[google_sheets]
spreadsheet_id = "ID_SPREADSHEET_ANDA"
sheet_name     = "Data Peserta"

[google_drive]
folder_id = "ID_FOLDER_DRIVE_ANDA"

[gcp_service_account]
type                        = "service_account"
project_id                  = "isi dari file JSON"
private_key_id              = "isi dari file JSON"
private_key                 = "isi dari file JSON (termasuk -----BEGIN...-----)"
client_email                = "isi dari file JSON"
client_id                   = "isi dari file JSON"
auth_uri                    = "https://accounts.google.com/o/oauth2/auth"
token_uri                   = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url        = "isi dari file JSON"
universe_domain             = "googleapis.com"
```

> ⚠️ **Pastikan** nilai `private_key` menyertakan newline `\n` dengan benar. Salin persis dari file JSON.

---

## 🚀 Deployment ke Streamlit Cloud

### Langkah:

1. **Push project ke GitHub** (pastikan `secrets.toml` ada di `.gitignore`!)
   ```bash
   git init
   git add app.py requirements.txt README.md .gitignore
   git commit -m "initial commit"
   git remote add origin https://github.com/username/nama-repo.git
   git push -u origin main
   ```

2. **Buka** [share.streamlit.io](https://share.streamlit.io) → login dengan akun GitHub

3. Klik **"New app"**

4. Pilih repository dan branch → set **Main file path**: `app.py`

5. Klik **"Advanced settings"** → tab **"Secrets"**

6. **Paste seluruh isi `secrets.toml`** ke dalam kotak Secrets

7. Klik **"Deploy!"**

8. Tunggu build selesai (biasanya 1–3 menit) → app siap diakses via URL publik

---

## 🗂 Struktur Kolom Google Sheets (otomatis dibuat)

| Kolom | Keterangan |
|-------|-----------|
| Timestamp | Waktu submit (YYYY-MM-DD HH:MM:SS) |
| Email Address | Email peserta |
| Regional Corpu | Regional peserta |
| Batch | Batch pelatihan |
| Nama Lengkap | Nama peserta |
| Personal Number | Nomor pegawai |
| Unit Kerja | Unit/cabang kerja |
| Link Tanda Tangan | URL file PNG di Google Drive |
| Alat Bantu Pendeteksi Keaslian Uang | Pilihan dropdown |
| Keterangan Alat Bantu Lainnya | Isi jika pilih "Lainnya" |
| Mesin Hitung Uang | Pilihan dropdown |
| Keterangan Mesin Hitung Lainnya | Isi jika pilih "Lainnya" |
| Komputer dan Printer | Pilihan dropdown |
| Keterangan Komputer Printer Lainnya | Isi jika pilih "Lainnya" |

---

## ⚙️ Menjalankan Secara Lokal (Opsional)

```bash
# 1. Clone repo
git clone https://github.com/username/nama-repo.git
cd nama-repo

# 2. Install dependensi
pip install -r requirements.txt

# 3. Buat file secrets
mkdir -p .streamlit
# Isi .streamlit/secrets.toml sesuai panduan di atas

# 4. Jalankan
streamlit run app.py
```

---

## 🔄 Alur Kerja Aplikasi

```
Peserta buka form
        ↓
Isi semua field + upload file PNG TTD
        ↓
Klik "Submit Data"
        ↓
Validasi semua field (client & server side)
        ↓
Validasi PNG ketat (ekstensi + MIME + magic bytes + ukuran)
        ↓
[Jika ada error] → tampilkan pesan error, berhenti
        ↓
[Jika valid] → upload PNG ke Google Drive folder
        ↓
Dapat link shareable file TTD
        ↓
Simpan semua data + link TTD ke Google Sheets
        ↓
Tampilkan pesan sukses ✅
```

---

## 🛠 Kustomisasi Dropdown

Edit bagian ini di `app.py` untuk mengubah pilihan dropdown:

```python
DROPDOWN_ALAT_BANTU      = ["-- Pilih --", "Tidak Ada", "Glory", "Dynamic", "Secure", "Lainnya"]
DROPDOWN_MESIN_HITUNG    = ["-- Pilih --", "Tidak Ada", "Glory", "Dynamic", "NCL", "Lainnya"]
DROPDOWN_KOMPUTER_PRINTER = ["-- Pilih --", "Tidak Ada", "PC + Printer", "Laptop + Printer", "Printer Only", "Lainnya"]
```

---

*Dibuat dengan ❤️ menggunakan Streamlit + Google Workspace API*
