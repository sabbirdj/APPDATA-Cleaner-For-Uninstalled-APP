import sys
import os

def run_fluent():
    from PyQt6.QtWidgets import QApplication
    from ui_fluent.main_window import MainWindow
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

def run_classic():
    import customtkinter as ctk
    from ui.app import AppDataCleanerApp

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = AppDataCleanerApp()
    app.mainloop()

if __name__ == "__main__":
    # If user specifies --classic, use CustomTkinter; otherwise modern Fluent UI
    if "--classic" in sys.argv:
        run_classic()
    else:
        run_fluent()
