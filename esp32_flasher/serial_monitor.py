"""Monitor serial para leitura de dados do ESP32 via pyserial.

Suporta:
- Timestamps por linha (prefixo [HH:MM:SS.mmm])
- Envio de comandos para a porta serial
- Filtro de exibição por regex (não filtra leitura, apenas display)
"""

import re
import threading
import time

import serial


class SerialMonitor:
    """Lê dados da porta serial em thread separada e envia para callback."""

    def __init__(self, callback):
        """Inicializa o monitor serial.

        Args:
            callback: Função chamada com cada linha recebida da porta serial.
                      Assinatura: callback(linha_str, raw=False)
                      - raw=False → linha já processada (com timestamp se ativo)
                      - raw=True  → linha bruta antes de qualquer processamento
                        (reservado para uso futuro)
        """
        self._callback = callback
        self._serial = None
        self._thread = None
        self._running = False
        self._stop_requested = False

        # Configurações de exibição — modificáveis de fora (thread-safe via GIL
        # para atribuições simples de booleano/string).
        self.timestamps_enabled: bool = False
        self.crlf_enabled: bool = False  # True → envia \r\n; False → \n

    def start(self, port, baud=115200):
        """Abre a porta serial e inicia leitura em thread daemon.

        Args:
            port: Porta serial (ex: COM3).
            baud: Baud rate (padrão: 115200).
        """
        # Evita iniciar duas vezes (vazaria thread/porta).
        if self._running:
            return
        self._stop_requested = False
        self._serial = serial.Serial(port, baud, timeout=1)
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Para o monitor e fecha a porta serial."""
        self._stop_requested = True
        self._running = False
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
        except Exception:
            pass
        self._serial = None

    def send(self, text: str):
        """Envia texto para a porta serial.

        Acrescenta \\r\\n ou \\n dependendo de ``crlf_enabled``.

        Args:
            text: Texto a enviar (sem terminador de linha).

        Returns:
            True se enviado, False se porta não estiver aberta.
        """
        if not self._running or self._serial is None:
            return False
        terminator = "\r\n" if self.crlf_enabled else "\n"
        try:
            self._serial.write((text + terminator).encode("utf-8", errors="replace"))
            return True
        except (serial.SerialException, OSError):
            return False

    @property
    def is_running(self):
        """Retorna True se o monitor está ativo."""
        return self._running

    def _format_line(self, line: str) -> str:
        """Aplica timestamp à linha se habilitado.

        Args:
            line: Linha recebida da porta serial.

        Returns:
            Linha formatada com ou sem timestamp.
        """
        if self.timestamps_enabled:
            now = time.time()
            # Formata como HH:MM:SS.mmm usando o horário local
            t = time.localtime(now)
            millis = int((now % 1) * 1000)
            prefix = time.strftime(f"%H:%M:%S.{millis:03d}", t)
            return f"[{prefix}] {line}"
        return line

    def _read_loop(self):
        """Loop de leitura — roda em thread daemon."""
        try:
            while self._running and self._serial is not None:
                try:
                    if self._serial.in_waiting:
                        raw = self._serial.readline()
                        line = raw.decode("utf-8", errors="replace").rstrip()
                        if line:
                            formatted = self._format_line(line)
                            self._callback(formatted)
                    else:
                        # Evita busy-loop consumindo 100% de CPU.
                        time.sleep(0.02)
                except (AttributeError, TypeError):
                    # Porta foi fechada por stop() em outra thread.
                    break
        except serial.SerialException:
            if not self._stop_requested:
                self._callback("[Monitor] Dispositivo desconectado")
        except OSError:
            if not self._stop_requested:
                self._callback("[Monitor] Erro de comunicação")
        finally:
            self._running = False
