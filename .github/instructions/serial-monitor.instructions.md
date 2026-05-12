---
description: "Use when implementing or modifying the serial monitor. Covers pyserial threading, USB disconnect handling, and GUI callback patterns for ESP32 serial output."
applyTo: "**/serial_monitor.py"
---
# Serial Monitor — Padrões

## Classe SerialMonitor

```python
import serial
import threading

class SerialMonitor:
    def __init__(self, callback):
        self._callback = callback  # Função para enviar linhas para a GUI
        self._serial = None
        self._thread = None
        self._running = False

    def start(self, port: str, baud: int = 115200):
        self._running = True
        self._serial = serial.Serial(port, baud, timeout=1)
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()

    @property
    def is_running(self) -> bool:
        return self._running

    def _read_loop(self):
        try:
            while self._running:
                if self._serial.in_waiting:
                    line = self._serial.readline().decode("utf-8", errors="replace").rstrip()
                    if line:
                        self._callback(line)
        except serial.SerialException:
            self._callback("[Monitor] Dispositivo desconectado")
        finally:
            self._running = False
```

## Regras Críticas

1. **Fechar antes de gravar** — `stop()` ANTES de iniciar qualquer operação de flash (liberar porta)
2. **Thread daemon** — usar `daemon=True` para não travar o encerramento da app
3. **Timeout na serial** — usar `timeout=1` para que o loop verifique `_running` periodicamente
4. **Decodificação** — `errors="replace"` para dados binários não travarem o monitor
5. **Desconexão USB** — capturar `serial.SerialException` e notificar GUI com mensagem amigável

## Integração com a GUI

```python
# Na GUI, usar self.after() para thread-safety
def on_serial_data(self, line: str):
    self.after(0, lambda: self.log_append(line))

# Iniciar monitor
self.serial_monitor = SerialMonitor(callback=self.on_serial_data)
self.serial_monitor.start(port, baud=115200)

# Parar monitor antes de flash
if self.serial_monitor.is_running:
    self.serial_monitor.stop()
```

## Baud Rate

- Padrão: 115200 (compatível com `Serial.begin(115200)` no Arduino)
- Configurável pelo usuário na GUI
