"""Xpl0it00ls - простой менеджер iPhone (инфо об устройстве, батарея, перезагрузка)."""
import sys
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QListWidget, QTableWidget, QTableWidgetItem, QPushButton,
                               QLabel, QMessageBox, QHeaderView)

from pymobiledevice3.usbmux import list_devices
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.diagnostics import DiagnosticsService

INFO_KEYS = [
    ("DeviceName", "Имя"), ("ProductType", "Модель (ID)"), ("ProductVersion", "iOS"),
    ("BuildVersion", "Сборка"), ("SerialNumber", "Серийный номер"),
    ("UniqueDeviceID", "UDID"), ("PhoneNumber", "Номер"), ("CPUArchitecture", "CPU"),
    ("ModelNumber", "Модель"), ("RegionInfo", "Регион"), ("ActivationState", "Активация"),
]


def read_device(serial):
    ld = create_using_usbmux(serial=serial)  # при первом подключении покажет «Доверять» на iPhone
    vals = ld.all_values
    rows = [(label, str(vals.get(k, "—"))) for k, label in INFO_KEYS]
    try:
        b = ld.get_value(domain="com.apple.mobile.battery")
        rows.append(("Заряд", f"{b.get('BatteryCurrentCapacity', '?')}%"
                              f"{' (заряжается)' if b.get('BatteryIsCharging') else ''}"))
    except Exception:
        pass
    return rows


class Scanner(QThread):
    found = Signal(list)

    def run(self):
        try:
            self.found.emit([d.serial for d in list_devices()])
        except Exception as e:
            self.found.emit([f"__error__:{e}"])


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xpl0it00ls")
        self.resize(820, 520)
        root = QWidget(); self.setCentralWidget(root)
        lay = QHBoxLayout(root)

        left = QVBoxLayout()
        self.devices = QListWidget(); self.devices.setMaximumWidth(260)
        self.devices.currentTextChanged.connect(self.show_info)
        btn_refresh = QPushButton("Обновить"); btn_refresh.clicked.connect(self.refresh)
        left.addWidget(QLabel("Устройства")); left.addWidget(self.devices); left.addWidget(btn_refresh)

        right = QVBoxLayout()
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.status = QLabel("")
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        btn_reboot = QPushButton("Перезагрузить iPhone"); btn_reboot.clicked.connect(self.reboot)
        right.addWidget(self.table); right.addWidget(self.status); right.addWidget(btn_reboot)

        lay.addLayout(left); lay.addLayout(right, 1)
        self.refresh()

    def refresh(self):
        self.status.setText("Поиск устройств…")
        self.scanner = Scanner(); self.scanner.found.connect(self.on_found); self.scanner.start()

    def on_found(self, serials):
        self.devices.clear()
        if serials and serials[0].startswith("__error__:"):
            self.status.setText(
                "Не удалось связаться с usbmuxd: " + serials[0][10:] +
                "\nWindows: установите «Apple Devices» из Microsoft Store (iTunes не нужен) "
                "или драйвер Apple Mobile Device. Linux: sudo apt install usbmuxd.")
            return
        self.devices.addItems(serials)
        self.status.setText(f"Найдено устройств: {len(serials)}" if serials
                            else "iPhone не найден. Подключите кабель и разблокируйте экран.")
        if serials:
            self.devices.setCurrentRow(0)

    def show_info(self, serial):
        if not serial:
            return
        try:
            rows = read_device(serial)
        except Exception as e:
            self.status.setText(f"Ошибка: {e}\nНажмите «Доверять» на iPhone и повторите.")
            return
        self.table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(k))
            self.table.setItem(i, 1, QTableWidgetItem(v))

    def reboot(self):
        item = self.devices.currentItem()
        if not item:
            return
        if QMessageBox.question(self, "Xpl0it00ls", "Перезагрузить устройство?") != QMessageBox.Yes:
            return
        try:
            DiagnosticsService(create_using_usbmux(serial=item.text())).restart()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))


def main():
    app = QApplication(sys.argv)
    w = Window(); w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
