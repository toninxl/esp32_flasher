---
name: esp32-flash-expert
description: Especialista em gravação de firmware ESP32 via esptool. Use para implementar GUI de flash com CustomTkinter, configurar parâmetros esptool, mapear endereços de flash por chip (ESP32/S2/S3/C3), integrar binários do PlatformIO Arduino, implementar serial monitor pós-flash, resolver erros de gravação e empacotar com PyInstaller.
---

# ESP32 Flash Expert

Skill especialista para implementar e manter o **ESP32 Flasher GUI** — aplicação desktop Python (CustomTkinter) que encapsula `esptool.py` para gravar firmware em dispositivos ESP32 a partir de binários PlatformIO/Arduino.

## Quando usar

- Implementar/modificar qualquer componente do ESP32 Flasher GUI
- Resolver problemas de gravação (conexão, timeout, chip não detectado)
- Ajustar endereços de flash para novos chips ou partições customizadas
- Integrar binários gerados pelo PlatformIO com framework Arduino
- Configurar serial monitor para debug pós-flash
- Empacotar o projeto com PyInstaller

## Conhecimento de domínio

### Binários do PlatformIO (Arduino)

Gerados em `.pio/build/<env>/`:

| Arquivo          | Descrição               | Obrigatório           |
| ---------------- | ----------------------- | --------------------- |
| `bootloader.bin` | Second-stage bootloader | Sim                   |
| `partitions.bin` | Tabela de partições     | Sim                   |
| `boot_app0.bin`  | OTA boot selector       | Não (mas recomendado) |
| `firmware.bin`   | Aplicação do usuário    | Sim                   |

### Endereços por chip

| Chip     | Bootloader | Partitions | boot_app0 | Firmware |
| -------- | ---------- | ---------- | --------- | -------- |
| ESP32    | 0x1000     | 0x8000     | 0xe000    | 0x10000  |
| ESP32-S2 | 0x1000     | 0x8000     | 0xe000    | 0x10000  |
| ESP32-S3 | 0x0        | 0x8000     | 0xe000    | 0x10000  |
| ESP32-C3 | 0x0        | 0x8000     | 0xe000    | 0x10000  |

Regra rápida: ESP32/S2 → bootloader em `0x1000`; S3/C3 → `0x0`. Demais endereços iguais.

### Regras críticas do esptool

- Invocar como **subprocesso**: `sys.executable -m esptool` (nunca como lib)
- Sempre `--before default_reset --after hard_reset`
- `--flash_size detect --flash_mode dio -z`
- Baud flash padrão: `921600` (máximo estável p/ maioria de USB-Serial)
- Baud monitor padrão: `115200`

## Estrutura esperada do projeto

```
esp32_flasher/
├── __init__.py          # Pacote
├── __main__.py          # Entry point: inicializa a GUI
├── gui.py               # Interface CustomTkinter
├── flasher.py           # Wrapper esptool via subprocess
└── serial_monitor.py    # Monitor serial pyserial em thread
```

`requirements.txt`:

```
esptool>=4.0
pyserial
customtkinter>=5.0
```

## Padrões de implementação

### flasher.py

```python
import subprocess
import sys
from serial.tools import list_ports

class ESP32Flasher:
    def __init__(self, output_callback):
        self._callback = output_callback

    def list_serial_ports(self) -> list:
        return [p.device for p in list_ports.comports()]

    def flash(self, port, chip, baud, files_with_addresses,
              erase_before=False, flash_mode="dio"):
        cmd = [sys.executable, "-m", "esptool",
               "--chip", chip, "--port", port, "--baud", str(baud),
               "--before", "default_reset", "--after", "hard_reset"]
        if erase_before:
            self._run_cmd(cmd + ["erase_flash"])
        cmd.extend(["write_flash", "--flash_mode", flash_mode,
                    "--flash_size", "detect", "-z"])
        for address, filepath in files_with_addresses:
            cmd.extend([address, filepath])
        return self._run_cmd(cmd)

    def _run_cmd(self, cmd):
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        for line in process.stdout:
            self._callback(line.rstrip())
        process.wait()
        return process.returncode
```

### serial_monitor.py

```python
import serial
import threading

class SerialMonitor:
    def __init__(self, callback):
        self._callback = callback
        self._serial = None
        self._running = False

    def start(self, port, baud=115200):
        self._running = True
        self._serial = serial.Serial(port, baud, timeout=1)
        threading.Thread(target=self._read_loop, daemon=True).start()

    def stop(self):
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()

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

### gui.py — padrões

- **Threading**: toda I/O em thread daemon; atualizar GUI via `self.after(0, ...)`
- **Log unificado**: `CTkTextbox` com `state="disabled"`; habilitar para inserir, scroll automático
- **Transição flash → serial**: detectar `"Hard resetting via RTS pin..."` e iniciar monitor automaticamente
- **Fechar monitor antes de flash**: sempre `serial_monitor.stop()` antes de nova gravação
- **Persistência**: `config.json` com porta, caminhos, bauds, chip e checkboxes

### Build (PyInstaller)

`build.spec` com `console=False`, `onefile=True`, `hiddenimports=["esptool", "serial.tools.list_ports", "customtkinter"]`.

## Troubleshooting

| Sintoma                             | Causa provável                            | Solução                                    |
| ----------------------------------- | ----------------------------------------- | ------------------------------------------ |
| "Failed to connect"                 | ESP32 não entrou em bootloader            | Segurar BOOT, pressionar EN, soltar BOOT   |
| "A fatal error occurred: Timed out" | Baud rate alto demais                     | Reduzir para 460800 ou 115200              |
| "Permission denied" na porta        | Porta em uso (monitor serial ativo)       | Fechar monitor antes de gravar             |
| "No serial data received"           | Baud do monitor ≠ baud do firmware        | Usar mesmo baud do `Serial.begin()`        |
| Bootloader address errado           | Chip selecionado ≠ hardware               | Verificar com `esptool chip_id`            |
| PyInstaller: "ModuleNotFoundError"  | Hidden import faltando                    | Adicionar módulo em `hiddenimports`        |

## Referências adicionais

Quando precisar de detalhes extras consulte os arquivos de referência originais do projeto:

- `.github/skills/esp32-flash-expert/references/chip-flash-map.md`
- `.github/skills/esp32-flash-expert/references/esptool-commands.md`
- `.github/skills/esp32-flash-expert/references/platformio-build-output.md`
- `.github/instructions/*.instructions.md`
