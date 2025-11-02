"""Main entry point for the MP3paraMIDI application."""

import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from .gui import MainWindow


def main() -> None:
    """Run the MP3paraMIDI application."""
    try:
        # Create the application
        app = QApplication(sys.argv)
        
        # Set application-wide style
        app.setStyle("Fusion")
        
        # Create and show the main window
        window = MainWindow()
        window.show()
        
        # Run the event loop
        sys.exit(app.exec())
    except Exception as e:
        # Show error message if something goes wrong
        error_msg = QMessageBox()
        error_msg.setIcon(QMessageBox.Icon.Critical)
        error_msg.setWindowTitle("Error")
        error_msg.setText("An unexpected error occurred")
        error_msg.setDetailedText(str(e))
        error_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        error_msg.exec()
        sys.exit(1)


if __name__ == "__main__":
    main()
