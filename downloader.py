import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import requests
from bs4 import BeautifulSoup
import os
import threading
import logging
from urllib.parse import urljoin, urlparse
import queue

# --- تنظیمات اولیه لاگ‌گیری ---
# تمام اتفاقات در ترمینال با فرمت مشخص ثبت می‌شوند
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class DownloadManagerApp:
    """
    کلاس اصلی برنامه مدیر دانلود
    """
    def __init__(self, root):
        self.root = root
        self.root.title("مدیر دانلود حرفه‌ای")
        self.root.geometry("900x600")

        self.download_path = os.getcwd()  # مسیر پیش‌فرض برای دانلود
        self.file_queue = queue.Queue() # صف برای ارتباط بین تردها و رابط کاربری

        self.setup_ui()
        self.process_queue()

    def setup_ui(self):
        """
        طراحی و ساخت رابط کاربری برنامه
        """
        # --- فریم بالا برای ورودی URL ---
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="آدرس سایت (URL):").pack(side=tk.LEFT, padx=(0, 5))
        self.url_entry = ttk.Entry(top_frame, width=60)
        self.url_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.scrape_button = ttk.Button(top_frame, text="بررسی و یافتن فایل‌ها", command=self.start_scraping)
        self.scrape_button.pack(side=tk.LEFT, padx=(5, 0))

        # --- فریم میانی برای لیست فایل‌ها ---
        middle_frame = ttk.Frame(self.root, padding="10")
        middle_frame.pack(expand=True, fill=tk.BOTH)

        # ستون‌های جدول
        columns = ("file_name", "file_type", "file_size", "status", "url")
        self.tree = ttk.Treeview(middle_frame, columns=columns, show="headings")
        
        self.tree.heading("file_name", text="نام فایل")
        self.tree.heading("file_type", text="نوع")
        self.tree.heading("file_size", text="حجم")
        self.tree.heading("status", text="وضعیت")
        self.tree.heading("url", text="لینک")

        # تنظیم عرض ستون‌ها
        self.tree.column("file_name", width=300)
        self.tree.column("file_type", width=80)
        self.tree.column("file_size", width=100)
        self.tree.column("status", width=150)
        self.tree.column("url", width=250)

        # اضافه کردن اسکرول‌بار
        scrollbar = ttk.Scrollbar(middle_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- فریم پایین برای دکمه‌ها و مسیر ---
        bottom_frame = ttk.Frame(self.root, padding="10")
        bottom_frame.pack(fill=tk.X)

        self.path_label = ttk.Label(bottom_frame, text=f"مسیر دانلود: {self.download_path}")
        self.path_label.pack(side=tk.LEFT, pady=(5,0))

        self.choose_dir_button = ttk.Button(bottom_frame, text="انتخاب پوشه", command=self.choose_directory)
        self.choose_dir_button.pack(side=tk.RIGHT, padx=(5, 0))

        self.download_button = ttk.Button(bottom_frame, text="دانلود فایل‌های انتخاب شده", command=self.start_downloading)
        self.download_button.pack(side=tk.RIGHT)

    def choose_directory(self):
        """
        پنجره انتخاب پوشه برای ذخیره فایل‌ها را باز می‌کند
        """
        path = filedialog.askdirectory(title="پوشه مقصد را انتخاب کنید")
        if path:
            self.download_path = path
            self.path_label.config(text=f"مسیر دانلود: {self.download_path}")
            logging.info(f"مسیر دانلود به {self.download_path} تغییر یافت.")

    def start_scraping(self):
        """
        یک ترد جدید برای بررسی URL و استخراج لینک‌ها ایجاد می‌کند
        """
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("خطا", "لطفاً یک آدرس اینترنتی معتبر وارد کنید.")
            return

        # پاک کردن لیست قبلی
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        logging.info(f"شروع بررسی سایت: {url}")
        self.scrape_button.config(state=tk.DISABLED) # غیرفعال کردن دکمه تا پایان عملیات
        
        # اجرای عملیات در یک ترد جداگانه برای جلوگیری از هنگ کردن UI
        threading.Thread(target=self.scrape_url, args=(url,), daemon=True).start()

    def scrape_url(self, url):
        """
        صفحه وب را دانلود و لینک‌های قابل دانلود را استخراج می‌کند
        این تابع در یک ترد جداگانه اجرا می‌شود
        """
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status() # بررسی خطاهای HTTP

            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a')
            
            found_files = set() # برای جلوگیری از افزودن لینک‌های تکراری

            # انواع فایل‌های رایج برای دانلود
            file_extensions = ['.zip', '.rar', '.exe', '.msi', '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mkv', '.avi', '.mp3', '.wav', '.doc', '.docx', '.xls', '.xlsx']

            for link in links:
                href = link.get('href')
                if href:
                    # تبدیل لینک‌های نسبی به مطلق
                    full_url = urljoin(url, href)
                    # بررسی اینکه آیا لینک یک فایل قابل دانلود است
                    if any(full_url.lower().endswith(ext) for ext in file_extensions):
                        if full_url not in found_files:
                            file_name = os.path.basename(urlparse(full_url).path)
                            file_type = os.path.splitext(file_name)[1]
                            # ارسال اطلاعات فایل به صف برای نمایش در UI
                            self.file_queue.put(("add_file", (file_name, file_type, "نامشخص", "آماده دانلود", full_url)))
                            found_files.add(full_url)
            
            if not found_files:
                logging.warning("هیچ فایل قابل دانلودی در این صفحه پیدا نشد.")
                self.file_queue.put(("scraping_done", "no_files"))
            else:
                 logging.info(f"بررسی کامل شد. {len(found_files)} فایل پیدا شد.")
                 self.file_queue.put(("scraping_done", "success"))

        except requests.exceptions.RequestException as e:
            logging.error(f"خطا در اتصال به {url}: {e}")
            self.file_queue.put(("error", f"خطا در اتصال: {e}"))
        except Exception as e:
            logging.error(f"یک خطای پیش‌بینی نشده در هنگام بررسی رخ داد: {e}")
            self.file_queue.put(("error", "یک خطای ناشناخته رخ داد."))

    def start_downloading(self):
        """
        برای هر فایل انتخاب شده، یک ترد دانلود جدید ایجاد می‌کند
        """
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("توجه", "لطفاً حداقل یک فایل را برای دانلود انتخاب کنید.")
            return

        logging.info(f"آماده‌سازی برای دانلود {len(selected_items)} فایل.")
        for item_id in selected_items:
            item_values = self.tree.item(item_id, 'values')
            url = item_values[4]
            status = item_values[3]
            
            if status not in ["در حال دانلود...", "کامل شد"]:
                self.tree.set(item_id, "status", "در صف...")
                # اجرای دانلود در یک ترد جداگانه
                threading.Thread(target=self.download_file, args=(item_id, url), daemon=True).start()
            else:
                logging.warning(f"فایل {url} در حال دانلود است یا قبلاً دانلود شده است. از آن صرف نظر شد.")

    def download_file(self, item_id, url):
        """
        یک فایل را از URL مشخص شده دانلود می‌کند
        این تابع در یک ترد جداگانه اجرا می‌شود
        """
        try:
            file_name = os.path.basename(urlparse(url).path)
            save_path = os.path.join(self.download_path, file_name)
            
            logging.info(f"شروع دانلود: {url} -> {save_path}")
            self.file_queue.put(("update_status", (item_id, "در حال دانلود...")))

            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # به‌روزرسانی وضعیت با درصد پیشرفت
                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 100
                        status_text = f"در حال دانلود... ({progress:.1f}%)"
                        self.file_queue.put(("update_status", (item_id, status_text)))

            # به‌روزرسانی حجم فایل پس از دانلود
            final_size_mb = f"{downloaded_size / (1024*1024):.2f} MB"
            self.file_queue.put(("update_size", (item_id, final_size_mb)))
            self.file_queue.put(("update_status", (item_id, "کامل شد")))
            logging.info(f"دانلود با موفقیت کامل شد: {file_name}")

        except requests.exceptions.RequestException as e:
            logging.error(f"خطا در دانلود {url}: {e}")
            self.file_queue.put(("update_status", (item_id, f"خطا: {e}")))
        except Exception as e:
            logging.error(f"خطای پیش‌بینی نشده در دانلود {url}: {e}")
            self.file_queue.put(("update_status", (item_id, "خطای ناشناخته")))

    def process_queue(self):
        """
        صف پیام را برای به‌روزرسانی UI از تردها پردازش می‌کند
        """
        try:
            while True:
                message_type, data = self.file_queue.get_nowait()
                if message_type == "add_file":
                    file_name, file_type, file_size, status, url = data
                    self.tree.insert("", tk.END, values=(file_name, file_type, file_size, status, url))
                
                elif message_type == "update_status":
                    item_id, status = data
                    if self.tree.exists(item_id):
                        self.tree.set(item_id, "status", status)

                elif message_type == "update_size":
                    item_id, size = data
                    if self.tree.exists(item_id):
                        self.tree.set(item_id, "file_size", size)

                elif message_type == "scraping_done":
                    self.scrape_button.config(state=tk.NORMAL) # فعال کردن مجدد دکمه
                    if data == "no_files":
                         messagebox.showinfo("اطلاعات", "هیچ فایل قابل دانلودی در این صفحه پیدا نشد.")
                
                elif message_type == "error":
                    self.scrape_button.config(state=tk.NORMAL)
                    messagebox.showerror("خطا", data)

        except queue.Empty:
            pass # اگر صف خالی بود، مشکلی نیست
        
        # این تابع هر 100 میلی‌ثانیه یکبار خودش را فراخوانی می‌کند
        self.root.after(100, self.process_queue)


if __name__ == "__main__":
    # --- کتابخانه‌های مورد نیاز ---
    # pip install requests beautifulsoup4
    
    root = tk.Tk()
    app = DownloadManagerApp(root)
    root.mainloop()

