import sys
import pyperclip
import pytesseract
import numpy as np
import mss
import cv2
from PyQt5.QtWidgets import QApplication, QWidget, QRubberBand, QPushButton, QVBoxLayout, QLabel, QTextEdit
from PyQt5.QtCore import QRect, QPoint, QSize

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"




class ScreenCaptureTool(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Select Code Area")
        self.setGeometry(0, 0, QApplication.desktop().width(), QApplication.desktop().height())
        self.setWindowOpacity(0.3)  # Make window transparent
        self.start_pos = None
        self.end_pos = None
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.show()

    def mousePressEvent(self, event):
        self.start_pos = event.pos()
        self.rubber_band.setGeometry(QRect(self.start_pos, QSize()))
        self.rubber_band.show()

    def mouseMoveEvent(self, event):
        if self.start_pos:
            self.rubber_band.setGeometry(QRect(self.start_pos, event.pos()).normalized())

    def mouseReleaseEvent(self, event):
        self.end_pos = event.pos()
        self.capture_screen()
        self.close()

    def capture_screen(self):
        x1, y1 = self.start_pos.x(), self.start_pos.y()
        x2, y2 = self.end_pos.x(), self.end_pos.y()
        x, y, w, h = min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)

        with mss.mss() as sct:
            screenshot = sct.grab({'left': x, 'top': y, 'width': w, 'height': h})
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            extracted_text = pytesseract.image_to_string(img_gray)
            if extracted_text.strip():
                pyperclip.copy(extracted_text)
                self.parent.display_extracted_text(extracted_text)
            else:
                self.parent.display_extracted_text("Error: No text detected in selection.")


class CaptureLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Code Extractor")
        self.setGeometry(100, 100, 500, 300)

        layout = QVBoxLayout()
        self.button = QPushButton("Capture Code")
        self.button.clicked.connect(self.launch_capture)
        layout.addWidget(self.button)

        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        layout.addWidget(self.text_display)

        self.setLayout(layout)
        self.show()

    def launch_capture(self):
        self.capture_tool = ScreenCaptureTool(self)

    def display_extracted_text(self, text):
        self.text_display.setPlainText(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CaptureLauncher()
    sys.exit(app.exec_())