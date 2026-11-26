"""Xpl0it00ls TUI — терминальный интерфейс на textual.

Вкладки: Обзор, Приложения, Файлы (AFC), Скриншот, Syslog, Бэкап/Восстановление,
Прошивка (IPSW) и честный раздел про джейлбрейк (без встроенных эксплойтов).
"""
from __future__ import annotations

import os
import shutil
import webbrowser
from datetime import datetime
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (Button, DataTable, Footer, Header, Input, Label,
                             RichLog, Select, Static, Switch, TabbedContent, TabPane)

from . import pmd3

BANNER = r"""
██╗  ██╗██████╗ ██╗      ██████╗ ██╗████████╗ ██████╗  ██████╗ ██╗     ███████╗
╚██╗██╔╝██╔══██╗██║      ██╔══██╗██║╚══██╔══╝██╔═████╗██╔═████╗██║     ██╔════╝
 ╚███╔╝ ██████╔╝██║█████╗██████╔╝██║   ██║   ██║██╔██║██║██╔██║██║     ███████╗
 ██╔██╗ ██╔═══╝ ██║╚════╝██╔═══╝ ██║   ██║   ████╔╝██║████╔╝██║██║     ╚════██║
██╔╝ ██╗██║     ███████╗ ██║     ██║   ██║   ╚██████╔╝╚██████╔╝███████╗███████║
╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═╝     ╚═╝   ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝╚══════╝
""".strip("\n")

TAGLINE = "iPhone toolkit · без iTunes · AFC · Apps · Syslog · Backup · Firmware"

# Своя цветовая палитра — не завязана на тему textual по умолчанию,
# чтобы выглядело одинаково в любой версии библиотеки.
APP_CSS = """
$xbg: #05050a;
$xpanel: #0c0f16;
$xpanel2: #10141d;
$xaccent: #00ffc8;
$xaccent2: #ff2bd6;
$xdim: #5c6773;
$xok: #39ff88;
$xwarn: #ffb000;
$xerr: #ff3860;
$xtext: #d7e3e8;

Screen {
    background: $xbg;
    color: $xtext;
}

#banner {
    content-align: center middle;
    color: $xaccent;
    text-style: bold;
    height: auto;
    padding-top: 1;
}

#tagline {
    content-align: center middle;
    color: $xdim;
    height: 1;
    padding-bottom: 1;
}

Header {
    background: $xpanel;
    color: $xaccent;
    text-style: bold;
}

Footer {
    background: $xpanel;
    color: $xdim;
}

#topbar {
    height: 3;
    padding: 0 1;
    margin: 0 1;
    background: $xpanel2;
    border: round $xaccent2;
}
#topbar Label {
    padding: 1 1 0 0;
    color: $xaccent2;
    text-style: bold;
}
#device-select {
    width: 42;
}
#device-status {
    padding: 1 0 0 1;
    color: $xdim;
}

TabbedContent {
    margin: 0 1;
}
Tabs {
    background: $xpanel;
}
Tab {
    color: $xdim;
    text-style: bold;
}
Tab:hover {
    color: $xaccent;
}
Tab.-active {
    color: $xbg;
    background: $xaccent;
    text-style: bold;
}

.pane {
    padding: 1 2;
    background: $xpanel;
}
.hint {
    color: $xdim;
    margin-bottom: 1;
}
.warn {
    background: $xwarn;
    color: $xbg;
    text-style: bold;
    padding: 0 1;
    margin: 1 0;
}
.row {
    height: 3;
}
.row Input {
    margin-right: 1;
}
Input {
    border: round $xdim;
    background: $xpanel2;
    color: $xtext;
}
Input:focus {
    border: round $xaccent;
}
RichLog {
    border: round $xaccent;
    background: $xpanel2;
    color: $xtext;
    height: 1fr;
}
Button {
    margin-right: 1;
    border: round $xdim;
    background: $xpanel2;
    color: $xtext;
}
Button:hover {
    border: round $xaccent;
}
Button.-primary {
    background: $xaccent;
    color: $xbg;
    text-style: bold;
    border: round $xaccent;
}
Button.-error {
    background: $xerr;
    color: $xbg;
    text-style: bold;
    border: round $xerr;
}
DataTable {
    height: 1fr;
    border: round $xaccent;
    background: $xpanel2;
}
Switch {
    border: round $xdim;
}
"""


class DevicePicker(Horizontal):
    """Общий виджет выбора устройства — вынесен наверх, виден на всех вкладках."""

    def compose(self) -> ComposeResult:
        yield Label("📱 Устройство:")
        yield Select([], id="device-select", allow_blank=True, prompt="нет устройств")
        yield Button("⟳ Обновить", id="refresh-devices", variant="primary")
        yield Static("", id="device-status")

    def on_mount(self) -> None:
        self.border_title = "🔌 DEVICE"


class DashboardPane(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Static("Основная информация об устройстве.", classes="hint")
        table = DataTable(id="info-table")
        table.add_columns("Параметр", "Значение")
        table.border_title = "📊 DEVICE INFO"
        table.zebra_stripes = True
        yield table
        with Horizontal(classes="row"):
            yield Button("Обновить инфо", id="info-refresh", variant="primary")
            yield Button("🔁 Перезагрузить iPhone", id="reboot", variant="error")
        yield Static("", id="dash-status")

    @on(Button.Pressed, "#info-refresh")
    def _refresh(self) -> None:
        self.load_info()

    @on(Button.Pressed, "#reboot")
    def _reboot(self) -> None:
        self.do_reboot()

    @work(thread=True)
    def load_info(self) -> None:
        udid = self.app.current_udid  # type: ignore[attr-defined]
        table = self.query_one("#info-table", DataTable)
        status = self.query_one("#dash-status", Static)
        if not udid:
            self.app.call_from_thread(status.update, "Устройство не выбрано.")
            return
        try:
            rows = pmd3.device_rows(udid)
        except Exception as e:  # noqa: BLE001
            self.app.call_from_thread(status.update, f"Ошибка: {e}")
            return

        def apply():
            table.clear()
            for r in rows:
                table.add_row(*r)
            status.update("Готово.")

        self.app.call_from_thread(apply)

    @work(thread=True)
    def do_reboot(self) -> None:
        udid = self.app.current_udid  # type: ignore[attr-defined]
        status = self.query_one("#dash-status", Static)
        if not udid:
            return
        try:
            pmd3.reboot_device(udid)
            self.app.call_from_thread(status.update, "Команда перезагрузки отправлена.")
        except Exception as e:  # noqa: BLE001
            self.app.call_from_thread(status.update, f"Ошибка: {e}")


class RunnerPane(Vertical):
    """Базовый класс для вкладок, которые просто запускают pmd3-команду и льют лог."""

    def make_log(self, title: str = "OUTPUT") -> RichLog:
        self._log = RichLog(wrap=True, markup=True, highlight=False)
        self._log.border_title = f"🖥 {title}"
        return self._log

    @work(thread=True)
    def run_cmd(self, args: list[str], label: str | None = None) -> None:
        udid = self.app.current_udid  # type: ignore[attr-defined]
        if label:
            self.app.call_from_thread(
                self._log.write, f"\n[bold #00ffc8]❯[/] pymobiledevice3 {' '.join(args)}\n")
        for chunk in pmd3.run_pmd3(args, udid=udid):
            self.app.call_from_thread(self._log.write, chunk)
        self.app.call_from_thread(self._log.write, "\n[bold #39ff88][готово][/]\n")


class AppsPane(RunnerPane):
    def compose(self) -> ComposeResult:
        yield Static("Список / установка / удаление приложений (через pymobiledevice3 apps).",
                     classes="hint")
        with Horizontal(classes="row"):
            yield Button("Список приложений", id="apps-list", variant="primary")
        with Horizontal(classes="row"):
            yield Input(placeholder="Путь к .ipa", id="ipa-path")
            yield Button("Установить", id="apps-install")
        with Horizontal(classes="row"):
            yield Input(placeholder="Bundle ID (com.example.app)", id="bundle-id")
            yield Button("Удалить", id="apps-uninstall", variant="error")
        yield self.make_log("APPS OUTPUT")

    @on(Button.Pressed, "#apps-list")
    def _list(self) -> None:
        self.run_cmd(["apps", "list", "--user", "--system"], label=True)

    @on(Button.Pressed, "#apps-install")
    def _install(self) -> None:
        path = self.query_one("#ipa-path", Input).value.strip()
        if path:
            self.run_cmd(["apps", "install", path], label=True)

    @on(Button.Pressed, "#apps-uninstall")
    def _uninstall(self) -> None:
        bid = self.query_one("#bundle-id", Input).value.strip()
        if bid:
            self.run_cmd(["apps", "uninstall", bid], label=True)


class FilesPane(RunnerPane):
    """Файловый менеджер через AFC (папка Media устройства)."""

    def compose(self) -> ComposeResult:
        yield Static("Файловый менеджер (AFC) — работает с /var/mobile/Media на устройстве.",
                     classes="hint")
        with Horizontal(classes="row"):
            yield Input(value="/", placeholder="Путь на устройстве", id="remote-path")
            yield Button("Ls", id="afc-ls")
            yield Button("Mkdir", id="afc-mkdir")
            yield Button("Rm", id="afc-rm", variant="error")
        with Horizontal(classes="row"):
            yield Input(placeholder="Локальный путь (для Pull/Push)", id="local-path")
            yield Button("⬇ Pull", id="afc-pull")
            yield Button("⬆ Push", id="afc-push")
        yield self.make_log("AFC OUTPUT")

    def _remote(self) -> str:
        return self.query_one("#remote-path", Input).value.strip() or "/"

    def _local(self) -> str:
        return self.query_one("#local-path", Input).value.strip()

    @on(Button.Pressed, "#afc-ls")
    def _ls(self) -> None:
        self.run_cmd(["afc", "ls", self._remote()], label=True)

    @on(Button.Pressed, "#afc-mkdir")
    def _mkdir(self) -> None:
        self.run_cmd(["afc", "mkdir", self._remote()], label=True)

    @on(Button.Pressed, "#afc-rm")
    def _rm(self) -> None:
        self.run_cmd(["afc", "rm", self._remote()], label=True)

    @on(Button.Pressed, "#afc-pull")
    def _pull(self) -> None:
        local = self._local() or "."
        self.run_cmd(["afc", "pull", self._remote(), local], label=True)

    @on(Button.Pressed, "#afc-push")
    def _push(self) -> None:
        local = self._local()
        if local:
            self.run_cmd(["afc", "push", local, self._remote()], label=True)


class ScreenshotPane(RunnerPane):
    def compose(self) -> ComposeResult:
        yield Static("Скриншот экрана устройства (через DeveloperDiskImage / DVT).",
                     classes="hint")
        with Horizontal(classes="row"):
            yield Input(value="./screenshots", placeholder="Папка сохранения", id="shot-dir")
        with Horizontal(classes="row"):
            yield Label("Старый API (iOS ниже 17 / старый pymobiledevice3):")
            yield Switch(id="legacy-switch")
        yield Button("📸 Сделать снимок", id="shot-take", variant="primary")
        yield self.make_log("SCREENSHOT OUTPUT")

    @on(Button.Pressed, "#shot-take")
    def _take(self) -> None:
        out_dir = Path(self.query_one("#shot-dir", Input).value.strip() or "./screenshots")
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = out_dir / f"shot_{datetime.now():%Y%m%d_%H%M%S}.png"
        legacy = self.query_one("#legacy-switch", Switch).value
        args = ["developer", "screenshot", str(fname)] if legacy else \
               ["developer", "dvt", "screenshot", str(fname)]
        self.run_cmd(args, label=True)


class SyslogPane(Vertical):
    def compose(self) -> ComposeResult:
        yield Static("Живой системный лог устройства.", classes="hint")
        with Horizontal(classes="row"):
            yield Input(placeholder="Фильтр (необязательно, например SpringBoard)", id="syslog-filter")
            yield Button("▶ Старт", id="syslog-start", variant="primary")
            yield Button("■ Стоп", id="syslog-stop", variant="error")
        self._log = RichLog(wrap=True, markup=True, highlight=False)
        self._log.border_title = "🪵 LIVE SYSLOG"
        yield self._log
        self._handle = None

    @on(Button.Pressed, "#syslog-start")
    def _start(self) -> None:
        udid = self.app.current_udid  # type: ignore[attr-defined]
        if self._handle is not None:
            self._handle.stop_event.set()
        match = self.query_one("#syslog-filter", Input).value.strip() or None
        self._log.write(f"\n[bold #39ff88]▶ старт[/], устройство: {udid or 'авто'}\n")

        def on_line(line: str) -> None:
            self.app.call_from_thread(self._log.write, line)

        def on_error(err: str) -> None:
            self.app.call_from_thread(self._log.write, f"\n[bold #ff3860]ошибка:[/] {err}\n")

        self._handle = pmd3.start_syslog(udid, on_line, on_error, match=match)

    @on(Button.Pressed, "#syslog-stop")
    def _stop(self) -> None:
        if self._handle is not None:
            self._handle.stop_event.set()
            self._log.write("\n[bold #ffb000]■ остановлено[/]\n")


class BackupPane(RunnerPane):
    def compose(self) -> ComposeResult:
        yield Static("Полный бэкап и восстановление устройства (backup2). "
                     "Долгая операция — не отключайте телефон.", classes="hint")
        with Horizontal(classes="row"):
            yield Input(value="./backup", placeholder="Папка для бэкапа", id="backup-dir")
            yield Button("💾 Сделать бэкап", id="backup-go", variant="primary")
        with Horizontal(classes="row"):
            yield Input(placeholder="Папка с бэкапом для восстановления", id="restore-dir")
            yield Button("♻ Восстановить", id="backup-restore", variant="error")
        yield self.make_log("BACKUP OUTPUT")

    @on(Button.Pressed, "#backup-go")
    def _backup(self) -> None:
        d = self.query_one("#backup-dir", Input).value.strip() or "./backup"
        Path(d).mkdir(parents=True, exist_ok=True)
        self.run_cmd(["backup2", "backup", "--full", d], label=True)

    @on(Button.Pressed, "#backup-restore")
    def _restore(self) -> None:
        d = self.query_one("#restore-dir", Input).value.strip()
        if d:
            self.run_cmd(["backup2", "restore", d], label=True)


class FirmwarePane(RunnerPane):
    def compose(self) -> ComposeResult:
        yield Static(
            "⚠ Обновление / восстановление прошивки (IPSW). Это рискованная операция: "
            "при сбое, отключении кабеля или несовместимой прошивке устройство можно "
            "привести в нерабочее состояние. Обязательно сделайте бэкап заранее. "
            "Требуется установленный libusb.", classes="warn")
        with Horizontal(classes="row"):
            yield Input(placeholder="Путь к .ipsw или URL", id="ipsw-path")
            yield Button("⚡ Восстановить/обновить", id="fw-go", variant="error")
        yield self.make_log("RESTORE/FLASH OUTPUT")

    @on(Button.Pressed, "#fw-go")
    def _go(self) -> None:
        path = self.query_one("#ipsw-path", Input).value.strip()
        if path:
            self.run_cmd(["restore", "update", "-i", path], label=True)


class JailbreakPane(Vertical):
    """Xpl0it00ls НЕ содержит собственного джейлбрейка/эксплойтов.
    Это только детектор уже установленных у пользователя инструментов
    (checkra1n / palera1n) и ссылка на их официальные сайты."""

    TOOLS = {
        "checkra1n": "https://checkra.in",
        "palera1n": "https://palera1n.com",
    }

    def compose(self) -> ComposeResult:
        yield Static(
            "Xpl0it00ls не реализует джейлбрейк сам — это отдельная, быстро меняющаяся "
            "область (эксплойты под конкретные версии iOS/чипов), и встраивать такой код "
            "сюда небезопасно и неправильно. Ниже — просто проверка, установлены ли у вас "
            "уже known-good инструменты (checkra1n / palera1n), и быстрый доступ к их "
            "официальным сайтам.", classes="hint")
        self._status = Static("")
        yield self._status
        with Horizontal(classes="row"):
            for name in self.TOOLS:
                yield Button(f"Открыть сайт {name}", id=f"site-{name}")

    def on_mount(self) -> None:
        lines = []
        for name in self.TOOLS:
            found = shutil.which(name)
            lines.append(f"{name}: {'найден — ' + found if found else 'не найден в PATH'}")
        self._status.update("\n".join(lines))

    @on(Button.Pressed)
    def _open_site(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("site-"):
            name = bid.removeprefix("site-")
            url = self.TOOLS.get(name)
            if url:
                webbrowser.open(url)


class Xpl0it00lsApp(App):
    TITLE = "Xpl0it00ls"
    SUB_TITLE = "iPhone manager — без iTunes"
    CSS = APP_CSS
    BINDINGS = [("q", "quit", "Выход"), ("r", "refresh_devices", "Обновить устройства")]

    current_udid: reactive[str | None] = reactive(None)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(BANNER, id="banner")
        yield Static(TAGLINE, id="tagline")
        yield DevicePicker(id="topbar")
        with TabbedContent(initial="dash"):
            with TabPane("📋 Обзор", id="dash"):
                yield DashboardPane(classes="pane")
            with TabPane("📦 Приложения", id="apps"):
                yield AppsPane(classes="pane")
            with TabPane("📁 Файлы", id="files"):
                yield FilesPane(classes="pane")
            with TabPane("📸 Экран", id="shot"):
                yield ScreenshotPane(classes="pane")
            with TabPane("🪵 Syslog", id="syslog"):
                yield SyslogPane(classes="pane")
            with TabPane("💾 Бэкап", id="backup"):
                yield BackupPane(classes="pane")
            with TabPane("⚡ Прошивка", id="firmware"):
                yield FirmwarePane(classes="pane")
            with TabPane("🔓 Джейлбрейк", id="jb"):
                yield JailbreakPane(classes="pane")
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh_devices()

    def action_refresh_devices(self) -> None:
        self._refresh_devices()

    @work(thread=True)
    def _refresh_devices(self) -> None:
        status = self.query_one("#device-status", Static)
        try:
            serials = pmd3.list_serials()
        except Exception as e:  # noqa: BLE001
            self.call_from_thread(status.update, f"ошибка usbmux: {e}")
            return

        def apply():
            select = self.query_one("#device-select", Select)
            select.set_options([(s, s) for s in serials])
            if serials:
                select.value = serials[0]
                self.current_udid = serials[0]
                status.update(f"найдено: {len(serials)}")
            else:
                self.current_udid = None
                status.update("iPhone не найден (кабель? доверие на экране?)")

        self.call_from_thread(apply)

    @on(Button.Pressed, "#refresh-devices")
    def _refresh_btn(self) -> None:
        self.action_refresh_devices()

    @on(Select.Changed, "#device-select")
    def _device_changed(self, event: Select.Changed) -> None:
        self.current_udid = event.value if event.value != Select.BLANK else None

    def watch_current_udid(self, udid: str | None) -> None:
        if udid:
            os.environ["PYMOBILEDEVICE3_UDID"] = udid
        else:
            os.environ.pop("PYMOBILEDEVICE3_UDID", None)


def main() -> None:
    Xpl0it00lsApp().run()


if __name__ == "__main__":
    main()
