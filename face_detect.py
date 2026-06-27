import cv2
import os
import sys
import argparse
import serial
import time

def detect_faces(source=None, port=None):
    # Memuat Haar Cascade classifier bawaan OpenCV untuk deteksi wajah
    cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    if face_cascade.empty():
        print("Error: Gagal memuat Haar Cascade XML file.")
        return

    # Inisialisasi Serial ke Arduino jika port diberikan
    ser = None
    if port:
        try:
            print(f"Membuka port serial {port}...")
            # Arduino biasanya auto-reset saat serial dibuka, butuh delay
            ser = serial.Serial(port, 115200, timeout=1)
            time.sleep(2) 
            print(f"Koneksi Serial berhasil tersambung ke Arduino di {port}")
            # Kirim sinyal reset untuk memastikan Arduino berada di mode kalibrasi manual (joystick)
            ser.write(b"RESET\n")
        except Exception as e:
            print(f"Error: Gagal membuka port serial {port}: {e}")
            print("Program akan berjalan tanpa koneksi serial.")
            ser = None

    if source is not None and os.path.exists(source):
        # =====================================================================
        # MODE 1: Deteksi Wajah pada File Gambar (Static Image Mode)
        # =====================================================================
        print(f"Membaca gambar: {source}")
        frame = cv2.imread(source)
        if frame is None:
            print("Error: Gagal membaca file gambar.")
            if ser:
                ser.close()
            return
            
        # Konversi ke grayscale untuk proses deteksi
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        
        print(f"Jumlah wajah terdeteksi: {len(faces)}")
        
        for i, (x, y, w, h) in enumerate(faces, 1):
            # Hitung titik tengah wajah
            center_x = x + (w // 2)
            center_y = y + (h // 2)
            
            # Gambar kotak pembatas hijau
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # Gambar titik tengah berwarna merah
            cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)
            # Tambahkan teks koordinat titik tengah di layar
            text_coord = f"({center_x}, {center_y})"
            cv2.putText(frame, text_coord, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            print(f"Wajah #{i}: Area ({x}, {y}) s/d ({x+w}, {y+h}) | Titik Tengah: ({center_x}, {center_y})")
            
        # Simpan hasil deteksi ke file baru
        output_name = "output_" + os.path.basename(source)
        cv2.imwrite(output_name, frame)
        print(f"Hasil deteksi telah disimpan ke: {output_name}")
        
        # Tampilkan hasil gambar (Tekan tombol apa saja untuk menutup)
        cv2.imshow('Face Detection (Tekan tombol apa saja untuk keluar)', frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
    else:
        # =====================================================================
        # MODE 2: Deteksi Wajah Real-time via Webcam + Serial Arduino
        # =====================================================================
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Gagal membuka webcam. Pastikan webcam terhubung.")
            if ser:
                ser.close()
            return

        print("\n=== KENDALI TURRET DETEKSI WAJAH ===")
        print("1. Program dimulai dalam MODE KALIBRASI MANUAL.")
        print("2. Gerakkan JOYSTICK untuk mengarahkan turret tepat ke tengah wajah target.")
        print("3. Tekan tombol 'y' untuk mengunci posisi referensi & mulai AUTO-TRACKING.")
        print("4. Tekan tombol 'r' untuk mereset ke MODE KALIBRASI.")
        print("5. Tekan tombol 'q' untuk keluar dari program.\n")
        
        # State Kalibrasi
        is_calibrated = False
        calib_x = 0
        calib_y = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Gagal mengambil frame dari webcam.")
                break
                
            # Konversi ke grayscale untuk proses deteksi
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            
            # Tentukan wajah aktif (wajah pertama yang terdeteksi)
            active_face = None
            if len(faces) > 0:
                active_face = faces[0]
                
            # Gambar visualisasi wajah
            if active_face is not None:
                (x, y, w, h) = active_face
                center_x = x + (w // 2)
                center_y = y + (h // 2)
                
                # Gambar kotak pembatas wajah target utama
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)
                
                # Tampilkan koordinat wajah saat ini
                cv2.putText(frame, f"({center_x}, {center_y})", (x, y - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Mode Auto-Tracking
                if is_calibrated:
                    # Hitung deviasi/jarak dari koordinat referensi
                    dx = center_x - calib_x
                    dy = center_y - calib_y
                    
                    # Garis hubung antara titik referensi kalibrasi dan posisi wajah sekarang
                    cv2.line(frame, (calib_x, calib_y), (center_x, center_y), (255, 0, 0), 2)
                    cv2.circle(frame, (calib_x, calib_y), 6, (255, 255, 0), -1)
                    
                    # Info status tracking
                    status_text = f"AUTO-TRACKING | Offset dx: {dx}, dy: {dy}"
                    cv2.putText(frame, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                    
                    # Kirim data offset ke Arduino via Serial
                    if ser:
                        try:
                            cmd = f"TRACK:{dx},{dy}\n"
                            ser.write(cmd.encode('utf-8'))
                        except Exception as e:
                            print(f"Error mengirim data serial: {e}")
                else:
                    # Mode Kalibrasi Manual
                    status_text = "MODE KALIBRASI: Arahkan joystick, tekan 'y' jika sudah pas."
                    cv2.putText(frame, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
            else:
                # Jika tidak ada wajah yang terdeteksi
                if is_calibrated:
                    status_text = "AUTO-TRACKING: Wajah Hilang!"
                    cv2.putText(frame, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                else:
                    status_text = "KALIBRASI: Wajah tidak terdeteksi"
                    cv2.putText(frame, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            # Tampilkan window webcam
            cv2.imshow('Face Detection & Turret Control', frame)
            
            # Input keyboard untuk transisi state
            key = cv2.waitKey(1) & 0xFF
            
            # Tekan 'y' untuk menyelesaikan kalibrasi & kunci posisi tengah wajah
            if key == ord('y'):
                if active_face is not None:
                    (x, y, w, h) = active_face
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
                    print("Peringatan: Gagal mengunci kalibrasi karena wajah tidak terdeteksi.")
                    
            # Tekan 'r' untuk mereset kalibrasi dan kembali ke kontrol joystick manual
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
                        
            # Tekan 'q' untuk keluar
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
    parser = argparse.ArgumentParser(description="Program Face Tracking & Turret Controller")
    parser.add_argument("image", nargs="?", default=None, help="Path file gambar (Opsional untuk deteksi gambar statis)")
    parser.add_argument("--port", default=None, help="COM Port Arduino (Contoh: COM3 atau /dev/ttyUSB0)")
    
    args = parser.parse_args()
    detect_faces(args.image, args.port)
