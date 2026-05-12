# Referência de Comandos esptool

## Gravação de Firmware (write_flash)

```bash
python -m esptool \
  --chip esp32 \
  --port COM3 \
  --baud 921600 \
  --before default_reset \
  --after hard_reset \
  write_flash \
  --flash_mode dio \
  --flash_size detect \
  -z \
  0x1000 bootloader.bin \
  0x8000 partitions.bin \
  0xe000 boot_app0.bin \
  0x10000 firmware.bin
```

### Flags Detalhadas

| Flag           | Valor                         | Descrição                                              |
| -------------- | ----------------------------- | ------------------------------------------------------ |
| `--chip`       | esp32/esp32s2/esp32s3/esp32c3 | Chip alvo                                              |
| `--port`       | COM3, /dev/ttyUSB0            | Porta serial                                           |
| `--baud`       | 921600                        | Baud rate para upload (não para serial monitor)        |
| `--before`     | default_reset                 | Reset automático para entrar no bootloader via DTR/RTS |
| `--after`      | hard_reset                    | Hard reset via RTS após gravação (executa firmware)    |
| `--flash_mode` | dio                           | Dual I/O — compatível com todos os módulos             |
| `--flash_size` | detect                        | Detecta automaticamente o tamanho da flash             |
| `-z`           | —                             | Comprime dados durante upload (mais rápido)            |

## Apagar Flash (erase_flash)

```bash
python -m esptool --chip esp32 --port COM3 erase_flash
```

Apaga **toda** a flash, incluindo NVS, SPIFFS, firmware. Útil para:

- Limpar configurações salvas em NVS
- Resolver problemas de partições corrompidas
- Reset completo do dispositivo

## Identificar Chip (chip_id)

```bash
python -m esptool --port COM3 chip_id
```

Retorna tipo do chip, MAC address, e revisão. Útil para debug.

## Output Esperado (Sucesso)

```
esptool.py v4.x
Serial port COM3
Connecting....
Chip is ESP32-D0WD-V3 (revision v3.1)
Features: WiFi, BT, Dual Core, 240MHz
Crystal is 40MHz
MAC: aa:bb:cc:dd:ee:ff
Uploading stub...
Running stub...
Stub running...
Changing baud rate to 921600
Changed.
Configuring flash size...
Auto-detected Flash size: 4MB
Compressed 26368 bytes to 16218...
Writing at 0x00001000... (100 %)
Wrote 26368 bytes (16218 compressed) at 0x00001000 in 0.4 seconds
...
Hard resetting via RTS pin...
```

**A string "Hard resetting via RTS pin..." indica sucesso e é o trigger para iniciar o serial monitor.**

## Códigos de Retorno

| Código | Significado                          |
| ------ | ------------------------------------ |
| 0      | Sucesso                              |
| 1      | Erro genérico                        |
| 2      | Erro de conexão (chip não respondeu) |

## Erros Comuns e Soluções

### "Failed to connect to ESP32: Timed out waiting for packet header"

- **Causa**: Chip não entrou no modo bootloader
- **Solução**: Segurar botão BOOT → pressionar EN/RESET → soltar BOOT
- Alguns boards fazem isso automaticamente via DTR/RTS (CP210x)

### "A serial exception error occurred"

- **Causa**: Porta serial em uso por outro processo
- **Solução**: Fechar serial monitor, outro terminal, ou outra instância

### "Invalid head of packet (0xNN): Possible serial noise"

- **Causa**: Cabo USB ruim ou longo
- **Solução**: Usar cabo mais curto, reduzir baud para 460800

### "Wrong boot mode detected (0xNN)! The chip needs to be in download mode."

- **Causa**: GPIO0 não está LOW durante reset
- **Solução**: Verificar circuito de auto-reset (DTR→EN, RTS→GPIO0)

### Invocação via Python subprocess

```python
import subprocess, sys

cmd = [sys.executable, "-m", "esptool", "--chip", "esp32", ...]

process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,   # Merge stderr no stdout
    text=True,
    bufsize=1,                  # Line-buffered
)

for line in process.stdout:
    print(line, end="")         # Ou enviar para callback da GUI

returncode = process.wait()
```

**IMPORTANTE**: Usar `sys.executable` (não `"python"`) para garantir que usa o mesmo interpretador do ambiente virtual.
