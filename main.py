import sys
import pyperclip
import pytesseract
import numpy as np
import mss
import cv2
import requests  # Brukes for å kalle LLM-endepunktet
from PyQt5.QtWidgets import QApplication, QWidget, QRubberBand, QPushButton, QVBoxLayout, QTextEdit
from PyQt5.QtCore import QRect, QSize, Qt
from PyQt5.QtGui import QGuiApplication
from pygments import highlight  # Brukes for syntax highlighting
from pygments.lexers import guess_lexer
from pygments.formatters import HtmlFormatter

# Angi bane til Tesseract installasjon
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def generate_comment(code):
    """
    Sender koden til LLM (LM Studio) for å få kommentarer og forbedret lesbarhet.
    Oppdatert i henhold til LM Studio-responsen med forbedret feilhåndtering og variabelnavngivning.
    """
    prompt = f"Please comment and improve the following code:\n\n{code}"
    url = "http://10.0.0.22:1234/v1/completions"  # Oppdater dette til riktig LM Studio-endepunkt
    try:
        response = requests.post(url, json={"prompt": prompt})
        if response.status_code == 200:
            # Forvent at LLM returnerer JSON med et 'text'-felt
            text = response.json().get("text", "No response text received")
            return text
        else:
            return f"LLM error: {response.status_code}"
    except Exception as e:
        return f"LLM exception: {str(e)}"


def syntax_highlight_code(code):
    """
    Bruker Pygments for å gjette språk og formatere koden med syntax highlighting.
    Returnerer HTML som kan vises i en QTextEdit.
    """
    try:
        lexer = guess_lexer(code)
    except Exception:
        from pygments.lexers import PythonLexer
        lexer = PythonLexer()
    # Bruker 'colorful' tema og legger til linjenumre
    formatter = HtmlFormatter(style='colorful', full=True, linenos=True)
    highlighted_code = highlight(code, lexer, formatter)
    return highlighted_code


class ScreenCaptureTool(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        # Fjern vindusramme for å unngå offset fra tittelbaren
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("Select Code Area")
        # Sett vinduet til å dekke hele skjermen
        self.setGeometry(0, 0, QApplication.desktop().width(), QApplication.desktop().height())
        self.setWindowOpacity(0.3)  # Gjør vinduet gjennomsiktig
        self.start_pos = None
        self.end_pos = None
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        # Hent skjermens DPI-skaleringsfaktor
        self.dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        self.show()

    def mousePressEvent(self, event):
        # Bruk globale posisjoner for nøyaktige koordinater
        self.start_pos = event.globalPos()
        self.rubber_band.setGeometry(QRect(self.start_pos, QSize()))
        self.rubber_band.show()

    def mouseMoveEvent(self, event):
        if self.start_pos:
            self.rubber_band.setGeometry(QRect(self.start_pos, event.globalPos()).normalized())

    def mouseReleaseEvent(self, event):
        # Lagre sluttposisjonen med globale koordinater
        self.end_pos = event.globalPos()
        self.capture_screen()
        self.close()

    def capture_screen(self):
        # Beregn koordinater og dimensjoner for den valgte regionen
        x1, y1 = self.start_pos.x(), self.start_pos.y()
        x2, y2 = self.end_pos.x(), self.end_pos.y()
        x, y, w, h = min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)

        # Juster koordinatene etter skjermens DPI-skaleringsfaktor
        x = int(x * self.dpr)
        y = int(y * self.dpr)
        w = int(w * self.dpr)
        h = int(h * self.dpr)

        with mss.mss() as sct:
            # Fang skjermbildet for det valgte området
            screenshot = sct.grab({'left': x, 'top': y, 'width': w, 'height': h})
            img = np.array(screenshot)
            # Konverter fra BGRA til BGR
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            # Konverter bildet til gråskala for bedre tekstgjenkjenning
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Bruk Otsu's terskling for å lage et binært bilde
            _, img_thresh = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Oppskaler bildet for å forbedre OCR-nøyaktigheten
            img_upscaled = cv2.resize(img_thresh, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

            # Bruk en whitelist for kode-tegn for å forbedre nøyaktigheten
            config = '--oem 3 --psm 6 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"\':=()'
            extracted_text = pytesseract.image_to_string(img_upscaled, config=config)
            extracted_text = extracted_text.strip()

            if extracted_text:
                # Kopier den gjenkjente teksten til utklippstavlen
                pyperclip.copy(extracted_text)
                self.parent.display_extracted_text(extracted_text)
            else:
                self.parent.display_extracted_text("Error: No text detected in selection.")


class CaptureLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Code Extractor")
        self.setGeometry(100, 100, 800, 600)  # Økt vindusstørrelse for flere elementer
        self.captured_code = ""

        # Opprett hovedlayout
        layout = QVBoxLayout()

        # Knapp for å starte skjermfangst
        self.capture_button = QPushButton("Capture Code")
        self.capture_button.clicked.connect(self.launch_capture)
        layout.addWidget(self.capture_button)

        # Tekstfelt for rå (ekstrahert) kode
        self.raw_code_display = QTextEdit()
        self.raw_code_display.setReadOnly(True)
        layout.addWidget(self.raw_code_display)

        # Knapp for å få LLM til å kommentere koden
        self.comment_button = QPushButton("Comment Code")
        self.comment_button.clicked.connect(self.comment_code)
        layout.addWidget(self.comment_button)

        # Tekstfelt for LLM-kommentert kode
        self.commented_code_display = QTextEdit()
        self.commented_code_display.setReadOnly(True)
        layout.addWidget(self.commented_code_display)

        # Knapp for syntax highlighting av koden
        self.highlight_button = QPushButton("Highlight Code")
        self.highlight_button.clicked.connect(self.highlight_code)
        layout.addWidget(self.highlight_button)

        # Tekstfelt for syntax-highlightet kode (HTML-støttet)
        self.highlighted_code_display = QTextEdit()
        self.highlighted_code_display.setReadOnly(True)
        self.highlighted_code_display.setAcceptRichText(True)
        layout.addWidget(self.highlighted_code_display)

        self.setLayout(layout)
        self.show()

    def launch_capture(self):
        # Start skjermfangstverktøyet
        self.capture_tool = ScreenCaptureTool(self)

    def display_extracted_text(self, text):
        # Vis den ekstraherte (rå) koden
        self.captured_code = text
        self.raw_code_display.setPlainText(text)

    def comment_code(self):
        # Kaller LLM for å kommentere koden
        if not self.captured_code:
            self.commented_code_display.setPlainText("No code captured.")
            return
        self.commented_code_display.setPlainText("Processing with LLM...")
        commented = generate_comment(self.captured_code)
        self.commented_code_display.setPlainText(commented)

    def highlight_code(self):
        # Bruker Pygments for syntax highlighting
        if not self.captured_code:
            self.highlighted_code_display.setPlainText("No code captured.")
            return
        highlighted_html = syntax_highlight_code(self.captured_code)
        self.highlighted_code_display.setHtml(highlighted_html)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CaptureLauncher()
    sys.exit(app.exec_())
