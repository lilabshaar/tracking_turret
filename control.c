#include <Arduino.h>
#include <Servo.h>

// ==========================================
// PENDEFINISIAN PIN
// ==========================================
const int PIN_SERVO_PAN  = 9;   // Servo Horizontal
const int PIN_SERVO_TILT = 10;  // Servo Vertikal
const int PIN_JOY_X      = A0;  // Pin Joystick X
const int PIN_JOY_Y      = A1;  // Pin Joystick Y

// ==========================================
// KONSTANTA & PARAMETER KONTROL
// ==========================================
const int PAN_MIN = 10;
const int PAN_MAX = 170;
const int TILT_MIN = 10;
const int TILT_MAX = 170;

// Konstanta kontrol proporsional untuk tracking (silakan disesuaikan)
const float KP_X = -0.06; // Meningkat 50% dari -0.04
const float KP_Y = -0.06; // Meningkat 50% dari -0.04

// ==========================================
// VARIABEL GLOBAL
// ==========================================
Servo servoPan;
Servo servoTilt;

int panAngle = 90;   // Sudut default tengah
int tiltAngle = 90;  // Sudut default tengah

int panAngleCalib = 90;  // Sudut referensi pan saat kalibrasi selesai
int tiltAngleCalib = 90; // Sudut referensi tilt saat kalibrasi selesai

bool isCalibrated = false; // False = Mode Joystick Manual, True = Mode Tracking Serial

void setup() {
  // Inisialisasi Serial Baudrate 115200 (harus sama dengan Python)
  Serial.begin(115200);
  
  // Lampu LED built-in sebagai indikator status mode
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW); // LOW = Mode Kalibrasi Manual
  
  // Lampirkan Servo ke Pin
  servoPan.attach(PIN_SERVO_PAN);
  servoTilt.attach(PIN_SERVO_TILT);
  
  // Posisikan servo ke tengah
  servoPan.write(panAngle);
  servoTilt.write(tiltAngle);
}

void loop() {
  // 1. MEMPROSES KOMUNIKASI SERIAL DARI PYTHON (Selalu Aktif)
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\n');
    data.trim();
    
    // Perintah Kalibrasi Selesai (Tombol 'y' ditekan di Python)
    if (data.equals("CALIB_OK")) {
      isCalibrated = true;
      panAngleCalib = panAngle;   // Mengunci sudut pan saat tombol 'y' ditekan
      tiltAngleCalib = tiltAngle; // Mengunci sudut tilt saat tombol 'y' ditekan
      digitalWrite(LED_BUILTIN, HIGH); // LED Menyala menandakan mode Tracking aktif
    } 
    // Perintah Pelacakan Wajah (Mengirimkan offset dx, dy)
    else if (data.startsWith("TRACK:") && isCalibrated) {
      int colonIdx = data.indexOf(':');
      int commaIdx = data.indexOf(',');
      
      if (colonIdx != -1 && commaIdx != -1) {
        String dxStr = data.substring(colonIdx + 1, commaIdx);
        String dyStr = data.substring(commaIdx + 1);
        
        int dx = dxStr.toInt();
        int dy = dyStr.toInt();
        
        // Hitung sudut servo berdasarkan offset mutlak dari posisi tengah kalibrasi
        panAngle = panAngleCalib + (dx * KP_X);
        tiltAngle = tiltAngleCalib + (dy * KP_Y);
        
        // Batasi sudut servo agar aman secara mekanis
        panAngle = constrain(panAngle, PAN_MIN, PAN_MAX);
        tiltAngle = constrain(tiltAngle, TILT_MIN, TILT_MAX);
        
        // Tulis sudut ke servo
        servoPan.write(panAngle);
        servoTilt.write(tiltAngle);
      }
    } 
    // Perintah Reset ke Mode Kalibrasi Manual
    else if (data.equals("RESET")) {
      isCalibrated = false;
      digitalWrite(LED_BUILTIN, LOW); // LED Mati
    }
  }

  // 2. MODE KENDALI MANUAL JOYSTICK (Hanya saat belum terkalibrasi)
  if (!isCalibrated) {
    int joyX = analogRead(PIN_JOY_X);
    int joyY = analogRead(PIN_JOY_Y);
    
    // Joystick ditengah biasanya bernilai ~512.
    // Terapkan Deadzone (450 s.d. 570) agar servo tidak bergerak sendiri jika joystick diam.
    bool moved = false;
    
    if (joyX < 450) {
      panAngle -= 1; // Putar ke kiri
      moved = true;
    } else if (joyX > 570) {
      panAngle += 1; // Putar ke kanan
      moved = true;
    }
    
    if (joyY < 450) {
      tiltAngle -= 1; // Gerak ke atas/bawah sesuai orientasi servo
      moved = true;
    } else if (joyY > 570) {
      tiltAngle += 1; // Gerak ke bawah/atas sesuai orientasi servo
      moved = true;
    }
    
    if (moved) {
      // Batasi sudut servo
      panAngle = constrain(panAngle, PAN_MIN, PAN_MAX);
      tiltAngle = constrain(tiltAngle, TILT_MIN, TILT_MAX);
      
      // Update posisi servo
      servoPan.write(panAngle);
      servoTilt.write(tiltAngle);
      
      // Kecepatan respon pergerakan manual joystick (makin kecil makin cepat)
      delay(15); 
    }
  }
}
