"""Interface gráfica CustomTkinter para o ESP32 Flasher.

Funcionalidades:
- Gravação de firmware com barra de progresso real (parseia output esptool)
- Importação automática de diretório .pio/build/<env>/
- Detecção automática de chip via esptool chip_id
- Monitor serial com timestamps, envio de comandos e filtro regex
- Drag-and-drop de .bin nos campos de arquivo (requer tkinterdnd2)
"""

import json
import os
import re
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from esp32_flasher.flasher import ESP32Flasher
from esp32_flasher.serial_monitor import SerialMonitor

# ── Suporte opcional a drag-and-drop ──────────────────────────────────────────
try:
    import tkinterdnd2
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

# Endereços padrão de flash por chip (PlatformIO Arduino)
CHIP_ADDRESSES = {
    "ESP32":    {"bootloader": "0x1000", "partitions": "0x8000", "boot_app0": "0xe000", "firmware": "0x10000"},
    "ESP32-S2": {"bootloader": "0x1000", "partitions": "0x8000", "boot_app0": "0xe000", "firmware": "0x10000"},
    "ESP32-S3": {"bootloader": "0x0",    "partitions": "0x8000", "boot_app0": "0xe000", "firmware": "0x10000"},
    "ESP32-C3": {"bootloader": "0x0",    "partitions": "0x8000", "boot_app0": "0xe000", "firmware": "0x10000"},
}

CHIPS = list(CHIP_ADDRESSES.keys())

# Diretório e arquivo de configuração em ~/.esp32_flasher/config.json
_CONFIG_DIR = Path.home() / ".esp32_flasher"
CONFIG_FILE = _CONFIG_DIR / "config.json"
# Arquivo legado na CWD — migrado automaticamente na primeira execução
_CONFIG_FILE_LEGACY = Path("config.json")

# Regex para parsear progresso do esptool: "Writing at 0x00010000... (45 %)"
_RE_PROGRESS = re.compile(r"\((\d+)\s*%\)")

# Regex para parsear nome do chip no output do esptool
_RE_CHIP = re.compile(r"Chip is (ESP32[-\w]*)", re.IGNORECASE)

# Nomes de arquivos PlatformIO esperados em .pio/build/<env>/
_PIO_FILES = {
    "bootloader": "bootloader.bin",
    "partitions": "partitions.bin",
    "boot_app0":  "boot_app0.bin",
    "firmware":   "firmware.bin",
}


class ESP32FlasherApp(ctk.CTk if not _DND_AVAILABLE else tkinterdnd2.TkinterDnD.Tk):
    """Janela principal da aplicação ESP32 Flasher GUI."""

    def __init__(self):
        """Inicializa a interface gráfica."""
        if _DND_AVAILABLE:
            # TkinterDnD.Tk.__init__ não aceita argumentos adicionais
            tkinterdnd2.TkinterDnD.Tk.__init__(self)
            # Aplica configurações visuais do CustomTkinter manualmente
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
        else:
            super().__init__()
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")

        self.title("ESP32 Flasher")
        self.geometry("750x750")
        self.minsize(650, 650)

        self.flasher = ESP32Flasher(output_callback=self._on_flash_output)
        self.serial_monitor = SerialMonitor(callback=self._on_serial_data)
        self._flashing = False

        # Variáveis dos campos de arquivo
        self._file_entries: dict[str, ctk.CTkEntry] = {}
        self._addr_entries: dict[str, ctk.CTkEntry] = {}
        # Botões "Selecionar..." — referenciados em _set_buttons_state
        self._file_browse_btns: list[ctk.CTkButton] = []

        self._build_ui()
        self._setup_dnd()
        self._migrate_config()
        self._load_config()
        self._refresh_ports()

        if not _DND_AVAILABLE:
            self.log_append("[Info] tkinterdnd2 não instalado — drag-and-drop desativado")

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Constrói todos os widgets da interface."""
        self.grid_columnconfigure(0, weight=1)

        row = 0

        # --- Seção Conexão ---
        conn_frame = ctk.CTkFrame(self)
        conn_frame.grid(row=row, column=0, padx=10, pady=(10, 5), sticky="ew")
        conn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(conn_frame, text="Porta:").grid(row=0, column=0, padx=5, pady=5)
        self.port_combo = ctk.CTkComboBox(conn_frame, values=[], width=150)
        self.port_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.btn_refresh = ctk.CTkButton(conn_frame, text="⟳", width=35,
                                         command=self._refresh_ports)
        self.btn_refresh.grid(row=0, column=2, padx=5, pady=5)

        ctk.CTkLabel(conn_frame, text="Chip:").grid(row=0, column=3, padx=5, pady=5)
        self.chip_combo = ctk.CTkComboBox(conn_frame, values=CHIPS, width=120,
                                          command=self._on_chip_changed)
        self.chip_combo.set(CHIPS[0])
        self.chip_combo.grid(row=0, column=4, padx=5, pady=5)

        # Botão "Detectar chip" (Item 3)
        self.btn_detect_chip = ctk.CTkButton(conn_frame, text="Detectar chip", width=100,
                                              command=self._start_detect_chip)
        self.btn_detect_chip.grid(row=0, column=5, padx=5, pady=5)

        ctk.CTkLabel(conn_frame, text="Baud:").grid(row=0, column=6, padx=5, pady=5)
        self.baud_entry = ctk.CTkEntry(conn_frame, width=80)
        self.baud_entry.insert(0, "921600")
        self.baud_entry.grid(row=0, column=7, padx=5, pady=5)

        row += 1

        # --- Seção Arquivos ---
        files_frame = ctk.CTkFrame(self)
        files_frame.grid(row=row, column=0, padx=10, pady=5, sticky="ew")
        files_frame.grid_columnconfigure(2, weight=1)

        # Botão "Importar PlatformIO..." (Item 2) — no topo da seção arquivos
        self.btn_import_pio = ctk.CTkButton(
            files_frame, text="Importar PlatformIO...", width=160,
            command=self._import_pio_dir,
        )
        self.btn_import_pio.grid(row=0, column=0, columnspan=4, padx=5, pady=(5, 8), sticky="w")

        file_labels = [
            ("bootloader", "Bootloader:"),
            ("partitions", "Partitions:"),
            ("boot_app0", "boot_app0 (opc.):"),
            ("firmware", "Firmware:"),
        ]

        default_addrs = CHIP_ADDRESSES[CHIPS[0]]
        for i, (key, label) in enumerate(file_labels):
            ui_row = i + 1  # linha 0 é o botão PlatformIO
            ctk.CTkLabel(files_frame, text=label).grid(row=ui_row, column=0, padx=5, pady=3, sticky="w")

            addr_entry = ctk.CTkEntry(files_frame, width=70)
            addr_entry.insert(0, default_addrs[key])
            addr_entry.grid(row=ui_row, column=1, padx=5, pady=3)
            self._addr_entries[key] = addr_entry

            file_entry = ctk.CTkEntry(files_frame)
            file_entry.grid(row=ui_row, column=2, padx=5, pady=3, sticky="ew")
            self._file_entries[key] = file_entry

            btn = ctk.CTkButton(files_frame, text="Selecionar...", width=100,
                                command=lambda k=key: self._select_file(k))
            btn.grid(row=ui_row, column=3, padx=5, pady=3)
            self._file_browse_btns.append(btn)

        row += 1

        # --- Seção Opções ---
        opts_frame = ctk.CTkFrame(self)
        opts_frame.grid(row=row, column=0, padx=10, pady=5, sticky="ew")

        self.erase_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(opts_frame, text="Limpar flash antes de gravar",
                        variable=self.erase_var).grid(row=0, column=0, padx=10, pady=5)

        self.monitor_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opts_frame, text="Abrir monitor serial após gravar",
                        variable=self.monitor_var).grid(row=0, column=1, padx=10, pady=5)

        ctk.CTkLabel(opts_frame, text="Baud monitor:").grid(row=0, column=2, padx=5, pady=5)
        self.monitor_baud_entry = ctk.CTkEntry(opts_frame, width=80)
        self.monitor_baud_entry.insert(0, "115200")
        self.monitor_baud_entry.grid(row=0, column=3, padx=5, pady=5)

        row += 1

        # --- Botões ---
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=row, column=0, padx=10, pady=5, sticky="ew")

        self.btn_flash = ctk.CTkButton(btn_frame, text="Gravar Firmware",
                                       command=self._start_flash, fg_color="green")
        self.btn_flash.grid(row=0, column=0, padx=5, pady=5)

        self.btn_erase = ctk.CTkButton(btn_frame, text="Limpar Flash",
                                       command=self._start_erase)
        self.btn_erase.grid(row=0, column=1, padx=5, pady=5)

        self.btn_monitor = ctk.CTkButton(btn_frame, text="Monitor Serial",
                                         command=self._toggle_monitor)
        self.btn_monitor.grid(row=0, column=2, padx=5, pady=5)

        row += 1

        # --- Área de Log ---
        self.log_text = ctk.CTkTextbox(self, height=220, state="disabled")
        self.log_text.grid(row=row, column=0, padx=10, pady=5, sticky="nsew")
        self.grid_rowconfigure(row, weight=1)

        row += 1

        # --- Barra de Progresso (Item 1) ---
        self.progress_bar = ctk.CTkProgressBar(self, mode="determinate")
        self.progress_bar.set(0)
        self.progress_bar.grid(row=row, column=0, padx=10, pady=(0, 2), sticky="ew")

        row += 1

        # --- Monitor serial inline — controles de envio e filtro (Item 6) ---
        monitor_ctrl_frame = ctk.CTkFrame(self)
        monitor_ctrl_frame.grid(row=row, column=0, padx=10, pady=(0, 5), sticky="ew")
        monitor_ctrl_frame.grid_columnconfigure(1, weight=1)
        monitor_ctrl_frame.grid_columnconfigure(3, weight=1)

        # Coluna 0-1: envio de comando
        ctk.CTkLabel(monitor_ctrl_frame, text="Enviar:").grid(
            row=0, column=0, padx=(5, 2), pady=4, sticky="w")
        self.monitor_send_entry = ctk.CTkEntry(monitor_ctrl_frame, placeholder_text="comando...")
        self.monitor_send_entry.grid(row=0, column=1, padx=2, pady=4, sticky="ew")
        self.monitor_send_entry.bind("<Return>", lambda _e: self._send_monitor_command())

        self.btn_send_cmd = ctk.CTkButton(monitor_ctrl_frame, text="Enviar", width=70,
                                          command=self._send_monitor_command)
        self.btn_send_cmd.grid(row=0, column=2, padx=(2, 8), pady=4)

        # Toggle CRLF
        self.crlf_var = ctk.BooleanVar(value=False)
        self.chk_crlf = ctk.CTkCheckBox(monitor_ctrl_frame, text="CRLF",
                                         variable=self.crlf_var,
                                         command=self._on_crlf_changed,
                                         width=60)
        self.chk_crlf.grid(row=0, column=3, padx=(0, 8), pady=4, sticky="w")

        # Toggle Timestamps
        self.timestamps_var = ctk.BooleanVar(value=False)
        self.chk_timestamps = ctk.CTkCheckBox(monitor_ctrl_frame, text="Timestamps",
                                               variable=self.timestamps_var,
                                               command=self._on_timestamps_changed,
                                               width=110)
        self.chk_timestamps.grid(row=0, column=4, padx=(0, 8), pady=4, sticky="w")

        # Coluna filtro regex
        ctk.CTkLabel(monitor_ctrl_frame, text="Filtro:").grid(
            row=0, column=5, padx=(0, 2), pady=4, sticky="w")
        self.filter_entry = ctk.CTkEntry(monitor_ctrl_frame, placeholder_text="regex...")
        self.filter_entry.grid(row=0, column=6, padx=(2, 5), pady=4, sticky="ew")
        monitor_ctrl_frame.grid_columnconfigure(6, weight=1)
        # Rastreia regex compilado atual — None significa sem filtro
        self._filter_regex: re.Pattern | None = None
        self.filter_entry.bind("<KeyRelease>", lambda _e: self._on_filter_changed())

        row += 1

        # --- Barra de Status ---
        self.status_label = ctk.CTkLabel(self, text="Pronto", anchor="w")
        self.status_label.grid(row=row, column=0, padx=10, pady=(0, 5), sticky="ew")

    # ── Drag-and-drop (Item 7) ────────────────────────────────────────

    def _setup_dnd(self):
        """Registra handlers de drag-and-drop nos entries de arquivo.

        Silencioso quando tkinterdnd2 não está disponível.
        """
        if not _DND_AVAILABLE:
            return

        for key, entry in self._file_entries.items():
            # Registra o widget para aceitar arquivos arrastados
            entry.drop_target_register(tkinterdnd2.DND_FILES)
            entry.dnd_bind("<<Drop>>", lambda event, k=key: self._on_file_drop(event, k))

    def _on_file_drop(self, event, key: str):
        """Preenche o entry de arquivo com o caminho recebido via drag-and-drop.

        Trata o formato do tkinterdnd2 que pode envolver caminhos em chaves
        ``{/path/with spaces/file.bin}`` ou sem, com múltiplos arquivos
        separados por espaço.

        Args:
            event: Evento DnD com ``event.data`` contendo o(s) caminho(s).
            key:   Chave do campo destino (bootloader/partitions/boot_app0/firmware).
        """
        raw: str = event.data.strip()

        # O tkinterdnd2 envolve caminhos com espaços em chaves
        if raw.startswith("{") and raw.endswith("}"):
            path = raw[1:-1]
        else:
            # Pega somente o primeiro arquivo se vários foram arrastados
            path = raw.split()[0]

        if not path.lower().endswith(".bin"):
            self.log_append(f"[DnD] Ignorado: '{Path(path).name}' não é .bin")
            return

        entry = self._file_entries[key]
        entry.delete(0, "end")
        entry.insert(0, path)
        self.log_append(f"[DnD] {key} ← {Path(path).name}")

    # ── Item 2 — Importar PlatformIO ──────────────────────────────────

    def _import_pio_dir(self):
        """Abre seletor de diretório e preenche campos com arquivos PlatformIO.

        Procura em ``<dir>/`` por bootloader.bin, partitions.bin, boot_app0.bin
        e firmware.bin.  Arquivos encontrados são inseridos nos entries
        correspondentes com os endereços corretos para o chip selecionado.
        Arquivos ausentes geram warning no log mas não impedem o preenchimento
        parcial.
        """
        directory = filedialog.askdirectory(
            title="Selecionar diretório .pio/build/<env>/",
        )
        if not directory:
            return

        chip = self.chip_combo.get()
        addrs = CHIP_ADDRESSES.get(chip, CHIP_ADDRESSES["ESP32"])
        found_any = False

        for key, filename in _PIO_FILES.items():
            candidate = os.path.join(directory, filename)
            if os.path.isfile(candidate):
                entry = self._file_entries[key]
                entry.delete(0, "end")
                entry.insert(0, candidate)
                # Atualiza endereço conforme chip selecionado
                self._addr_entries[key].delete(0, "end")
                self._addr_entries[key].insert(0, addrs[key])
                self.log_append(f"[PIO] {key}: {candidate}")
                found_any = True
            else:
                msg = f"[PIO] Aviso: {filename} não encontrado em {directory}"
                if key != "boot_app0":
                    # boot_app0 é opcional — só loga sem prefixo de erro
                    self.log_append(f"[PIO] Aviso: {filename} não encontrado (campo {key} mantido)")
                else:
                    self.log_append(msg)

        if not found_any:
            self.log_append(f"[PIO] Nenhum .bin encontrado em: {directory}")
        else:
            self.log_append(f"[PIO] Importação concluída de: {directory}")

    # ── Item 3 — Detecção de chip ─────────────────────────────────────

    def _start_detect_chip(self):
        """Inicia detecção de chip em thread separada para não bloquear a UI."""
        port = self.port_combo.get()
        if not port:
            self._set_status("Erro: nenhuma porta selecionada")
            return

        if self._flashing:
            self.log_append("[Info] Detecção de chip indisponível durante gravação")
            return

        # Fecha monitor serial se estiver ativo (libera porta)
        if self.serial_monitor.is_running:
            self.serial_monitor.stop()
            self.log_append("[Monitor serial fechado para detecção de chip]")

        self.btn_detect_chip.configure(state="disabled")
        self._set_status("Detectando chip...")
        self.log_append(f"--- Detectando chip em {port} ---")

        thread = threading.Thread(
            target=self._detect_chip_worker,
            args=(port,),
            daemon=True,
        )
        thread.start()

    def _detect_chip_worker(self, port: str):
        """Worker de detecção de chip — roda em thread separada."""
        try:
            chip_name, ret = self.flasher.detect_chip(port)
        except Exception as exc:  # noqa: BLE001
            chip_name = None
            ret = 1
            self.after(0, lambda e=exc: self.log_append(f"[Erro] Detecção falhou: {e}"))

        self.after(0, lambda: self._on_detect_chip_complete(chip_name, ret))

    def _on_detect_chip_complete(self, chip_name: str | None, returncode: int):
        """Callback chamado na main thread após detecção de chip."""
        self.btn_detect_chip.configure(state="normal")

        if returncode != 0 or chip_name is None:
            self._set_status("Detecção de chip falhou")
            self.log_append("[Detecção] Não foi possível identificar o chip")
            return

        # Normaliza nome detectado para correspondência na lista de chips
        detected_normalized = chip_name.upper()
        # Tenta encontrar correspondência exata ou parcial na lista
        matched_chip = None
        for c in CHIPS:
            if c.upper() == detected_normalized:
                matched_chip = c
                break
        # Correspondência parcial (ex: "ESP32S3" → "ESP32-S3")
        if matched_chip is None:
            normalized_no_dash = detected_normalized.replace("-", "")
            for c in CHIPS:
                if c.upper().replace("-", "") == normalized_no_dash:
                    matched_chip = c
                    break

        current_chip = self.chip_combo.get()

        if matched_chip is None:
            self.log_append(f"[Detecção] Chip detectado: {chip_name} (não mapeado na lista)")
            self._set_status(f"Chip detectado: {chip_name}")
            return

        if matched_chip == current_chip:
            self.log_append(f"[Detecção] Chip confirmado: {matched_chip}")
            self._set_status(f"Chip confirmado: {matched_chip}")
        else:
            resposta = messagebox.askyesno(
                "Chip diferente detectado",
                f"Chip detectado: {matched_chip}\n"
                f"Chip selecionado: {current_chip}\n\n"
                "Deseja atualizar o seletor para o chip detectado?",
            )
            if resposta:
                self.chip_combo.set(matched_chip)
                self._on_chip_changed(matched_chip)
                self.log_append(f"[Detecção] Chip atualizado para: {matched_chip}")
                self._set_status(f"Chip atualizado: {matched_chip}")
            else:
                self.log_append(
                    f"[Detecção] Chip {matched_chip} detectado; mantido: {current_chip}"
                )
                self._set_status("Pronto")

    # ── Ações ─────────────────────────────────────────────────────────

    def _refresh_ports(self):
        """Atualiza a lista de portas seriais disponíveis."""
        ports = self.flasher.list_serial_ports()
        self.port_combo.configure(values=ports)
        if ports:
            self.port_combo.set(ports[0])
        else:
            self.port_combo.set("")

    def _on_chip_changed(self, chip):
        """Atualiza endereços padrão quando o chip muda."""
        addrs = CHIP_ADDRESSES.get(chip, CHIP_ADDRESSES["ESP32"])
        for key, entry in self._addr_entries.items():
            entry.delete(0, "end")
            entry.insert(0, addrs[key])

    def _select_file(self, key):
        """Abre diálogo para selecionar arquivo .bin."""
        filepath = filedialog.askopenfilename(
            title=f"Selecionar {key}",
            filetypes=[("Binários", "*.bin"), ("Todos", "*.*")],
        )
        if filepath:
            entry = self._file_entries[key]
            entry.delete(0, "end")
            entry.insert(0, filepath)

    def _start_flash(self):
        """Inicia gravação de firmware em thread separada."""
        if self._flashing:
            return

        port = self.port_combo.get()
        if not port:
            self._set_status("Erro: nenhuma porta selecionada")
            return

        # Montar lista de arquivos com endereços
        files_with_addresses = []
        required = ["bootloader", "partitions", "firmware"]
        for key in ["bootloader", "partitions", "boot_app0", "firmware"]:
            filepath = self._file_entries[key].get().strip()
            address = self._addr_entries[key].get().strip()
            if filepath:
                if not os.path.isfile(filepath):
                    self._set_status(f"Erro: arquivo não encontrado — {filepath}")
                    return
                files_with_addresses.append((address, filepath))
            elif key in required:
                self._set_status(f"Erro: {key} é obrigatório")
                return

        # Fechar monitor serial se estiver ativo (liberar porta)
        if self.serial_monitor.is_running:
            self.serial_monitor.stop()
            self.log_append("[Monitor serial fechado para gravação]")

        chip = self.chip_combo.get()
        baud_str = self.baud_entry.get().strip()
        try:
            baud = int(baud_str)
            if baud <= 0:
                raise ValueError
        except ValueError:
            self._set_status(f"Erro: baud rate inválido — {baud_str}")
            return
        erase = self.erase_var.get()

        self._flashing = True
        self._set_buttons_state(False)
        self._set_status("Gravando...")
        # Reseta barra de progresso ao iniciar (Item 1)
        self.progress_bar.set(0)
        self.log_append("=" * 50)
        self.log_append(f"Iniciando gravação — {chip} em {port} @ {baud}")
        self.log_append("=" * 50)

        thread = threading.Thread(
            target=self._flash_worker,
            args=(port, chip, baud, files_with_addresses, erase),
            daemon=True,
        )
        thread.start()

    def _flash_worker(self, port, chip, baud, files_with_addresses, erase):
        """Worker de gravação — roda em thread separada."""
        try:
            ret = self.flasher.flash(port, chip, baud, files_with_addresses,
                                     erase_before=erase)
        except Exception as exc:  # noqa: BLE001
            self.after(0, lambda e=exc: self.log_append(f"[Erro inesperado] {e}"))
            ret = 1
        self.after(0, lambda: self._on_flash_complete(ret, port))

    def _on_flash_complete(self, returncode, port):
        """Callback chamado na main thread após conclusão da gravação."""
        self._flashing = False
        self._set_buttons_state(True)

        if returncode == 0:
            # Barra vai para 100% ao concluir com sucesso (Item 1)
            self.progress_bar.set(1.0)
            self._set_status("Gravação concluída com sucesso!")
            if self.monitor_var.get():
                self._start_monitor(port)
        else:
            # Reseta barra em erro/cancelamento (Item 1)
            self.progress_bar.set(0)
            self._set_status(f"Erro na gravação (código {returncode})")

    def _start_erase(self):
        """Inicia limpeza de flash em thread separada."""
        if self._flashing:
            return

        port = self.port_combo.get()
        if not port:
            self._set_status("Erro: nenhuma porta selecionada")
            return

        if self.serial_monitor.is_running:
            self.serial_monitor.stop()

        chip = self.chip_combo.get()

        self._flashing = True
        self._set_buttons_state(False)
        self._set_status("Apagando flash...")
        self.log_append("--- Apagando flash ---")

        def worker():
            try:
                ret = self.flasher.erase_flash(port, chip)
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda e=exc: self.log_append(f"[Erro inesperado] {e}"))
                ret = 1
            self.after(0, lambda: self._on_erase_complete(ret))

        threading.Thread(target=worker, daemon=True).start()

    def _on_erase_complete(self, returncode):
        """Callback chamado na main thread após limpeza da flash."""
        self._flashing = False
        self._set_buttons_state(True)
        if returncode == 0:
            self._set_status("Flash apagada com sucesso!")
        else:
            self._set_status(f"Erro ao apagar flash (código {returncode})")

    def _toggle_monitor(self):
        """Abre ou fecha o monitor serial."""
        if self.serial_monitor.is_running:
            self.serial_monitor.stop()
            self.log_append("[Monitor serial fechado]")
            self._set_status("Pronto")
            self.btn_monitor.configure(text="Monitor Serial")
        else:
            port = self.port_combo.get()
            if not port:
                self._set_status("Erro: nenhuma porta selecionada")
                return
            self._start_monitor(port)

    def _start_monitor(self, port):
        """Inicia o monitor serial na porta indicada."""
        try:
            baud = int(self.monitor_baud_entry.get().strip())
        except ValueError:
            baud = 115200

        try:
            self.serial_monitor.start(port, baud)
        except Exception as e:  # noqa: BLE001
            self.log_append(f"[Erro ao abrir monitor: {e}]")
            self._set_status("Erro no monitor serial")
            self.btn_monitor.configure(text="Monitor Serial")
            return

        self.log_append(f"[Monitor serial aberto — {port} @ {baud}]")
        self._set_status("Monitor Serial")
        self.btn_monitor.configure(text="Parar Monitor")

    # ── Item 6 — Controles do monitor serial ─────────────────────────

    def _send_monitor_command(self):
        """Envia o comando digitado no entry para a porta serial."""
        text = self.monitor_send_entry.get()
        if not text:
            return

        if not self.serial_monitor.is_running:
            self.log_append("[Monitor] Não há monitor ativo para enviar comandos")
            return

        success = self.serial_monitor.send(text)
        if success:
            self.log_append(f">>> {text}")
            self.monitor_send_entry.delete(0, "end")
        else:
            self.log_append("[Monitor] Falha ao enviar comando")

    def _on_timestamps_changed(self):
        """Propaga alteração do toggle de timestamps para o SerialMonitor."""
        self.serial_monitor.timestamps_enabled = self.timestamps_var.get()

    def _on_crlf_changed(self):
        """Propaga alteração do toggle CRLF para o SerialMonitor."""
        self.serial_monitor.crlf_enabled = self.crlf_var.get()

    def _on_filter_changed(self):
        """Recompila o regex de filtro quando o conteúdo do entry muda.

        Borda vermelha no entry se o regex for inválido.
        Regex vazio desativa o filtro.
        """
        pattern = self.filter_entry.get().strip()
        if not pattern:
            self._filter_regex = None
            self.filter_entry.configure(border_color=("gray75", "gray30"))
            return
        try:
            self._filter_regex = re.compile(pattern)
            # Borda padrão — regex válido
            self.filter_entry.configure(border_color=("gray75", "gray30"))
        except re.error:
            # Regex inválido — borda vermelha, sem crash
            self._filter_regex = None
            self.filter_entry.configure(border_color="red")

    def _should_display(self, line: str) -> bool:
        """Retorna True se a linha deve ser exibida com base no filtro ativo.

        Args:
            line: Linha de texto a verificar.

        Returns:
            True se não houver filtro ou se a linha casar o regex.
        """
        if self._filter_regex is None:
            return True
        return bool(self._filter_regex.search(line))

    # ── Callbacks ─────────────────────────────────────────────────────

    def _on_flash_output(self, line):
        """Callback do esptool — recebe output linha a linha (thread separada).

        Além de logar, parseia progresso para atualizar a barra (Item 1).
        """
        # Parsear progresso (Item 1)
        match = _RE_PROGRESS.search(line)
        if match:
            percent = int(match.group(1))
            value = percent / 100.0
            self.after(0, lambda v=value: self.progress_bar.set(v))

        self.after(0, lambda ln=line: self.log_append(ln))

    def _on_serial_data(self, line):
        """Callback do serial monitor — recebe dados da porta serial (thread separada).

        Aplica filtro regex antes de exibir (Item 6).
        """
        # O filtro é verificado na main thread para thread-safety do atributo
        self.after(0, lambda ln=line: self._display_serial_line(ln))
        # Se o monitor caiu (ex.: desconexão), restaura UI no thread principal.
        if not self.serial_monitor.is_running:
            self.after(0, self._reset_monitor_button)

    def _display_serial_line(self, line: str):
        """Exibe linha do monitor serial se passar pelo filtro regex."""
        if self._should_display(line):
            self.log_append(line)

    def _reset_monitor_button(self):
        """Restaura o botão do monitor para o estado inicial."""
        self.btn_monitor.configure(text="Monitor Serial")

    # ── Utilidades ────────────────────────────────────────────────────

    def log_append(self, text):
        """Adiciona texto à área de log com scroll automático."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_status(self, text):
        """Atualiza a barra de status."""
        self.status_label.configure(text=text)

    def _set_buttons_state(self, enabled):
        """Habilita ou desabilita botões e campos editáveis durante operações.

        Além dos botões de ação, trava porta, chip, baud, endereços, caminhos
        de arquivo e botões "Selecionar..." para evitar edição durante flash.
        """
        state = "normal" if enabled else "disabled"

        # Botões de ação
        self.btn_flash.configure(state=state)
        self.btn_erase.configure(state=state)
        # Bloqueia abertura de monitor durante operações que usam a porta.
        self.btn_monitor.configure(state=state)
        self.btn_refresh.configure(state=state)
        self.btn_detect_chip.configure(state=state)
        self.btn_import_pio.configure(state=state)

        # Campos de conexão
        self.port_combo.configure(state=state)
        self.chip_combo.configure(state=state)
        self.baud_entry.configure(state=state)

        # Campos de arquivo (.bin) e endereços
        for entry in self._file_entries.values():
            entry.configure(state=state)
        for entry in self._addr_entries.values():
            entry.configure(state=state)

        # Botões "Selecionar..." de cada arquivo
        for btn in self._file_browse_btns:
            btn.configure(state=state)

    # ── Persistência ──────────────────────────────────────────────────

    def _migrate_config(self):
        """Migra config.json legado da CWD para ~/.esp32_flasher/config.json.

        Se já existir um arquivo na CWD e ainda não houver um no destino,
        move (não copia) o arquivo para evitar duplicação.
        """
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if _CONFIG_FILE_LEGACY.is_file() and not CONFIG_FILE.exists():
            try:
                _CONFIG_FILE_LEGACY.rename(CONFIG_FILE)
            except OSError:
                pass  # Migração silenciosa — falha não é crítica

    def _load_config(self):
        """Carrega configurações salvas de ~/.esp32_flasher/config.json."""
        if not CONFIG_FILE.is_file():
            return
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        if cfg.get("port"):
            self.port_combo.set(cfg["port"])
        if cfg.get("chip") and cfg["chip"] in CHIPS:
            self.chip_combo.set(cfg["chip"])
            self._on_chip_changed(cfg["chip"])
        if cfg.get("baud"):
            self.baud_entry.delete(0, "end")
            self.baud_entry.insert(0, cfg["baud"])
        if cfg.get("monitor_baud"):
            self.monitor_baud_entry.delete(0, "end")
            self.monitor_baud_entry.insert(0, cfg["monitor_baud"])
        if "erase" in cfg:
            self.erase_var.set(cfg["erase"])
        if "auto_monitor" in cfg:
            self.monitor_var.set(cfg["auto_monitor"])
        if "timestamps" in cfg:
            self.timestamps_var.set(cfg["timestamps"])
            self.serial_monitor.timestamps_enabled = cfg["timestamps"]
        if "crlf" in cfg:
            self.crlf_var.set(cfg["crlf"])
            self.serial_monitor.crlf_enabled = cfg["crlf"]

        # Restaurar caminhos de arquivos
        for key in self._file_entries:
            path = cfg.get(f"file_{key}", "")
            if path:
                self._file_entries[key].delete(0, "end")
                self._file_entries[key].insert(0, path)

    def _save_config(self):
        """Salva configurações atuais em ~/.esp32_flasher/config.json."""
        cfg = {
            "port": self.port_combo.get(),
            "chip": self.chip_combo.get(),
            "baud": self.baud_entry.get(),
            "monitor_baud": self.monitor_baud_entry.get(),
            "erase": self.erase_var.get(),
            "auto_monitor": self.monitor_var.get(),
            "timestamps": self.timestamps_var.get(),
            "crlf": self.crlf_var.get(),
        }
        for key in self._file_entries:
            cfg[f"file_{key}"] = self._file_entries[key].get()

        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with CONFIG_FILE.open("w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except OSError:
            pass

    def destroy(self):
        """Salva configurações e encerra a aplicação."""
        if self.serial_monitor.is_running:
            self.serial_monitor.stop()
        self._save_config()
        super().destroy()
