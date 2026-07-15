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

## 🤖 Metode Deteksi Drone

Berbeda dari deteksi wajah yang menggunakan Haar Cascade statis, deteksi drone menggunakan pendekatan **berbasis gerakan** karena drone bergerak di udara dengan latar belakang yang relatif statis (langit).

| Tahap | Metode | Keterangan |
| :--- | :--- | :--- |
| **Background Model** | `MOG2` (Mixture of Gaussians) | Membangun model latar belakang dari 300 frame pertama |
| **Foreground Extraction** | Background Subtraction | Memisahkan objek bergerak dari latar belakang |
| **Noise Reduction** | Morfologi (Open + Close) | Menghilangkan noise kecil dan menyambungkan komponen |
| **Kontur & Filter** | `findContours` | Area: 80–8000 px², Aspect Ratio: 0.3–3.0 |
| **Target Selection** | Area terbesar | Drone dengan area kontur terbesar = target utama |

> [!NOTE]
> Program membutuhkan ±60 frame pertama (±2 detik) untuk membangun model *background* yang stabil. Semakin statis latar belakang (langit cerah), semakin akurat deteksinya.

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
