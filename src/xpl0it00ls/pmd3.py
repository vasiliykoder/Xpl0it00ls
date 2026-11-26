"""
Обёртка над pymobiledevice3: CLI-команды запускаются В ТОМ ЖЕ процессе
(через click-группу), а не через subprocess — это принципиально, потому что
в собранном .exe/.AppImage нет отдельного интерпретатора python, который можно
было бы вызвать как `python -m pymobiledevice3 ...`.

Мы не переизобретаем протоколы USB/lockdown сами — просто вызываем
документированные команды pymobiledevice3 (apps/afc/backup2/restore/developer/
syslog/diagnostics) и отдаём их вывод построчно в UI.

Точные флаги у pymobiledevice3 иногда немного меняются между версиями.
Если какая-то команда перестанет работать — смотрите
`pymobiledevice3 <группа> --help` и поправьте список аргументов ниже.
"""
from __future__ import annotations

import contextlib
import importlib
import io
import os
import queue
import threading
from dataclasses import dataclass

DONE = object()


def _load_cli_group():
    """Находим click-группу pymobiledevice3, не завязываясь на точный путь модуля."""
    candidates = [
        ("pymobiledevice3.__main__", "cli"),
        ("pymobiledevice3.cli.cli", "cli"),
        ("pymobiledevice3.cli.cli", "main"),
    ]
    last_err = None
    for modpath, attr in candidates:
        try:
            mod = importlib.import_module(modpath)
            return getattr(mod, attr)
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"Не найдена CLI-группа pymobiledevice3: {last_err}")


class _QueueWriter(io.TextIOBase):
    """Файлоподобный объект: всё, что в него пишут (print/click.echo), улетает в очередь."""

    def __init__(self, q: "queue.Queue[str]"):
        self.q = q

    def write(self, s):  # noqa: D401
        if s:
            self.q.put(s)
        return len(s)

    def flush(self):
        pass


def run_pmd3(args: list[str], udid: str | None = None):
    """
    Генератор: запускает `pymobiledevice3 <args>` в фоновом потоке и построчно
    (точнее — чанками) отдаёт то, что команда печатает. Безопасно вызывать и
    из исходников, и из собранного PyInstaller-бинарника.
    """
    q: "queue.Queue[str]" = queue.Queue()

    def worker():
        writer = _QueueWriter(q)
        old_udid = os.environ.get("PYMOBILEDEVICE3_UDID")
        try:
            if udid:
                os.environ["PYMOBILEDEVICE3_UDID"] = udid
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                try:
                    cli = _load_cli_group()
                    cli.main(args=list(args), prog_name="pymobiledevice3", standalone_mode=False)
                except SystemExit:
                    pass
                except Exception as e:  # noqa: BLE001
                    writer.write(f"\n[Xpl0it00ls] Ошибка: {e!r}\n")
        finally:
            if old_udid is None:
                os.environ.pop("PYMOBILEDEVICE3_UDID", None)
            else:
                os.environ["PYMOBILEDEVICE3_UDID"] = old_udid
            q.put(DONE)

    threading.Thread(target=worker, daemon=True).start()
    while True:
        item = q.get()
        if item is DONE:
            return
        yield item


@dataclass
class SyslogHandle:
    stop_event: threading.Event
    thread: threading.Thread


def start_syslog(udid: str | None, on_line, on_error, match: str | None = None) -> SyslogHandle:
    """Живой поток syslog через прямой Python API (им можно корректно управлять —
    в отличие от `syslog live` через CLI, которую нельзя чисто остановить)."""
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.syslog import SyslogService

    stop_event = threading.Event()

    def worker():
        try:
            ld = create_using_usbmux(serial=udid) if udid else create_using_usbmux()
            try:
                svc = SyslogService(lockdown=ld)
            except TypeError:
                svc = SyslogService(ld)
            for line in svc.watch():
                if stop_event.is_set():
                    break
                if match and match not in str(line):
                    continue
                on_line(str(line))
            with contextlib.suppress(Exception):
                svc.close()
        except Exception as e:  # noqa: BLE001
            on_error(str(e))

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return SyslogHandle(stop_event=stop_event, thread=t)


def list_serials() -> list[str]:
    from pymobiledevice3.usbmux import list_devices
    return [d.serial for d in list_devices()]


def device_rows(serial: str) -> list[tuple[str, str]]:
    from pymobiledevice3.lockdown import create_using_usbmux

    keys = [
        ("DeviceName", "Имя"), ("ProductType", "Модель (ID)"), ("ProductVersion", "iOS"),
        ("BuildVersion", "Сборка"), ("SerialNumber", "Серийный номер"),
        ("UniqueDeviceID", "UDID"), ("CPUArchitecture", "CPU"), ("ModelNumber", "Модель"),
        ("RegionInfo", "Регион"), ("ActivationState", "Активация"),
    ]
    ld = create_using_usbmux(serial=serial)
    vals = ld.all_values
    rows = [(label, str(vals.get(k, "—"))) for k, label in keys]
    with contextlib.suppress(Exception):
        b = ld.get_value(domain="com.apple.mobile.battery")
        charging = " (заряжается)" if b.get("BatteryIsCharging") else ""
        rows.append(("Заряд", f"{b.get('BatteryCurrentCapacity', '?')}%{charging}"))
    return rows


def reboot_device(serial: str) -> None:
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.diagnostics import DiagnosticsService
    DiagnosticsService(create_using_usbmux(serial=serial)).restart()
