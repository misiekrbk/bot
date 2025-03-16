# test_qt.py
import sys
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Qt")
        self.label = QLabel("Qt działa poprawnie!", self)
        self.setCentralWidget(self.label)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())