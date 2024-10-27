from PyQt6 import QtWidgets, QtCore
from tqdm import tqdm


class TqdmProgressBar(tqdm):
    def __init__(self, log_emitter, *args, **kwargs):
        """Класс для интеграции tqdm с обновлением progress bar через сигнал"""
        super().__init__(*args, **kwargs)
        self.log_emitter = log_emitter  # Эмиттер для сигналов

    def update(self, n=1):
        """Переопределение метода обновления прогресса"""
        super().update(n)  # Вызываем оригинальный метод обновления

        # Передаем прогресс через сигнал
        if self.total:
            progress = int((self.n / self.total) * 100)  # Рассчитываем процент выполнения
            self.log_emitter.progress_signal.emit(progress)


class LogEmitter(QtCore.QObject):
    log_signal = QtCore.pyqtSignal(str)
    progress_signal = QtCore.pyqtSignal(int)
    stop_signal = QtCore.pyqtSignal()


class LogWindow(QtWidgets.QWidget):
    def __init__(self, log_emitter):
        super().__init__()
        self.setWindowTitle("Логи расчета")
        self.setGeometry(100, 100, 600, 400)

        # Текстовое поле для вывода логов
        self.log_area = QtWidgets.QTextEdit(self)
        self.log_area.setReadOnly(True)

        # Кнопка для прерывания расчета
        self.stop_button = QtWidgets.QPushButton("Прервать расчет")

        # Прогресс-бар
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setMaximum(100)  # Максимум 100%, будет обновляться от 0 до 100

        # Горизонтальный макет для кнопки и спейсера
        button_layout = QtWidgets.QHBoxLayout()

        # Горизонтальный спейсер для выравнивания кнопки справа
        button_layout.addWidget(self.progress_bar)
        button_layout.addWidget(self.stop_button)

        # Основной вертикальный макет
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.log_area)  # Логи сверху
        layout.addLayout(button_layout)  # Кнопка снизу
        self.setLayout(layout)

        # Привязка сигналов
        self.log_emitter = log_emitter
        self.log_emitter.log_signal.connect(self.write_log)  # Логи поступают через сигнал
        self.log_emitter.progress_signal.connect(self.update_progress_bar)  # Обновление прогресса
        self.log_emitter.stop_signal.connect(self.stop_calculation)  # Остановка процесса

        # При закрытии или нажатии "Прервать" вызовем stop_calculation
        self.stop_button.clicked.connect(self.stop_calculation)
        self.log_emitter.stop_signal.connect(self.stop_calculation)

        self.show()

    def write_log(self, message):
        """Добавление логов в текстовое поле"""
        self.log_area.append(message)
        self.log_area.ensureCursorVisible()

    def update_progress_bar(self, value):
        """Обновление значения прогресс-бара"""
        self.progress_bar.setValue(value)

    def stop_calculation(self, process):
        """Метод для отправки сигнала о прерывании расчета"""
        self.log_emitter.log_signal.emit("Расчет остановлен")
        self.log_emitter.stop_signal.emit()  # Передаем сигнал для остановки

    def closeEvent(self, event):
        """Обработчик закрытия окна - отправка сигнала о прерывании расчета"""
        self.log_emitter.stop_signal.emit()  # При закрытии окна расчет прерывается
        event.accept()  # Закрыть окно
