import cv2
import os
import sys
import argparse
import serial
import time
import numpy as np

def detect_drones(source=None, port=None):
    """
    Deteksi drone menggunakan Background Subtraction (MOG2) + Contour Filtering.
    Metode ini mendeteksi objek bergerak kecil di udara yang memiliki karakteristik drone:
    - Ukuran relatif kecil
    - Bergerak di area langit / latar belakang seragam
    - Bentuk kompak (aspect ratio mendekati 1:1)
    
    Untuk gambar statis, digunakan threshold adaptif + morfologi untuk menemukan
    objek dengan karakteristik bentuk drone.
    """

    # Inisialisasi Serial ke Arduino jika port diberikan
    ser = None
    if port:
        try:
            print(f"Membuka port serial {port}...")
            ser = serial.Serial(port, 115200, timeout=1)
            time.sleep(2)
            print(f"Koneksi Serial berhasil tersambung ke Arduino di {port}")
            ser.write(b"RESET\n")
        except Exception as e:
            print(f"Error: Gagal membuka port serial {port}: {e}")
            print("Program akan berjalan tanpa koneksi serial.")
            ser = None

    if source is not None and os.path.exists(source):
        # =====================================================================
        # MODE 1: Deteksi Drone pada File Gambar (Static Image Mode)
        # Menggunakan threshold adaptif untuk menemukan objek kontras tinggi
        # =====================================================================
        print(f"Membaca gambar: {source}")
        frame = cv2.imread(source)
        if frame is None:
            print("Error: Gagal membaca file gambar.")
            if ser:
                ser.close()
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Blur untuk mengurangi noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Threshold adaptif untuk menemukan objek gelap di latar terang (langit)
        thresh = cv2.adaptiveThreshold(blurred, 255,
                                       cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 11, 2)

        # Operasi morfologi untuk membersihkan noise dan menyambungkan komponen drone
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

        # Temukan kontur
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        drones = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Filter berdasarkan ukuran: drone berukuran sedang (bukan noise, bukan objek sangat besar)
            if 200 < area < 50000:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = float(w) / h if h > 0 else 0
                # Drone umumnya memiliki bentuk kompak (tidak terlalu memanjang)
                if 0.3 < aspect_ratio < 3.0:
                    drones.append((x, y, w, h))

        print(f"Jumlah drone terdeteksi: {len(drones)}")

        for i, (x, y, w, h) in enumerate(drones, 1):
            center_x = x + (w // 2)
            center_y = y + (h // 2)

            # Kotak pembatas merah untuk drone
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
            # Titik tengah kuning
            cv2.circle(frame, (center_x, center_y), 5, (0, 255, 255), -1)
            # Label dan koordinat
            cv2.putText(frame, f"DRONE #{i}", (x, y - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.putText(frame, f"({center_x}, {center_y})", (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

            print(f"Drone #{i}: Area ({x}, {y}) s/d ({x+w}, {y+h}) | Titik Tengah: ({center_x}, {center_y})")

        output_name = "output_" + os.path.basename(source)
        cv2.imwrite(output_name, frame)
        print(f"Hasil deteksi telah disimpan ke: {output_name}")

        cv2.imshow('Drone Detection (Tekan tombol apa saja untuk keluar)', frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    else:
        # =====================================================================
        # MODE 2: Deteksi Drone Real-time via Webcam + Serial Arduino
        # Menggunakan MOG2 Background Subtractor untuk mendeteksi objek bergerak
        # =====================================================================
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Gagal membuka webcam. Pastikan webcam terhubung.")
            if ser:
                ser.close()
            return

        # Inisialisasi Background Subtractor MOG2
        # history=300: frame yang digunakan untuk membangun model background
        # varThreshold=40: sensitivitas deteksi perubahan piksel
        # detectShadows=False: abaikan bayangan untuk akurasi lebih baik
        bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=300, varThreshold=40, detectShadows=False
        )

        # Kernel morfologi untuk membersihkan hasil foreground mask
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

        print("\n=== KENDALI TURRET DETEKSI DRONE ===")
        print("1. Program dimulai dalam MODE KALIBRASI MANUAL.")
        print("2. Arahkan kamera ke area pengamatan (biarkan beberapa detik untuk build background).")
        print("3. Gerakkan JOYSTICK untuk mengarahkan turret tepat ke tengah drone target.")
        print("4. Tekan tombol 'y' untuk mengunci posisi referensi & mulai AUTO-TRACKING.")
        print("5. Tekan tombol 'r' untuk mereset ke MODE KALIBRASI.")
        print("6. Tekan tombol 'q' untuk keluar dari program.\n")
        print("INFO: Background sedang dibangun, harap tunggu beberapa detik...\n")

        is_calibrated = False
        calib_x = 0
        calib_y = 0
        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                print("Gagal mengambil frame dari webcam.")
                break

            frame_count += 1

            # ---- Proses Background Subtraction ----
            # Resize ke resolusi lebih kecil untuk performa lebih cepat
            h_orig, w_orig = frame.shape[:2]
            scale = 0.5
            small = cv2.resize(frame, (int(w_orig * scale), int(h_orig * scale)))

            # Terapkan background subtractor
            fg_mask = bg_subtractor.apply(small)

            # Morfologi: hapus noise kecil dan sambungkan komponen drone
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

            # Temukan kontur pada foreground mask
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # ---- Filter kontur untuk karakteristik drone ----
            drones_detected = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                # Ukuran minimum dan maksimum area drone (dalam frame yang di-resize)
                if 80 < area < 8000:
                    x, y, w, h = cv2.boundingRect(cnt)
                    aspect_ratio = float(w) / h if h > 0 else 0
                    # Drone kompak: aspect ratio 0.3 - 3.0
                    if 0.3 < aspect_ratio < 3.0:
                        # Kembalikan koordinat ke skala asli
                        x_orig = int(x / scale)
                        y_orig = int(y / scale)
                        w_orig_r = int(w / scale)
                        h_orig_r = int(h / scale)
                        drones_detected.append((x_orig, y_orig, w_orig_r, h_orig_r))

            # Tampilkan foreground mask di pojok kiri bawah (debug view kecil)
            h_frame, w_frame = frame.shape[:2]
            mask_display = cv2.cvtColor(fg_mask, cv2.COLOR_GRAY2BGR)
            mask_small = cv2.resize(mask_display, (160, 120))
            frame[h_frame - 130:h_frame - 10, 10:170] = mask_small
            cv2.putText(frame, "FG Mask", (10, h_frame - 135),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

            # Pilih drone pertama sebagai target aktif
            active_drone = None
            if len(drones_detected) > 0:
                # Pilih drone dengan area terbesar sebagai target utama
                active_drone = max(drones_detected,
                                   key=lambda b: b[2] * b[3])

            # ---- Visualisasi ----
            # Gambar semua drone yang terdeteksi (abu-abu tipis)
            for (x, y, w, h) in drones_detected:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (100, 100, 100), 1)

            if active_drone is not None:
                (x, y, w, h) = active_drone
                center_x = x + (w // 2)
                center_y = y + (h // 2)

                # Kotak pembatas merah tebal untuk target utama
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                # Crosshair di titik tengah
                cv2.drawMarker(frame, (center_x, center_y), (0, 255, 255),
                               cv2.MARKER_CROSS, 20, 2)
                # Koordinat
                cv2.putText(frame, f"DRONE ({center_x}, {center_y})",
                            (x, max(y - 10, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)

                if is_calibrated:
                    dx = center_x - calib_x
                    dy = center_y - calib_y

                    cv2.line(frame, (calib_x, calib_y), (center_x, center_y), (255, 0, 0), 2)
                    cv2.circle(frame, (calib_x, calib_y), 6, (255, 255, 0), -1)

                    status_text = f"AUTO-TRACKING | dx: {dx}, dy: {dy}"
                    cv2.putText(frame, status_text, (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

                    if ser:
                        try:
                            cmd = f"TRACK:{dx},{dy}\n"
                            ser.write(cmd.encode('utf-8'))
                        except Exception as e:
                            print(f"Error mengirim data serial: {e}")
                else:
                    status_text = "MODE KALIBRASI: Arahkan joystick, tekan 'y' jika sudah pas."
                    cv2.putText(frame, status_text, (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 2)
            else:
                if frame_count < 60:
                    # Fase warming up background model
                    status_text = f"Membangun model background... ({frame_count}/60)"
                    cv2.putText(frame, status_text, (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 0), 2)
                elif is_calibrated:
                    status_text = "AUTO-TRACKING: Drone Hilang!"
                    cv2.putText(frame, status_text, (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                else:
                    status_text = "KALIBRASI: Drone tidak terdeteksi"
                    cv2.putText(frame, status_text, (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            # Info jumlah drone
            cv2.putText(frame, f"Drone Terdeteksi: {len(drones_detected)}", (20, h_frame - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

            cv2.imshow('Drone Detection & Turret Control', frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('y'):
                if active_drone is not None:
                    (x, y, w, h) = active_drone
                    calib_x = x + (w // 2)
                    calib_y = y + (h // 2)
                    is_calibrated = True
                    print(f"Kalibrasi disimpan! Titik acuan dikunci pada: X={calib_x}, Y={calib_y}")
                    if ser:
                        try:
                            ser.write(b"CALIB_OK\n")
                        except Exception as e:
                            print(f"Error mengirim sinyal serial CALIB_OK: {e}")
                else:
                    print("Peringatan: Gagal mengunci kalibrasi karena drone tidak terdeteksi.")

            elif key == ord('r'):
                is_calibrated = False
                calib_x = 0
                calib_y = 0
                print("Kalibrasi di-reset. Kembali ke mode joystick manual.")
                if ser:
                    try:
                        ser.write(b"RESET\n")
                    except Exception as e:
                        print(f"Error mengirim sinyal serial RESET: {e}")

            elif key == ord('q'):
                print("Menutup program...")
                if ser:
                    try:
                        ser.write(b"RESET\n")
                    except:
                        pass
                break

        cap.release()
        cv2.destroyAllWindows()
        if ser:
            ser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Program Drone Tracking & Turret Controller")
    parser.add_argument("image", nargs="?", default=None,
                        help="Path file gambar (Opsional untuk deteksi gambar statis)")
    parser.add_argument("--port", default=None,
                        help="COM Port Arduino (Contoh: COM3 atau /dev/ttyUSB0)")

    args = parser.parse_args()
    detect_drones(args.image, args.port)
