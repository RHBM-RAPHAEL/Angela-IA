"""Small Qt window to paste folder paths and give voice-friendly names."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from .folder_registry import FolderRegistry


class FolderRegistryWindow(QWidget):
    saved = Signal(str)
    error = Signal(str)

    def __init__(self, parent=None, *, registry: FolderRegistry | None = None):
        super().__init__(parent)
        self.registry = registry or FolderRegistry()
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
        folder = QFileDialog.getExistingDirectory(
            self, "Escolha uma pasta", self.path_edit.text().strip()
        )
        if folder:
            self.path_edit.setText(folder.replace("/", "\\"))

    def _save(self):
        try:
            target = self.registry.save(
                self.alias_edit.text(), self.path_edit.text()
            )
            self.status.setText(
                "Pasta salva. Agora diga: abra a pasta " + self.alias_edit.text()
            )
            self.saved.emit(self.alias_edit.text().strip())
            self.refresh()
        except (ValueError, OSError) as exc:
            self._error(str(exc))

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
        answer = self.registry.open_alias(key)
        self.status.setText(answer or "Pasta não encontrada.")

    def _remove(self):
        key = self._selection()
        if key is None:
            return
        try:
            if self.registry.remove(key):
                self.status.setText("Pasta removida: " + key)
                self.refresh()
        except (ValueError, OSError):
            self._error("Não consegui remover essa pasta.")

    def _error(self, message: str):
        self.status.setText(message)
        self.error.emit(message)
