# ESP32 Flasher GUI

Aplicação desktop que encapsula o [esptool](https://github.com/espressif/esptool) para gravar firmware em dispositivos ESP32 de forma simplificada. Interface gráfica moderna com dark mode, endereços de flash pré-configurados por chip e monitor serial integrado.

Projetada para binários gerados pelo **PlatformIO** com framework **Arduino**.

## Funcionalidades

- **Interface gráfica** com CustomTkinter (dark mode, cantos arredondados)
- **Chips suportados**: ESP32, ESP32-S2, ESP32-S3, ESP32-C3
- **Endereços de flash pré-configurados** por chip — atualizam automaticamente ao selecionar
- **4 arquivos de flash**: bootloader, partitions, boot_app0 (opcional), firmware
- **Limpar flash** antes de gravar (opcional)
- **Monitor serial integrado** — abre automaticamente após gravação bem-sucedida
- **Detecção automática** de portas seriais e tamanho da flash
- **Reset automático via RTS** após gravação (`--after hard_reset`)
- **Persistência de configurações** em JSON local

## Requisitos

- Python 3.8+
- Driver USB-Serial do dispositivo (CP210x, CH340, ou USB nativo do chip)

## Instalação

```bash
git clone https://github.com/seu-usuario/esp32_flasher.git
cd esp32_flasher
pip install -r requirements.txt
```

## Uso

```bash
python -m esp32_flasher
```

### Fluxo de gravação

1. Selecione a **porta serial** e o **chip** (ESP32, ESP32-S3, etc.)
2. Selecione os **arquivos .bin** exportados do PlatformIO:
   - `bootloader.bin` — em `.pio/build/<env>/`
   - `partitions.bin` — em `.pio/build/<env>/`
   - `boot_app0.bin` — opcional, em `~/.platformio/packages/framework-arduinoespressif32/tools/partitions/`
   - `firmware.bin` — em `.pio/build/<env>/`
3. Clique em **"Gravar Firmware"**
4. O monitor serial abre automaticamente após o flash (se habilitado)

### Endereços de flash padrão

| Chip     | Bootloader | Partitions | boot_app0 | Firmware |
| -------- | ---------- | ---------- | --------- | -------- |
| ESP32    | 0x1000     | 0x8000     | 0xe000    | 0x10000  |
| ESP32-S2 | 0x1000     | 0x8000     | 0xe000    | 0x10000  |
| ESP32-S3 | 0x0        | 0x8000     | 0xe000    | 0x10000  |
| ESP32-C3 | 0x0        | 0x8000     | 0xe000    | 0x10000  |

## Build do Executável

### Pré-requisitos

```bash
pip install pyinstaller
```

### Gerar .exe

```bash
pyinstaller build.spec
```

O executável é gerado em `dist/ESP32_Flasher.exe` — não requer Python instalado na máquina de destino.

### Builds multi-arquitetura

| Build | Python necessário | Executável                | Compatibilidade   |
| ----- | ----------------- | ------------------------- | ----------------- |
| x86   | Python 32-bit     | `esp32_flasher_win32.exe` | Windows 32/64-bit |
| x64   | Python 64-bit     | `esp32_flasher_win64.exe` | Windows 64-bit    |

**Alternativa simples**: gerar apenas o build x86 com Python 32-bit — roda em ambas as arquiteturas.

## Estrutura do Projeto

```
esp32_flasher/
├── __init__.py          # Pacote
├── __main__.py          # Entry point
├── gui.py               # Interface CustomTkinter
├── flasher.py           # Wrapper do esptool (subprocess)
└── serial_monitor.py    # Monitor serial (pyserial + thread)
```

## Licença

MIT
