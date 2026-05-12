---
description: "Use when implementing or modifying the esptool flash wrapper. Covers subprocess invocation, argument building, output capture, and chip-specific parameters for ESP32 firmware flashing."
applyTo: "**/flasher.py"
---
# esptool Flasher — Padrões

## Invocação via Subprocesso

Usar `subprocess.Popen` (não `esptool.main()`) para capturar output em tempo real:

```python
import subprocess
import sys

def flash(self, port, chip, baud, files_with_addresses, erase_before=False,
          flash_mode="dio"):
    cmd = [
        sys.executable, "-m", "esptool",
        "--chip", chip,
        "--port", port,
        "--baud", str(baud),
        "--before", "default_reset",
        "--after", "hard_reset",
        "write_flash",
        "--flash_mode", flash_mode,
        "--flash_size", "detect",
        "-z",
    ]
    # Adicionar pares endereço + arquivo
    for address, filepath in files_with_addresses:
        cmd.extend([address, filepath])

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    # Ler output linha a linha e enviar para callback
    for line in process.stdout:
        self.output_callback(line.rstrip())
    process.wait()
    return process.returncode
```

## Erase Flash

```python
def erase_flash(self, port, chip):
    cmd = [
        sys.executable, "-m", "esptool",
        "--chip", chip,
        "--port", port,
        "erase_flash",
    ]
    # Mesmo padrão de Popen com captura de output
```

## Detecção de Portas

```python
from serial.tools import list_ports

def list_serial_ports(self) -> list[str]:
    return [p.device for p in list_ports.comports()]
```

## Chip → Argumentos

| Parâmetro | Valor |
|-----------|-------|
| `--chip` | `esp32`, `esp32s2`, `esp32s3`, `esp32c3` (lowercase, sem hífen) |
| `--baud` | 921600 (padrão para flash) |
| `--flash_mode` | `dio` |
| `--flash_size` | `detect` |

## Validação Antes de Flash

- Verificar que todos os arquivos obrigatórios existem (bootloader, partitions, firmware)
- boot_app0.bin é opcional — se não fornecido, omitir do comando
- Porta serial não pode estar vazia
- Validar que endereços estão no formato `0xNNNN`

## Tratamento de Erros

- Capturar `FileNotFoundError` se esptool não instalado
- Capturar timeout de conexão (esptool retorna código != 0)
- Sempre reportar return code ao callback
