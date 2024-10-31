from PyQt6 import QtWidgets, QtGui
from tqdm import tqdm


class LogWindow(QtWidgets.QWidget):
    def __init__(self, calculation_thread, main_window):
        super().__init__()
        self.calculation_thread = calculation_thread
        self.main_window = main_window
        self.setWindowTitle("Выполнение расчета")
        self.setGeometry(100, 100, 600, 400)

        # UI components
        self.log_area = QtWidgets.QTextEdit(readOnly=True)
        self.progress_bar = QtWidgets.QProgressBar(maximum=100)
        self.stop_button = QtWidgets.QPushButton("Прервать расчет")
        self.setWindowIcon(QtGui.QIcon('Icon.png'))

        # Layout
        hbox_layout = QtWidgets.QHBoxLayout()
        hbox_layout.addWidget(self.progress_bar)
        hbox_layout.addWidget(self.stop_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.log_area)
        layout.addLayout(hbox_layout)
        self.setLayout(layout)

        # Signals connect
        # self.calculation_thread.log_signal.connect(self.log_area.append)
        self.calculation_thread.progress_signal.connect(self.progress_bar.setValue)
        self.calculation_thread.finished_signal.connect(self.on_calculation_finished)
        self.calculation_thread.stop_signal.connect(self.stop_calculation)
        self.stop_button.clicked.connect(self.stop_calculation)

    def stop_calculation(self):
        self.log_area.append("Расчет остановлен")
        self.calculation_thread.stop()
        self.calculation_thread.terminate()  # Остановка расчета
        self.stop_button.setDisabled(True)
        self.main_window.setEnabled(True)

    def on_calculation_finished(self):
        self.stop_button.setDisabled(True)  # Отключение кнопки после завершения
        self.main_window.setEnabled(True)

    def closeEvent(self, event):
        if self.stop_button.isEnabled():
            self.stop_calculation()  # Остановка расчета при закрытии окна
        self.main_window.setEnabled(True)
        event.accept()
