from django.apps import AppConfig
import threading
import easyocr

class IdentityVerifierAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "identity_verifier_app"
    reader = None
    _reader_lock = threading.Lock() 

    def get_reader(self):
        return self.reader

    def ready(self):
        t = threading.Thread(target=self._load_reader)
        t.start()
        t.join()

    def _load_reader(self):
        with self._reader_lock:
            if self.reader is None:  
                try:
                    self.reader = easyocr.Reader(["en"]) 
                except Exception as e:
                    print(f"Error loading EasyOCR reader: {e}")