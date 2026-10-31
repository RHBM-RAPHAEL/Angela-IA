"""Small Qt window to paste folder paths and give voice-friendly names."""
from __future__ import annotations

import os
import ntpath
import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout, QWidget,
)

from .folder_registry import FolderRegistry


class FolderRegistryWindow(QWidget):
    saved = Signal(str)
    error = Signal(str)
    operation_done = Signal(str, bool, str, object)
    browse_ready = Signal(int, str, list, str)

    def __init__(self, parent=None, *, registry: FolderRegistry | None = None):
        super().__init__(parent)
        self.registry = registry or FolderRegistry()
        self._pending_operation = False
        self._browse_request_id = 0
        self._browse_workers = []
        self._browse_current = ""
        self._browse_open = False
        self.browse_ready.connect(self._finish_browse)
        # Worker thread returns results through a queued Qt signal; it must
        # never manipulate widgets from outside the GUI thread.
        self.operation_done.connect(self._finish_operation)
        self.setObjectName("angelaFolderRegistry")
        self.setWindowTitle("Ângela AI · Minhas pastas")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setMinimumSize(480, 380)
        self.resize(560, 460)
        self.setStyleSheet("""
            QWidget#angelaFolderRegistry { background: #101b2a; color: #eaf4ff; }
            QLabel { color: #d8eafa; }
            QLineEdit, QListWidget { background: #17283b; color: #f2f9ff;
                border: 1px solid #385d7d; border-radius: 6px; padding: 7px; }
            QPushButton { color: #f1f8ff; background: #24547c;
                border: 1px solid #487aa0; border-radius: 7px; padding: 7px; }
            QPushButton:hover { background: #3577a5; }
        """)
        layout = QVBoxLayout(self)
        heading = QLabel("CADASTRAR PASTAS")
        heading.setStyleSheet("font-size: 18px; font-weight: 700; color: #83d7ff")
        layout.addWidget(heading)
        help_text = QLabel(
            "Cole um caminho completo, dê um apelido e diga depois "
            "\"Ângela, abra a pasta [apelido]\"."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        layout.addWidget(QLabel("Apelido para chamar por voz"))
        self.alias_edit = QLineEdit()
        self.alias_edit.setPlaceholderText("Ex.: Meus projetos")
        self.alias_edit.setMaxLength(45)
        layout.addWidget(self.alias_edit)

        layout.addWidget(QLabel("Caminho da pasta"))
        path_line = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(r"Ex.: D:\RHBM TechWorks\Meus Softwares")
        self.path_edit.setAccessibleName("Cole aqui o caminho da pasta")
        path_line.addWidget(self.path_edit, 1)
        choose = QPushButton("Procurar...")
        choose.clicked.connect(self._browse)
        path_line.addWidget(choose)
        layout.addLayout(path_line)

        # Our own inline folder browser. No Windows native Shell dialog and
        # no modal Qt event loop; even slow drives are listed off-thread.
        self.browse_panel = QFrame(self)
        self.browse_panel.setObjectName("angelaFolderBrowser")
        self.browse_panel.setStyleSheet(
            "QFrame#angelaFolderBrowser { border: 1px solid #385d7d;"
            "border-radius: 7px; background: #142337; }"
        )
        browse_layout = QVBoxLayout(self.browse_panel)
        browse_layout.addWidget(QLabel("Escolha uma pasta neste computador"))
        location_line = QHBoxLayout()
        self.browse_location = QLineEdit()
        self.browse_location.setPlaceholderText(r"Ex.: D:\Curso de Dart e Flutter")
        self.browse_location.returnPressed.connect(self._browse_go)
        location_line.addWidget(self.browse_location, 1)
        go_button = QPushButton("Ir")
        go_button.clicked.connect(self._browse_go)
        location_line.addWidget(go_button)
        up_button = QPushButton("Voltar")
        up_button.clicked.connect(self._browse_up)
        location_line.addWidget(up_button)
        browse_layout.addLayout(location_line)
        self.browse_list = QListWidget()
        self.browse_list.setMinimumHeight(130)
        self.browse_list.itemDoubleClicked.connect(self._browse_enter)
        browse_layout.addWidget(self.browse_list)
        browser_actions = QHBoxLayout()
        choose_button = QPushButton("Usar esta pasta")
        choose_button.clicked.connect(self._browse_choose)
        browser_actions.addWidget(choose_button)
        drives_button = QPushButton("Unidades")
        drives_button.clicked.connect(lambda: self._browse_to(""))
        browser_actions.addWidget(drives_button)
        cancel_button = QPushButton("Fechar busca")
        cancel_button.clicked.connect(self._browse_hide)
        browser_actions.addWidget(cancel_button)
        browse_layout.addLayout(browser_actions)
        self.browse_panel.hide()
        layout.addWidget(self.browse_panel)

        self.save_button = QPushButton("Salvar pasta")
        self.save_button.clicked.connect(self._save)
        layout.addWidget(self.save_button)
        layout.addWidget(QLabel("Pastas salvas"))
        self.listing = QListWidget()
        self.listing.itemSelectionChanged.connect(self._fill_selection)
        layout.addWidget(self.listing, 1)
        actions = QHBoxLayout()
        self.open_button = QPushButton("Abrir selecionada")
        self.open_button.clicked.connect(self._open)
        self.remove_button = QPushButton("Remover selecionada")
        self.remove_button.clicked.connect(self._remove)
        actions.addWidget(self.open_button)
        actions.addWidget(self.remove_button)
        layout.addLayout(actions)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.refresh()

        screen = QApplication.primaryScreen()
        if screen:
            bounds = screen.availableGeometry()
            self.move(
                bounds.left() + max(20, (bounds.width() - self.width()) // 2),
                bounds.top() + max(25, (bounds.height() - self.height()) // 2),
            )

    def refresh(self):
        self.listing.clear()
        try:
            for label, path in sorted(self.registry.all().items()):
                from PySide6.QtWidgets import QListWidgetItem
                item = QListWidgetItem(label + "  —  " + path)
                item.setData(Qt.ItemDataRole.UserRole, label)
                self.listing.addItem(item)
        except (OSError, ValueError) as exc:
            self._error("Não foi possível carregar as pastas.")

    def _browse(self):
        """Show an inline browser; never call Qt/Windows modal file pickers."""
        if self._browse_open:
            self._browse_hide()
            return
        self._browse_open = True
        self.browse_panel.show()
        self.resize(max(560, self.width()), max(650, self.height()))
        self._browse_to(self.path_edit.text().strip())

    def _browse_hide(self):
        self._browse_open = False
        self.browse_panel.hide()
        self._browse_request_id += 1  # Ignore late directory listings.
        self.resize(self.width(), 460)

    def _browse_to(self, path):
        """List just folders on a worker: slow disks never freeze the UI."""
        value = str(path).strip().strip('"').replace("/", "\\")
        self._browse_request_id += 1
        request_id = self._browse_request_id
        self.browse_location.setText(value)
        self.browse_list.clear()
        self.browse_list.addItem("Carregando pastas...")
        self.status.setText("Buscando pastas no computador...")

        def worker():
            entries = []
            error = ""
            try:
                if not value:
                    # Windows local/mapped drives, without Shell dialogs.
                    entries = [(drive, drive) for drive in os.listdrives()]
                elif not (len(value) >= 3 and value[1:3] == ":\\"
                          and value[0].isalpha()
                          and not value.startswith("\\\\")):
                    error = "Selecione um caminho local, como D:\\Meus Cursos."
                else:
                    with os.scandir(value) as listing:
                        for entry in listing:
                            try:
                                if entry.is_dir(follow_symlinks=False):
                                    entries.append((entry.name, entry.path))
                            except OSError:
                                continue
                            if len(entries) >= 600:
                                break
                    entries.sort(key=lambda item: item[0].casefold())
            except (OSError, ValueError, PermissionError) as exc:
                error = "Não consegui listar essa pasta. Confira o caminho."
            try:
                self.browse_ready.emit(request_id, value, entries, error)
            except RuntimeError:
                pass  # Window was closed during slow filesystem access.

        thread = threading.Thread(
            target=worker, daemon=True, name="angela-folder-browser"
        )
        self._browse_workers = [
            existing for existing in self._browse_workers if existing.is_alive()
        ]
        self._browse_workers.append(thread)
        thread.start()

    def _finish_browse(self, request_id, path, entries, error):
        if request_id != self._browse_request_id or not self._browse_open:
            return
        self.browse_list.clear()
        if error:
            self._browse_current = ""
            self.status.setText(error)
            return
        self._browse_current = path
        if not entries:
            self.browse_list.addItem("Nenhuma subpasta encontrada.")
        else:
            for name, location in entries:
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, location)
                self.browse_list.addItem(item)
        self.status.setText(
            "Abra uma pasta com dois cliques ou use 'Usar esta pasta'."
        )

    def _browse_go(self):
        self._browse_to(self.browse_location.text())

    def _browse_enter(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self._browse_to(path)

    def _browse_up(self):
        current = self._browse_current
        if not current:
            return
        if len(current.rstrip("\\/")) == 2 and current[1] == ":":
            self._browse_to("")
            return
        parent = ntpath.dirname(current.rstrip("\\/"))
        if len(parent) == 2 and parent[1] == ":":
            parent += "\\"
        self._browse_to(parent if parent != current else "")

    def _browse_choose(self):
        if not self._browse_open or not self._browse_current:
            self._error("Escolha primeiro uma unidade e uma pasta.")
            return
        self.path_edit.setText(self._browse_current)
        self.status.setText("Pasta selecionada. Clique em Salvar pasta.")
        self._browse_hide()

    def _run_async(self, operation: str, handler):
        """Return to Qt immediately, even if Windows stalls on folder I/O."""
        if self._pending_operation:
            return
        self._pending_operation = True
        self.save_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.status.setText("Verificando pasta..." if operation == "save"
                            else "Processando...")
        def worker():
            try:
                result = handler()
                self.operation_done.emit(operation, True, "", result)
            except (OSError, ValueError, RuntimeError, PermissionError) as exc:
                self.operation_done.emit(
                    operation, False, str(exc)[:200], None
                )
        threading.Thread(
            target=worker, daemon=True, name="angela-folder-ui"
        ).start()

    def _finish_operation(self, operation: str, ok: bool, message: str, result):
        self._pending_operation = False
        self.save_button.setEnabled(True)
        self.open_button.setEnabled(True)
        self.remove_button.setEnabled(True)
        if not ok:
            self._error(message or "Não foi possível acessar a pasta.")
            return
        if operation == "save":
            self.status.setText("Pasta salva. Agora diga: abra a pasta " + str(result))
            self.saved.emit(str(result))
            self.refresh()
        elif operation == "open":
            self.status.setText(str(result) if result
                                else "Pasta não encontrada.")
        elif operation == "remove":
            self.status.setText("Pasta removida." if result
                                else "Pasta não encontrada.")
            self.refresh()

    def _save(self):
        alias = self.alias_edit.text().strip()
        path = self.path_edit.text().strip()
        # Capture input on the GUI thread; only disk I/O goes to worker.
        self._run_async(
            "save", lambda: (self.registry.save(alias, path), alias)[1]
        )

    def _selection(self):
        item = self.listing.currentItem()
        if item is None:
            self._error("Escolha uma pasta da lista.")
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _fill_selection(self):
        item = self.listing.currentItem()
        if item:
            key = item.data(Qt.ItemDataRole.UserRole)
            folder = self.registry.resolve(key)
            if folder:
                self.alias_edit.setText(folder[0])
                self.path_edit.setText(folder[1])

    def _open(self):
        key = self._selection()
        if key is None:
            return
        self._run_async("open", lambda: self.registry.open_alias(key))

    def _remove(self):
        key = self._selection()
        if key is None:
            return
        self._run_async("remove", lambda: self.registry.remove(key))

    def _error(self, message: str):
        self.status.setText(message)
        self.error.emit(message)
