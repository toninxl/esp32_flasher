"""Wrapper do esptool para gravação de firmware ESP32 via subprocesso.

Quando empacotado com PyInstaller (``sys.frozen = True``), ``sys.executable``
aponta para o próprio ``.exe`` e não pode invocar ``-m esptool`` via
subprocesso sem reentrância no bootloader PyInstaller.  Nesse caso, o esptool
é chamado in-process via ``esptool.main()``, com stdout redirecionado para o
callback de linha usando ``contextlib.redirect_stdout``.

Fora do modo frozen (desenvolvimento normal), o subprocesso é mantido para
isolamento de processo e captura de stderr combinado.
"""

import contextlib
import io
import os
import subprocess
import sys

from serial.tools import list_ports

# Mapa de chips para nome usado pelo esptool (lowercase, sem hífen)
CHIP_ESPTOOL_MAP = {
    "ESP32": "esp32",
    "ESP32-S2": "esp32s2",
    "ESP32-S3": "esp32s3",
    "ESP32-C3": "esp32c3",
}


class ESP32Flasher:
    """Encapsula o esptool para operações de flash e erase."""

    def __init__(self, output_callback):
        """Inicializa o flasher com callback para output em tempo real.

        Args:
            output_callback: Função chamada com cada linha de output do esptool.
        """
        self._callback = output_callback

    @staticmethod
    def list_serial_ports():
        """Retorna lista de portas seriais disponíveis."""
        return [p.device for p in list_ports.comports()]

    def flash(self, port, chip, baud, files_with_addresses,
              erase_before=False, flash_mode="dio"):
        """Grava firmware no dispositivo ESP32.

        Args:
            port: Porta serial (ex: COM3).
            chip: Chip selecionado (ex: "ESP32", "ESP32-S3").
            baud: Baud rate para upload (ex: 921600).
            files_with_addresses: Lista de tuplas (endereço, caminho_arquivo).
            erase_before: Se True, apaga flash antes de gravar.
            flash_mode: Modo de flash (padrão: "dio").

        Returns:
            Código de retorno do esptool (0 = sucesso).
        """
        chip_arg = CHIP_ESPTOOL_MAP.get(chip, chip.lower().replace("-", ""))

        # Validar que os arquivos existem
        for address, filepath in files_with_addresses:
            if not os.path.isfile(filepath):
                self._callback(f"[Erro] Arquivo não encontrado: {filepath}")
                return 1

        if erase_before:
            self._callback("--- Apagando flash ---")
            ret = self.erase_flash(port, chip)
            if ret != 0:
                return ret
            self._callback("--- Flash apagada. Iniciando gravação ---")

        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", chip_arg,
            "--port", port,
            "--baud", str(baud),
            "--before", "default_reset",
            "--after", "hard_reset",
            "write_flash",
            "--flash_mode", flash_mode,
            "--flash_size", "detect",
            "-z",
        ]
        for address, filepath in files_with_addresses:
            cmd.extend([address, filepath])

        return self._run_cmd(cmd)

    def detect_chip(self, port):
        """Detecta o chip ESP32 conectado na porta serial.

        Executa ``esptool --port <port> chip_id`` e parseia a linha
        ``Chip is <nome>``.

        Args:
            port: Porta serial (ex: COM3).

        Returns:
            Tupla (chip_name: str | None, returncode: int).
            chip_name será None se não conseguir parsear.
        """
        import re as _re  # noqa: PLC0415

        cmd = [
            sys.executable, "-m", "esptool",
            "--port", port,
            "chip_id",
        ]

        detected: list[str | None] = [None]
        original_callback = self._callback

        def detecting_callback(line):
            """Intercepta linhas para parsear o nome do chip."""
            original_callback(line)
            match = _re.search(r"Chip is (ESP32[-\w]*)", line, _re.IGNORECASE)
            if match:
                detected[0] = match.group(1).upper()

        # Substitui temporariamente o callback para interceptar output
        self._callback = detecting_callback
        try:
            ret = self._run_cmd(cmd)
        finally:
            self._callback = original_callback

        return detected[0], ret

    def erase_flash(self, port, chip):
        """Apaga toda a flash do dispositivo.

        Args:
            port: Porta serial.
            chip: Chip selecionado.

        Returns:
            Código de retorno do esptool.
        """
        chip_arg = CHIP_ESPTOOL_MAP.get(chip, chip.lower().replace("-", ""))
        cmd = [
            sys.executable, "-m", "esptool",
            "--chip", chip_arg,
            "--port", port,
            "erase_flash",
        ]
        return self._run_cmd(cmd)

    def _run_cmd(self, cmd):
        """Executa comando e envia output linha a linha para o callback.

        Quando o executável está empacotado (frozen), delega para
        ``_run_inprocess`` para evitar reentrância no bootloader PyInstaller.
        Caso contrário, usa subprocesso normal.

        Args:
            cmd: Lista de argumentos tal como montada em ``flash`` e
                 ``erase_flash`` — começa com ``[sys.executable, '-m', 'esptool', ...]``.

        Returns:
            Código de retorno inteiro (0 = sucesso).
        """
        if getattr(sys, "frozen", False):
            # Executável PyInstaller: descarta os dois primeiros tokens
            # (sys.executable e '-m') e o terceiro ('esptool') para obter
            # somente os argumentos esptool.
            esptool_args = cmd[3:]
            return self._run_inprocess(esptool_args)
        return self._run_subprocess(cmd)

    def _run_subprocess(self, cmd):
        """Executa esptool via subprocesso, capturando output linha a linha."""
        # No Windows + GUI sem console, evita janela de cmd piscando.
        popen_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            process = subprocess.Popen(cmd, **popen_kwargs)
            assert process.stdout is not None
            for line in process.stdout:
                self._callback(line.rstrip())
            process.wait()
            return process.returncode
        except FileNotFoundError:
            self._callback("[Erro] esptool não encontrado. Instale com: pip install esptool")
            return 1
        except OSError as exc:
            self._callback(f"[Erro] Falha ao executar esptool: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001
            self._callback(f"[Erro inesperado] {exc}")
            return 1

    def _run_inprocess(self, esptool_args):
        """Executa esptool in-process via ``esptool.main()`` (modo frozen).

        Redireciona stdout para um buffer de string e entrega cada linha ao
        callback após a chamada concluir.  O retorno de ``esptool.main()``
        é void; erros são sinalizados por exceções — capturadas aqui e
        convertidas em código de retorno 1.

        Args:
            esptool_args: Lista de argumentos esptool (sem 'sys.executable',
                          '-m' nem 'esptool').

        Returns:
            0 em sucesso, 1 em falha.
        """
        try:
            import esptool  # noqa: PLC0415 — import tardio intencional
        except ImportError:
            self._callback("[Erro] esptool não encontrado no executável empacotado.")
            return 1

        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                esptool.main(esptool_args)
            returncode = 0
        except SystemExit as exc:
            # esptool.main() chama sys.exit(1) em falhas — captura o código.
            returncode = exc.code if isinstance(exc.code, int) else 1
        except Exception as exc:  # noqa: BLE001
            self._callback(f"[Erro inesperado] {exc}")
            returncode = 1

        # Entrega o output acumulado linha a linha (mesmo formato do subprocess).
        for line in buf.getvalue().splitlines():
            self._callback(line.rstrip())

        return returncode
