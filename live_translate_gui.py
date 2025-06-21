import subprocess
import threading
from PIL import Image, ImageDraw
import pystray
import keyboard

# --- Konfigurasi Shortcut ---
# Anda bisa mengubah shortcut di sini.
# Format: 'ctrl+alt+q', 'ctrl+shift+s', 'f9', dll.
SHORTCUT_KEY = "ctrl+alt+q"

def start_visual_ocr():
    """
    Menjalankan skrip ocr_visual_overlay.py sebagai proses terpisah.
    Dibuat agar tidak error jika shortcut ditekan berkali-kali dengan cepat.
    """
    # Mengecek apakah sudah ada proses overlay yang berjalan agar tidak duplikat
    # (Ini adalah pendekatan sederhana, mungkin tidak 100% foolproof)
    global ocr_process
    if ocr_process and ocr_process.poll() is None:
        print("Proses OCR sudah berjalan.")
        return
    
    print(f"Shortcut '{SHORTCUT_KEY}' ditekan, memulai mode pindai...")
    try:
        # Menggunakan "pythonw" agar tidak ada jendela konsol yang muncul
        ocr_process = subprocess.Popen(["pythonw", "ocr_visual_overlay.py"], shell=False)
    except FileNotFoundError:
        try:
            ocr_process = subprocess.Popen(["python", "ocr_visual_overlay.py"], shell=True)
        except Exception as e:
            print(f"Gagal menjalankan skrip overlay: {e}")
    except Exception as e:
        print(f"Gagal menjalankan skrip overlay: {e}")

def create_image():
    """Membuat gambar sederhana untuk ikon di system tray."""
    width = 64
    height = 64
    # Warna latar belakang (putih) dan warna teks/simbol (hitam)
    color1 = "white"
    color2 = "black"
    
    image = Image.new("RGB", (width, height), color1)
    dc = ImageDraw.Draw(image)
    
    # Gambar simbol 'Scan' sederhana
    dc.rectangle((width // 4, height // 4, width * 3 // 4, height * 3 // 4), outline=color2, width=4)
    dc.line((width // 2, height // 4, width // 2, height * 3 // 4), fill=color2, width=2)
    
    return image

def exit_action(icon, item):
    """Fungsi untuk keluar dari aplikasi."""
    print("Keluar dari aplikasi listener...")
    keyboard.unhook_all()  # Melepas semua hotkey yang terdaftar
    icon.stop()

def setup_and_run_tray():
    """Mempersiapkan dan menjalankan ikon di system tray."""
    # Buat menu yang akan muncul saat ikon di-klik kanan
    menu = (
        pystray.MenuItem(f"Shortcut: {SHORTCUT_KEY.upper()}", None, enabled=False), # Teks info, tidak bisa diklik
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Keluar", exit_action)
    )

    # Buat ikon dengan gambar dan menu
    image = create_image()
    icon = pystray.Icon("ocr_scanner", image, "Peluncur Mode Pindai", menu)
    
    # Daftarkan hotkey global
    try:
        keyboard.add_hotkey(SHORTCUT_KEY, start_visual_ocr)
        print(f"Aplikasi berjalan di background. Tekan '{SHORTCUT_KEY}' untuk memulai.")
    except Exception as e:
        print(f"Gagal mendaftarkan hotkey: {e}\nCoba jalankan sebagai Administrator.")
        return

    # Jalankan ikon (ini akan memblokir thread utama, menjaga skrip tetap hidup)
    icon.run()

if __name__ == "__main__":
    ocr_process = None
    setup_and_run_tray()