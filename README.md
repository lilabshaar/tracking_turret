# Arduino & Python Face Tracking Turret

Proyek ini adalah sistem pengendali turret (Pan & Tilt) berbasis deteksi wajah menggunakan kamera (OpenCV) dan mikrokontroler Arduino. Sistem ini dilengkapi dengan **Mode Kalibrasi Manual** menggunakan joystick fisik dan berpindah secara otomatis ke **Mode Pelacakan Wajah Otomatis (Auto-Tracking)** setelah penekanan tombol.

---

## 📁 Struktur Proyek

* [face_detect.py](file:///d:/UNHAN/PROJEK/Turret/face_detect.py) - Script Python untuk mendeteksi wajah via Webcam, menghitung pergeseran koordinat (offset), dan mengirimkannya ke Arduino via komunikasi Serial.
* [control.c](file:///d:/UNHAN/PROJEK/Turret/control.c) - Berkas kode program C/C++ (sketsa Arduino) untuk menerima input joystick, menggerakkan servo, dan merespons data pelacakan dari Python.
* [logika.md](file:///d:/UNHAN/PROJEK/Turret/logika.md) - Dokumentasi alur kerja sistem, *state machine*, diagram alir (Mermaid), dan rumus kontrol proporsional yang digunakan.

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
pip install opencv-python pyserial
```

### 2. Mengunggah Kode Arduino
1. Sambungkan Arduino Anda ke komputer via USB.
2. Buka **Arduino IDE**, salin seluruh isi berkas [control.c](file:///d:/UNHAN/PROJEK/Turret/control.c), lalu tempelkan ke sketsa baru.
3. Simpan dan beri nama sketsa tersebut `turret_control.ino`.
4. Unggah (*upload*) kode tersebut ke Arduino. Catat nama Port COM yang terdeteksi (contoh: `COM3`).

### 3. Menjalankan Pelacakan Wajah
Buka terminal/command prompt pada direktori proyek, lalu jalankan perintah berikut:
```bash
python face_detect.py --port COM3
```
*(Ganti `COM3` sesuai port serial Arduino Anda).*

---

## 🎮 Cara Kerja & Tombol Pintasan

1. **Inisialisasi**: Program dimulai dalam **Mode Kalibrasi Manual** (LED internal Arduino mati). Gunakan joystick fisik untuk memposisikan turret agar mengarah tepat ke tengah wajah target.
2. **Kunci Kalibrasi (Tombol `y`)**: Tekan tombol `'y'` pada jendela kamera OpenCV. Sudut servo dan posisi wajah saat itu akan disimpan sebagai referensi pusat pelacakan (LED internal Arduino menyala).
3. **Pelacakan Otomatis**: Turret akan secara otomatis memutar servo *pan & tilt* mengikuti pergerakan wajah Anda (ke kiri, kanan, atas, maupun bawah) dengan respons sensitivitas yang ditingkatkan.
4. **Reset Kalibrasi (Tombol `r`)**: Tekan tombol `'r'` untuk membatalkan penguncian pelacakan dan kembali ke kontrol joystick manual.
5. **Keluar (Tombol `q`)**: Tekan tombol `'q'` untuk menghentikan program Python dengan aman.
