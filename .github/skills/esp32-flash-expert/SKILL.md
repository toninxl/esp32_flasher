---
name: esp32-flash-expert
description: "Especialista em gravação de firmware ESP32 via esptool. Use para: implementar GUI de flash, configurar parâmetros esptool, mapear endereços de flash por chip (ESP32/S2/S3/C3), integrar com binários do PlatformIO Arduino, implementar serial monitor pós-flash, resolver erros de gravação, configurar PyInstaller para empacotamento."
argument-hint: "Descreva o que deseja implementar ou resolver na ferramenta de flash ESP32."
---

# ESP32 Flash Expert

Skill especialista para implementar e manter a aplicação ESP32 Flasher GUI — uma ferramenta desktop Python (CustomTkinter) que encapsula o `esptool.py` para gravar firmware em dispositivos ESP32.

## Quando Usar

- Implementar ou modificar qualquer componente do ESP32 Flasher GUI
- Resolver problemas de gravação (conexão, timeout, chip não detectado)
- Ajustar endereços de flash para novos chips ou partições customizadas
- Integrar binários gerados pelo PlatformIO com framework Arduino
- Configurar serial monitor para debug pós-flash
- Empacotar o projeto com PyInstaller

## Conhecimento de Domínio

### Binários do PlatformIO (Framework Arduino)

O PlatformIO com framework Arduino gera estes binários em `.pio/build/<env>/`:

| Arquivo          | Descrição               | Obrigatório           |
| ---------------- | ----------------------- | --------------------- |
| `bootloader.bin` | Second-stage bootloader | Sim                   |
| `partitions.bin` | Tabela de partições     | Sim                   |
| `boot_app0.bin`  | OTA boot selector       | Não (mas recomendado) |
| `firmware.bin`   | Aplicação do usuário    | Sim                   |

O usuário exporta esses 4 arquivos e os seleciona na GUI para gravação.

### Mapeamento de Endereços por Chip

Consultar [referência de chips](./references/chip-flash-map.md) para tabela completa.

Regra rápida:

- **ESP32, ESP32-S2**: bootloader em `0x1000`
- **ESP32-S3, ESP32-C3**: bootloader em `0x0`
- Todos os demais endereços são iguais entre chips

### esptool — Invocação e Parâmetros

Consultar [referência esptool](./references/esptool-commands.md) para comandos, flags e troubleshooting.

Regras críticas:

- Invocar como **subprocesso** (`sys.executable -m esptool`), não como biblioteca
- Sempre usar `--before default_reset --after hard_reset`
- Compressão `-z` reduz tempo de upload significativamente
- Baud `921600` é o máximo estável para a maioria dos adaptadores USB-Serial

## Procedimento: Implementação Completa

### 1. Estrutura do Projeto

```
esp32_flasher/
├── __init__.py          # Pacote vazio
├── __main__.py          # Entry point: inicializa e roda a GUI
├── gui.py               # Interface CustomTkinter
├── flasher.py           # Wrapper esptool via subprocess
└── serial_monitor.py    # Monitor serial pyserial em thread
```

Dependências (`requirements.txt`):

```
esptool>=4.0
pyserial
customtkinter>=5.0
```

### 2. flasher.py — Wrapper do esptool

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
            # Erase antes de write_flash
            self._run_cmd(cmd + ["erase_flash"])

        cmd.extend(["write_flash", "--flash_mode", flash_mode,
                     "--flash_size", "detect", "-z"])

        for address, filepath in files_with_addresses:
            cmd.extend([address, filepath])

        return self._run_cmd(cmd)

    def erase_flash(self, port, chip):
        cmd = [sys.executable, "-m", "esptool",
               "--chip", chip, "--port", port, "erase_flash"]
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

### 3. serial_monitor.py — Monitor Serial

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

    @property
    def is_running(self):
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

### 4. gui.py — Padrões Essenciais

- **Threading**: toda operação I/O em thread daemon; atualizar GUI via `self.after(0, callback)`
- **Log unificado**: `CTkTextbox` com `state="disabled"`, habilitar para inserir, scroll automático
- **Transição flash→serial**: detectar "Hard resetting via RTS pin..." no output, iniciar monitor automaticamente
- **Fechar monitor antes de flash**: sempre chamar `serial_monitor.stop()` antes de nova gravação
- **Persistência**: salvar/carregar config em `config.json` (porta, caminhos, bauds, chip, checkboxes)

### 5. Build com PyInstaller

```python
# build.spec — console=False para GUI, onefile=True
# hiddenimports: esptool, serial.tools.list_ports, customtkinter
```

## Troubleshooting

| Sintoma                             | Causa Provável                            | Solução                                  |
| ----------------------------------- | ----------------------------------------- | ---------------------------------------- |
| "Failed to connect"                 | ESP32 não entrou em bootloader            | Segurar BOOT, pressionar EN, soltar BOOT |
| "A fatal error occurred: Timed out" | Baud rate alto demais                     | Reduzir para 460800 ou 115200            |
| "Permission denied" na porta        | Porta em uso (monitor serial ativo)       | Fechar monitor antes de gravar           |
| "No serial data received"           | Baud do monitor ≠ baud do firmware        | Usar mesmo baud do `Serial.begin()`      |
| Bootloader address errado           | Chip selecionado não confere com hardware | Verificar chip real: `esptool chip_id`   |
| PyInstaller: "ModuleNotFoundError"  | Hidden import faltando                    | Adicionar módulo em `hiddenimports`      |
