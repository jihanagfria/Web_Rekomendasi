# MakeMatch - Sistem Rekomendasi Base Makeup

## Struktur proyek

```text
MakeMatch/
|-- app.py
|-- backend/
|   `-- data/
|       |-- dataset_makeup_fac.csv
|       `-- products.json
|-- frontend/
|   |-- templates/index.html
|   `-- static/
|       |-- style.css
|       |-- js/main.js
|       `-- images/
`-- README.md
```

## Tanggung jawab file

- `app.py`: Flask API, pembentukan JSON, ekstraksi benefit, hard filter subkategori, TF-IDF, dan cosine similarity.
- `backend/data/dataset_makeup_fac.csv`: dataset sumber Base Makeup.
- `backend/data/products.json`: katalog hasil transformasi yang dibaca aplikasi.
- `frontend/templates/index.html`: struktur halaman.
- `frontend/static/style.css`: tampilan halaman.
- `frontend/static/js/main.js`: interaksi tombol, katalog, dan hasil rekomendasi.

## Alur rekomendasi

```text
Preferensi pengguna
→ hard filter subkategori
→ kandidat produk
→ profil konten: jenis kulit + finish + cbfBenefits
→ TF-IDF
→ cosine similarity
→ pengurutan skor
→ produk dengan skor lebih dari 0
```

Subkategori adalah hard filter. Jenis kulit, finish, dan karakteristik produk digunakan sebagai fitur Content-Based Filtering.

## Ekstraksi benefit

Kolom `benefit` asli tidak diubah dan tetap ditampilkan pada kartu produk. Backend membentuk `cbfBenefits` terpisah untuk perhitungan CBF dengan delapan kategori:

- Long Lasting
- Oil Control
- Lightweight
- UV Protection
- Coverage
- Pore Blurring
- Waterproof
- Hydrating

Satu klaim dapat masuk lebih dari satu kategori. Contohnya klaim yang memuat `SPF` dan `Lightweight` menjadi `UV Protection` dan `Lightweight`.

Kategori `Coverage` hanya menunjukkan adanya klaim daya tutup. Sistem tidak membedakan tingkatnya: `Full Coverage`, `High Coverage`, `Medium Coverage`, dan bentuk klaim lain yang memuat kata `coverage` semuanya direpresentasikan sebagai `Coverage`.

## Pembobotan dan peringkat

IDF dihitung pada kandidat setelah hard filter menggunakan smoothing:

```text
IDF(t) = ln((N + 1) / (df(t) + 1)) + 1
```

Smoothing mencegah fitur yang muncul pada seluruh kandidat memiliki bobot nol. Skor akhir dihitung memakai cosine similarity. Skor hanya dipakai di backend untuk mengurutkan hasil dan tidak dikirim ke browser.

## Menjalankan aplikasi

Dari folder `C:\xampp\htdocs\MakeMatch`:

```powershell
python -m pip install -r requirements.txt
python -B app.py
```

Buka `http://127.0.0.1:5000`.

Opsi `-B` mencegah Python membuat folder `__pycache__`.

## Membangun ulang JSON

Setelah CSV diubah, jalankan:

```powershell
python -B app.py --build-data
```


