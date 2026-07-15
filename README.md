# Arduino & Python Drone Tracking Turret

Proyek ini adalah sistem pengendali turret (Pan & Tilt) berbasis **deteksi drone** menggunakan kamera (OpenCV) dan mikrokontroler Arduino. Sistem ini dilengkapi dengan **Mode Kalibrasi Manual** menggunakan joystick fisik dan berpindah secara otomatis ke **Mode Pelacakan Drone Otomatis (Auto-Tracking)** setelah penekanan tombol.

> Sistem ini awalnya dikembangkan untuk deteksi wajah, dan telah direvisi untuk mendukung **deteksi drone** menggunakan metode *Background Subtraction* (MOG2) dan *Contour Filtering* — tanpa memerlukan model machine learning tambahan.

---

## 📁 Struktur Proyek

* [drone_detect.py](file:///d:/UNHAN/PROJEK/Turret/drone_detect.py) - Script Python utama untuk mendeteksi drone via Webcam menggunakan Background Subtraction MOG2, menghitung pergeseran koordinat (offset), dan mengirimkannya ke Arduino via komunikasi Serial.
* [body_detect.py](file:///d:/UNHAN/PROJEK/Turret/body_detect.py) - Varian script untuk mendeteksi tubuh manusia penuh menggunakan Haar Cascade (`haarcascade_fullbody.xml`).
* [face_detect.py](file:///d:/UNHAN/PROJEK/Turret/face_detect.py) - Script versi awal untuk mendeteksi wajah menggunakan Haar Cascade (`haarcascade_frontalface_default.xml`).
* [control.c](file:///d:/UNHAN/PROJEK/Turret/control.c) - Berkas kode program C/C++ (sketsa Arduino) untuk menerima input joystick, menggerakkan servo, dan merespons data pelacakan dari Python.
* [logika.md](file:///d:/UNHAN/PROJEK/Turret/logika.md) - Dokumentasi alur kerja sistem, *state machine*, diagram alir (Mermaid), dan rumus kontrol proporsional yang digunakan.

---

## 🤖 Mekanisme Deteksi Drone

Deteksi drone **tidak dapat menggunakan Haar Cascade** seperti deteksi wajah, karena:
- Tidak ada dataset Haar Cascade bawaan untuk drone di OpenCV
- Drone memiliki bentuk yang sangat bervariasi (multirotor, fixed-wing, mini drone)
- Penampilan visual drone berubah drastis tergantung sudut pandang kamera

Sebagai gantinya, sistem menggunakan pendekatan **berbasis analisis gerakan piksel** yang memanfaatkan sifat alami drone: *drone selalu bergerak di depan latar belakang yang relatif statis*.

---

### 🔬 Pipeline Deteksi (Tahap per Tahap)

#### Tahap 1 — Resize Frame (Optimasi Performa)
```
Frame asli (misal 640×480) → Resize ke 50% (320×240)
```
Frame diperkecil setengah ukuran sebelum diproses. Ini mengurangi jumlah piksel yang dihitung sebesar 75%, sehingga proses deteksi berjalan lebih cepat dan real-time. Koordinat hasil deteksi kemudian dikembalikan ke skala asli.

---

#### Tahap 2 — Background Subtraction MOG2
```
Frame (saat ini) − Model Background (terakumulasi) = Foreground Mask
```
**MOG2** (*Mixture of Gaussians v2*) adalah algoritma yang membangun model statistik dari *background* secara adaptif. Setiap piksel dimodelkan sebagai campuran distribusi Gaussian. Ketika nilai piksel pada frame baru menyimpang signifikan dari model Gaussian-nya, piksel tersebut diklasifikasikan sebagai **foreground** (objek bergerak).

| Parameter MOG2 | Nilai | Penjelasan |
| :--- | :---: | :--- |
| `history` | `300` | Jumlah frame yang digunakan untuk membangun model background. Semakin besar, semakin stabil tapi lebih lambat adaptif. |
| `varThreshold` | `40` | Ambang batas jarak Mahalanobis antara nilai piksel dan model Gaussian-nya. Semakin kecil = semakin sensitif terhadap perubahan kecil. |
| `detectShadows` | `False` | Menonaktifkan deteksi bayangan. Jika aktif, bayangan akan dipisahkan (nilai abu-abu) agar tidak dihitung sebagai objek — dinonaktifkan untuk mempercepat proses. |

Hasil tahap ini adalah **Foreground Mask**: gambar biner di mana piksel putih = objek bergerak, piksel hitam = background statis.

---

#### Tahap 3 — Operasi Morfologi (Pembersihan Mask)
Foreground Mask mentah masih mengandung banyak noise (piksel putih acak yang bukan objek nyata). Dua operasi morfologi diterapkan secara berurutan:

**Morfologi OPEN** (Erosi → Dilasi):
```
Menghapus noise kecil yang lebih kecil dari kernel (5×5 piksel)
```
Piksel putih yang terlalu kecil (noise sensor, dedaunan goyang, cahaya berfluktuasi) dihapus terlebih dahulu.

**Morfologi CLOSE** (Dilasi → Erosi):
```
Mengisi celah/lubang kecil di dalam objek yang terdeteksi
```
Jika drone terdeteksi sebagai beberapa fragmen terpisah (misal badan + baling-baling), operasi ini menyambungkannya menjadi satu blob yang utuh.

Kernel yang digunakan adalah **ellipse 5×5** karena bentuk drone cenderung kompak dan membulat.

---

#### Tahap 4 — Deteksi Kontur (`findContours`)
```
Foreground Mask (bersih) → Ekstrak batas tepi setiap blob putih
```
OpenCV menelusuri tepi setiap blob putih pada mask dan menghasilkan daftar kontur (poligon). Setiap kontur mewakili satu kandidat objek bergerak.

---

#### Tahap 5 — Filtering Kontur (Eliminasi False Positive)
Tidak semua kontur adalah drone. Filter berlapis diterapkan:

**Filter 1 — Area Minimum & Maksimum:**
```
80 px² < area < 8000 px²  (pada frame yang sudah di-resize 50%)
```
- Area terlalu kecil (< 80 px²) → noise, debu, atau serangga
- Area terlalu besar (> 8000 px²) → bukan drone (pohon goyang, orang berjalan, awan bergerak)

**Filter 2 — Aspect Ratio (Rasio Lebar : Tinggi):**
```python
aspect_ratio = w / h
0.3 < aspect_ratio < 3.0  →  diterima sebagai kandidat drone
```
Drone multirotor umumnya berbentuk kompak (hampir persegi). Objek yang terlalu memanjang seperti burung yang sedang mengepak sayap atau kabel bergetar akan dibuang oleh filter ini.

---

#### Tahap 6 — Seleksi Target Utama
Jika lebih dari satu kandidat lolos semua filter, sistem memilih **kontur dengan area terbesar** sebagai target utama. Asumsinya: drone yang lebih dekat ke kamera akan tampak lebih besar dan lebih relevan sebagai ancaman.

```python
active_drone = max(drones_detected, key=lambda b: b[2] * b[3])
# b[2] = lebar bounding box, b[3] = tinggi bounding box
```

---

#### Tahap 7 — Perhitungan Offset & Pengiriman ke Arduino
Setelah drone target teridentifikasi, sistem menghitung **titik tengah** drone:
```
center_x = x + (w / 2)
center_y = y + (h / 2)
```

Kemudian dihitung **deviasi (offset)** dari titik referensi kalibrasi:
```
dx = center_x − calib_x   (positif = drone bergeser ke kanan)
dy = center_y − calib_y   (positif = drone bergeser ke bawah)
```

Data offset dikirim ke Arduino setiap frame via Serial dengan format:
```
TRACK:dx,dy\n
```
Arduino kemudian menggerakkan servo Pan (sumbu X) dan Tilt (sumbu Y) secara proporsional terhadap nilai `dx` dan `dy`.

---

### 📊 Ringkasan Pipeline

```
[Webcam Frame]
      │
      ▼
[Resize 50%]  ──────────────────────────────── (optimasi kecepatan)
      │
      ▼
[MOG2 Background Subtraction]  ─────────────── (pisahkan objek bergerak)
      │
      ▼
[Foreground Mask]
      │
      ▼
[Morfologi OPEN]  ──────────────────────────── (hapus noise kecil)
      │
      ▼
[Morfologi CLOSE]  ─────────────────────────── (sambungkan fragmen drone)
      │
      ▼
[findContours]  ────────────────────────────── (deteksi batas objek)
      │
      ▼
[Filter: Area & Aspect Ratio]  ─────────────── (buang false positive)
      │
      ▼
[Pilih Kontur Terbesar]  ───────────────────── (target drone utama)
      │
      ▼
[Hitung center_x, center_y]
      │
      ▼
[Hitung dx, dy dari titik kalibrasi]
      │
      ▼
[Kirim TRACK:dx,dy ke Arduino via Serial]
      │
      ▼
[Arduino gerakkan Servo Pan & Tilt]
```

> [!NOTE]
> Program membutuhkan ±60 frame pertama (±2 detik) untuk membangun model *background* yang stabil. Hindari menggerakkan kamera secara drastis di awal program karena akan merusak model background.

> [!TIP]
> Untuk hasil terbaik, gunakan latar belakang yang seragam (langit cerah, dinding polos). Latar belakang yang ramai (pepohonan, kerumunan) akan meningkatkan false positive karena banyak pergerakan selain drone.

---

## 🔌 Skema Rangkaian (Wiring Diagram)

Hubungkan komponen turret ke Arduino sesuai tabel berikut:

| Komponen | Pin Arduino | Deskripsi |
| :--- | :--- | :--- |
| **Servo Pan** | `D9` (PWM) | Mengendalikan gerakan horizontal (kiri/kanan) |
| **Servo Tilt** | `D10` (PWM) | Mengendalikan gerakan vertikal (atas/bawah) |
| **Joystick X** | `A0` (Analog) | Membaca input joystick sumbu X (manual) |
| **Joystick Y** | `A1` (Analog) | Membaca input joystick sumbu Y (manual) |
| **VCC & GND** | `5V` & `GND` | Catu daya servo dan joystick |

> [!WARNING]
> Sangat disarankan untuk menggunakan catu daya/baterai eksternal `5V` khusus untuk motor servo (hubungkan GND baterai dengan GND Arduino) agar Arduino tidak mengalami *reset* akibat lonjakan arus servo.

---

## 🚀 Langkah Instalasi & Penggunaan

### 1. Persiapan Pustaka Python
Pastikan Python sudah terinstal di PC Anda, kemudian pasang pustaka yang diperlukan:
```bash
pip install opencv-python pyserial numpy
```

### 2. Mengunggah Kode Arduino
1. Sambungkan Arduino Anda ke komputer via USB.
2. Buka **Arduino IDE**, salin seluruh isi berkas [control.c](file:///d:/UNHAN/PROJEK/Turret/control.c), lalu tempelkan ke sketsa baru.
3. Simpan dan beri nama sketsa tersebut `turret_control.ino`.
4. Unggah (*upload*) kode tersebut ke Arduino. Catat nama Port COM yang terdeteksi (contoh: `COM3`).

### 3. Menjalankan Pelacakan Drone
Buka terminal/command prompt pada direktori proyek, lalu jalankan perintah berikut:
```bash
python drone_detect.py --port COM3
```
*(Ganti `COM3` sesuai port serial Arduino Anda.)*

Untuk menguji deteksi pada gambar statis (tanpa Arduino):
```bash
python drone_detect.py foto_drone.jpg
```

---

## 🎮 Cara Kerja & Tombol Pintasan

1. **Inisialisasi**: Program dimulai dalam **Mode Kalibrasi Manual** (LED internal Arduino mati). Selama ±2 detik pertama, sistem membangun model *background*. Gunakan joystick fisik untuk memposisikan turret agar mengarah tepat ke drone target.
2. **Kunci Kalibrasi (Tombol `y`)**: Tekan tombol `'y'` pada jendela kamera OpenCV saat drone terdeteksi. Posisi drone saat itu akan disimpan sebagai referensi pusat pelacakan (LED internal Arduino menyala).
3. **Pelacakan Otomatis**: Turret akan secara otomatis memutar servo *pan & tilt* mengikuti pergerakan drone (ke kiri, kanan, atas, maupun bawah).
4. **Reset Kalibrasi (Tombol `r`)**: Tekan tombol `'r'` untuk membatalkan penguncian pelacakan dan kembali ke kontrol joystick manual.
5. **Keluar (Tombol `q`)**: Tekan tombol `'q'` untuk menghentikan program Python dengan aman.

---

## 📊 Perbandingan Mode Deteksi

| Fitur | `face_detect.py` | `body_detect.py` | `drone_detect.py` |
| :--- | :---: | :---: | :---: |
| **Metode** | Haar Cascade | Haar Cascade | MOG2 + Contour |
| **Target** | Wajah manusia | Tubuh penuh | Drone / objek terbang |
| **Perlu Model Tambahan** | ❌ | ❌ | ❌ |
| **Syarat Deteksi** | Cahaya cukup | Cahaya cukup | Objek harus bergerak |
| **Cocok untuk Demo** | ✅ | ✅ | ✅ (latar statis) |
