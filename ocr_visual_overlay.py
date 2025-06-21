import pytesseract
from PIL import Image, ImageTk
import mss
import tkinter as tk
from tkinter import Canvas, messagebox, ttk
import os
import ctypes
import cv2
import numpy as np
import pyperclip
from deep_translator import GoogleTranslator
import threading

# --- PENGATURAN DPI AWARENESS ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except AttributeError:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception as e:
        print(f"Tidak dapat mengatur DPI awareness: {e}")

# --- Konfigurasi Path Tesseract ---
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_PATH = r"C:\Program Files\Tesseract-OCR\tessdata"

# --- Pengaturan OCR & Tampilan yang Dapat Diubah ---
OVERLAY_SCALE_FACTOR = 1.25 
UPSCALE_FACTOR = 2
PSM_MODE = '11' 
CONFIDENCE_THRESHOLD = 30 

class SnippingTool(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # --- PERBAIKAN BARU ---
        # 1. Hapus semua dekorasi jendela (title bar, border) untuk kontrol penuh.
        self.overrideredirect(True)
        # --- AKHIR PERBAIKAN ---
        
        self.start_canvas_x = self.start_canvas_y = 0
        self.start_abs_x = self.start_abs_y = 0
        self.v_screen_x = 0
        self.v_screen_y = 0

        try:
            SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
            SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79

            self.v_screen_x = ctypes.windll.user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            self.v_screen_y = ctypes.windll.user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            v_screen_width = ctypes.windll.user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            v_screen_height = ctypes.windll.user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            
            self.geometry(f'{v_screen_width}x{v_screen_height}+{self.v_screen_x}+{self.v_screen_y}')

            # --- PERBAIKAN BARU ---
            # 2. Paksa Tkinter untuk segera menerapkan perubahan geometri di atas.
            self.update_idletasks()
            # --- AKHIR PERBAIKAN ---

        except Exception as e:
            print(f"Gagal mendapatkan metrik virtual screen, kembali ke fullscreen biasa: {e}")
            self.attributes("-fullscreen", True)

        self.attributes("-alpha", 0.3)
        self.config(bg='black')
        self.canvas = tk.Canvas(self, cursor="cross", bg='grey')
        self.canvas.pack(fill="both", expand=True)
        
        self.rect = None
        self.selection = None
        
        self.bind("<ButtonPress-1>", self.on_start)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", lambda e: self.destroy())

    def on_start(self, e):
        self.start_canvas_x = self.canvas.canvasx(e.x)
        self.start_canvas_y = self.canvas.canvasy(e.y)
        self.start_abs_x = e.x_root
        self.start_abs_y = e.y_root
        self.rect = self.canvas.create_rectangle(
            self.start_canvas_x, self.start_canvas_y, 
            self.start_canvas_x, self.start_canvas_y, 
            outline='red', width=2
        )

    def on_drag(self, e):
        current_canvas_x = self.canvas.canvasx(e.x)
        current_canvas_y = self.canvas.canvasy(e.y)
        self.canvas.coords(
            self.rect, self.start_canvas_x, self.start_canvas_y, 
            current_canvas_x, current_canvas_y
        )

    def on_release(self, e):
        abs_x1 = min(self.start_abs_x, e.x_root)
        abs_y1 = min(self.start_abs_y, e.y_root)
        width = abs(self.start_abs_x - e.x_root)
        height = abs(self.start_abs_y - e.y_root)

        if width > 0 and height > 0:
            self.selection = (abs_x1, abs_y1, width, height)
            
        self.destroy()


def show_error(title, message):
    cv2.destroyAllWindows()
    root = tk.Tk(); root.withdraw()
    messagebox.showerror(title, message)
    root.destroy()

def group_words_into_lines(ocr_data, min_confidence):
    lines = {}
    for i in range(len(ocr_data['text'])):
        conf = int(ocr_data['conf'][i])
        if conf > min_confidence:
            text = ocr_data['text'][i].strip()
            if text:
                line_id = (ocr_data['block_num'][i], ocr_data['par_num'][i], ocr_data['line_num'][i])
                word_data = {
                    'text': text, 'left': ocr_data['left'][i], 'top': ocr_data['top'][i],
                    'width': ocr_data['width'][i], 'height': ocr_data['height'][i]
                }
                if line_id not in lines: lines[line_id] = []
                lines[line_id].append(word_data)
                
    line_boxes = []
    for line_id in sorted(lines.keys()):
        words_in_line = lines[line_id]
        if not words_in_line: continue
        full_text = " ".join([word['text'] for word in words_in_line])
        left = min([word['left'] for word in words_in_line])
        top = min([word['top'] for word in words_in_line])
        right = max([word['left'] + word['width'] for word in words_in_line])
        bottom = max([word['top'] + word['height'] for word in words_in_line])
        line_boxes.append({'text': full_text, 'left': left, 'top': top, 'width': right - left, 'height': bottom - top})
    return line_boxes

def main():
    snipper = SnippingTool(); snipper.mainloop()
    if not snipper.selection: return

    try:
        selection_x, selection_y, selection_w, selection_h = snipper.selection
        
        monitor = {"left": selection_x, "top": selection_y, "width": selection_w, "height": selection_h}

        with mss.mss() as sct:
            sct_img = sct.grab(monitor)
            img_np = np.array(sct_img)
            img_cv = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
            img_pil_original = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))

        gray_img = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        if UPSCALE_FACTOR > 1:
            gray_img = cv2.resize(gray_img, (int(gray_img.shape[1] * UPSCALE_FACTOR), int(gray_img.shape[0] * UPSCALE_FACTOR)), interpolation=cv2.INTER_CUBIC)
        _, img_ocr = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        os.environ['TESSDATA_PREFIX'] = TESSDATA_PATH
        ocr_config = f'--psm {PSM_MODE} --oem 3'
        ocr_data = pytesseract.image_to_data(img_ocr, lang='jpn+eng', config=ocr_config, output_type=pytesseract.Output.DICT)
        
        line_boxes = group_words_into_lines(ocr_data, CONFIDENCE_THRESHOLD)
        
        root = tk.Tk()
        TOP_PANEL_HEIGHT = 40 
        new_w = int(selection_w * OVERLAY_SCALE_FACTOR)
        new_h = int(selection_h * OVERLAY_SCALE_FACTOR)
        new_x = selection_x
        new_y = selection_y + selection_h + 10 
        root.title("統 OCR Visual Overlay")
        root.geometry(f"{new_w}x{new_h + TOP_PANEL_HEIGHT}+{new_x}+{new_y}")
        root.attributes('-topmost', True)
        top_frame = tk.Frame(root, height=TOP_PANEL_HEIGHT, bg="#282c34")
        top_frame.pack(fill='x', side='top')
        top_frame.pack_propagate(False)

        text_entries = []
        is_translated = False

        def _translation_worker(text_block, target_lang_code):
            try:
                translated_block = GoogleTranslator(source='auto', target=target_lang_code).translate(text_block)
                root.after(0, _on_translation_complete, translated_block)
            except Exception as e:
                root.after(0, _on_translation_error, e)

        def _on_translation_complete(translated_block):
            nonlocal is_translated
            translated_lines = translated_block.split('\n') if translated_block else []
            
            if len(translated_lines) == len(text_entries):
                for i, entry_data in enumerate(text_entries):
                    entry_data['translated'] = translated_lines[i]
            else:
                full_translated_text = " ".join(translated_lines)
                messagebox.showwarning("Peringatan", f"Jumlah baris terjemahan tidak cocok. Menampilkan sebagai satu blok:\n\n{full_translated_text}", parent=root)
                for entry_data in text_entries:
                    entry_data['translated'] = full_translated_text

            is_translated = True
            update_text_display()
            toggle_button.config(state='normal')
            translate_button.config(state='normal', text="🌐 Terjemahkan")

        def _on_translation_error(e):
            show_error("Translation Error", f"Gagal menerjemahkan teks: \n{e}")
            translate_button.config(state='normal', text="🌐 Terjemahkan")

        def start_translation_thread():
            if not line_boxes:
                messagebox.showinfo("Info", "Tidak ada teks untuk diterjemahkan.", parent=root)
                return

            target_lang_name = lang_combobox.get()
            if not target_lang_name:
                messagebox.showwarning("Peringatan", "Pilih bahasa tujuan.", parent=root)
                return
            
            target_lang_code = lang_options[target_lang_name]
            translate_button.config(state='disabled', text="Menerjemahkan...")
            original_texts = [entry['original'] for entry in text_entries]
            text_to_translate = "\n".join(original_texts)

            thread = threading.Thread(target=_translation_worker, args=(text_to_translate, target_lang_code))
            thread.daemon = True
            thread.start()

        def toggle_translation():
            nonlocal is_translated
            is_translated = not is_translated
            update_text_display()

        def update_text_display():
            key_to_display = 'translated' if is_translated else 'original'
            for entry_data in text_entries:
                entry_data['var'].set(entry_data.get(key_to_display, ''))
            
            toggle_button.config(text="Lihat Asli" if is_translated else "Lihat Terjemahan")
        
        def open_text_selector():
            try:
                selector_window = tk.Toplevel(root)
                selector_window.title("Pilih & Salin Teks")
                selector_window.geometry("500x400")
                selector_window.transient(root)
                selector_window.grab_set()
                
                info_label = tk.Label(selector_window, text="Pilih teks yang Anda inginkan (gunakan Ctrl+C untuk menyalin).", padx=10, pady=5)
                info_label.pack(side='top', fill='x')

                text_frame = tk.Frame(selector_window)
                text_frame.pack(expand=True, fill='both', padx=10, pady=(0,10))
                scrollbar = tk.Scrollbar(text_frame)
                scrollbar.pack(side='right', fill='y')
                text_widget = tk.Text(text_frame, wrap='word', undo=True, yscrollcommand=scrollbar.set, font=('Segoe UI', 11))
                text_widget.pack(expand=True, fill='both')
                scrollbar.config(command=text_widget.yview)

                key_to_get = 'translated' if is_translated and any(e.get('translated') for e in text_entries) else 'original'
                texts_list = [entry.get(key_to_get, entry['original']) for entry in text_entries]
                current_text_to_display = "\n".join(texts_list)
                text_widget.insert('1.0', current_text_to_display)

            except Exception as e:
                messagebox.showerror("Error", f"Gagal membuka jendela seleksi teks:\n{e}", parent=root)

        full_text_for_copy = "\n".join([line['text'] for line in line_boxes])
        def copy_all_text():
            try:
                text_to_copy = full_text_for_copy
                if is_translated:
                    translated_texts = [entry.get('translated', '') for entry in text_entries]
                    text_to_copy = "\n".join(translated_texts)
                
                if not text_to_copy.strip(): return
                pyperclip.copy(text_to_copy)
                copy_button.config(text="✔ Tersalin")
                root.after(1500, lambda: copy_button.config(text="📋 Salin Semua"))
            except Exception as e:
                print(f"Gagal menyalin: {e}. Pastikan pyperclip terinstal.")
        
        copy_button = tk.Button(top_frame, text="📋 Salin Semua", command=copy_all_text, bg="#4CAF50", fg="white", activebackground="#45a049", activeforeground="white", relief="flat", bd=0, font=('Segoe UI', 10, 'bold'))
        copy_button.pack(pady=5, padx=10, side='left')
        
        select_button = tk.Button(top_frame, text="📝 Pilih Teks", command=open_text_selector, bg="#FFC107", fg="black", activebackground="#e0a800", activeforeground="black", relief="flat", bd=0, font=('Segoe UI', 10, 'bold'))
        select_button.pack(pady=5, padx=(0, 10), side='left')

        lang_options = {"Indonesian": "id", "English": "en", "Japanese": "ja"}
        lang_combobox = ttk.Combobox(top_frame, values=list(lang_options.keys()), state='readonly', width=12, font=('Segoe UI', 9))
        lang_combobox.pack(pady=5, side='left')
        lang_combobox.set("Indonesian")

        translate_button = tk.Button(top_frame, text="🌐 Terjemahkan", command=start_translation_thread, bg="#008CBA", fg="white", activebackground="#007ba7", activeforeground="white", relief="flat", bd=0, font=('Segoe UI', 10, 'bold'))
        translate_button.pack(pady=5, padx=10, side='left')

        toggle_button = tk.Button(top_frame, text="Lihat Terjemahan", command=toggle_translation, bg="#f44336", fg="white", activebackground="#da190b", activeforeground="white", relief="flat", bd=0, font=('Segoe UI', 10, 'bold'), state='disabled')
        toggle_button.pack(pady=5, padx=10, side='left')

        canvas = tk.Canvas(root, width=new_w, height=new_h, highlightthickness=0)
        canvas.pack(fill='both', expand=True, side='bottom')
        img_display = img_pil_original.resize((new_w, new_h), Image.LANCZOS)
        screenshot_tk = ImageTk.PhotoImage(img_display)
        canvas.create_image(0, 0, image=screenshot_tk, anchor='nw')
        canvas.image = screenshot_tk
        processed_height, processed_width = img_ocr.shape[:2]
        width_ratio = new_w / processed_width
        height_ratio = new_h / processed_height

        for line in line_boxes:
            text = line['text']
            x = int(line['left'] * width_ratio)
            y = int(line['top'] * height_ratio)
            w = int(line['width'] * width_ratio)
            h = int(line['height'] * height_ratio)
            entry_var = tk.StringVar(value=text)
            entry = tk.Entry(canvas, textvariable=entry_var, bd=0, highlightthickness=1, highlightbackground="cyan", highlightcolor="cyan", font=('Arial', 10, 'bold'), fg='black', bg='white', state='readonly', readonlybackground='white')
            
            # Padding vertikal untuk menutupi celah antar kotak teks
            canvas.create_window(x, y - 1, window=entry, anchor='nw', width=w, height=h + 2)
            
            text_entries.append({'var': entry_var, 'original': text, 'translated': '', 'widget': entry})
        
        root.lift(); root.attributes('-topmost',True); root.after_idle(root.attributes,'-topmost',False)
        root.mainloop()

    except Exception as e:
        show_error("Error", f"Terjadi error tak terduga:\n{e}")
    finally:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()