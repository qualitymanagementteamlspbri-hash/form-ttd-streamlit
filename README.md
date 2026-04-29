# Streamlit Form Data Peserta + Validasi TTD PNG + Google Sheets + Google Drive

Project ini digunakan untuk mengumpulkan data peserta dengan ketentuan tanda tangan wajib format PNG. Data form masuk ke Google Sheets, sedangkan file tanda tangan tersimpan di Google Drive dan link-nya otomatis tercatat di spreadsheet.

## Fitur

- Validasi tanda tangan wajib PNG.
- Menolak JPG/JPEG/PDF/HEIC atau file yang hanya diganti ekstensi menjadi `.png`.
- Upload file tanda tangan ke Google Drive.
- Link Google Drive otomatis masuk ke Google Sheets.
- Anti-duplikat berdasarkan Personal Number.
- Retry otomatis untuk mengurangi risiko gagal karena rate limit sementara.
- Preview admin opsional.

## Struktur File

```text
streamlit_form_ttd_png/
├── app.py
├── requirements.txt
├── google_sheet_headers.txt
├── README.md
└── .streamlit/
    └── secrets.toml.example
```

## Persiapan Google Cloud

1. Buka Google Cloud Console.
2. Buat project baru atau gunakan project yang sudah ada.
3. Aktifkan API berikut:
   - Google Sheets API
   - Google Drive API
4. Buat Service Account.
5. Buat key JSON untuk Service Account.
6. Simpan informasi JSON tersebut untuk dimasukkan ke Streamlit Secrets.

## Persiapan Google Sheets

1. Buat Google Sheets baru.
2. Buat worksheet dengan nama:

```text
Data Peserta
```

3. Copy header dari file `google_sheet_headers.txt` ke baris pertama Google Sheets.
4. Share Google Sheets ke email Service Account sebagai Editor.

Contoh email Service Account:

```text
nama-service-account@project-id.iam.gserviceaccount.com
```

## Persiapan Google Drive

1. Buat folder Google Drive untuk menyimpan TTD.
2. Copy Folder ID dari URL folder.

Contoh URL:

```text
https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz
```

Folder ID-nya adalah:

```text
1AbCdEfGhIjKlMnOpQrStUvWxYz
```

3. Share folder tersebut ke email Service Account sebagai Editor.

## Konfigurasi Streamlit Secrets

Untuk deployment di Streamlit Cloud:

1. Upload project ini ke GitHub.
2. Buka Streamlit Cloud.
3. Deploy repository.
4. Masuk ke menu App > Settings > Secrets.
5. Isi secrets seperti contoh berikut.

```toml
SPREADSHEET_ID = "ISI_ID_GOOGLE_SHEET_ANDA"
WORKSHEET_NAME = "Data Peserta"
DRIVE_FOLDER_ID = "ISI_ID_FOLDER_GOOGLE_DRIVE_ANDA"
MAX_FILE_MB = 5
ADMIN_PASSWORD = "password-admin-opsional"

[gcp_service_account]
type = "service_account"
project_id = "ISI_PROJECT_ID"
private_key_id = "ISI_PRIVATE_KEY_ID"
private_key = "-----BEGIN PRIVATE KEY-----\nISI_PRIVATE_KEY_ANDA\n-----END PRIVATE KEY-----\n"
client_email = "nama-service-account@project-id.iam.gserviceaccount.com"
client_id = "ISI_CLIENT_ID"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "ISI_CLIENT_CERT_URL"
universe_domain = "googleapis.com"
```

Catatan penting:

- Jangan upload credential asli ke GitHub public.
- Jangan commit file `secrets.toml` asli.
- Gunakan menu Secrets di Streamlit Cloud.

## Cara Menjalankan Lokal

Buat file lokal:

```text
.streamlit/secrets.toml
```

Isi sesuai contoh `secrets.toml.example`, lalu jalankan:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment ke GitHub dan Streamlit Cloud

```bash
git init
git add .
git commit -m "Initial Streamlit form TTD PNG"
git branch -M main
git remote add origin https://github.com/USERNAME/NAMA_REPOSITORY.git
git push -u origin main
```

Setelah itu deploy via Streamlit Cloud dengan entry point:

```text
app.py
```

## Catatan untuk 1.600 Peserta

Aplikasi sudah ditambahkan retry otomatis. Untuk mengurangi risiko submit bersamaan, disarankan pembukaan form dilakukan per batch atau per Regional Corpu.

