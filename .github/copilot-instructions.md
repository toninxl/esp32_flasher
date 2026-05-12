# ESP32 Flasher GUI — Project Guidelines

## Overview

Aplicação desktop GUI em Python (CustomTkinter) que encapsula o `esptool.py` para gravar firmware em dispositivos ESP32. Os binários de entrada são gerados pelo PlatformIO com framework Arduino.

## Architecture

```
esp32_flasher/
├── __init__.py          # Pacote
├── __main__.py          # Entry point (inicializa GUI)
├── gui.py               # Interface CustomTkinter (~350 linhas)
├── flasher.py           # Wrapper do esptool via subprocesso (~100 linhas)
└── serial_monitor.py    # Monitor serial pyserial em thread (~60 linhas)
```

- **gui.py** → orquestra tudo: chama `flasher.py` para gravar, `serial_monitor.py` para monitorar
- **flasher.py** → invoca `esptool` como **subprocesso** (não como lib) para capturar output fielmente
- **serial_monitor.py** → lê porta serial em thread separada, envia linhas via callback para a GUI

## Build & Run

```bash
pip install -r requirements.txt
python -m esp32_flasher           # Rodar a GUI
pyinstaller build.spec            # Gerar executável .exe
```

## Conventions

### Linguagem e estilo
- Python 3.8+ compatível
- Docstrings e comentários em português
- Nomes de variáveis/funções em inglês (snake_case)
- Classes em PascalCase

### Chips suportados e endereços padrão
| Chip | Bootloader | Partitions | boot_app0 | Firmware |
|------|-----------|------------|-----------|----------|
| ESP32 | 0x1000 | 0x8000 | 0xe000 | 0x10000 |
| ESP32-S2 | 0x1000 | 0x8000 | 0xe000 | 0x10000 |
| ESP32-S3 | 0x0 | 0x8000 | 0xe000 | 0x10000 |
| ESP32-C3 | 0x0 | 0x8000 | 0xe000 | 0x10000 |

### Parâmetros esptool padrão
- `--before default_reset` — reset para bootloader
- `--after hard_reset` — reset via RTS após gravação
- `--flash_size detect` — detecção automática
- `--flash_mode dio` — modo padrão
- `-z` — compressão durante upload
- Baud rate flash: 921600 (padrão)

### GUI
- Usar CustomTkinter (dark mode nativo, widgets arredondados)
- Operações de flash/serial em threads separadas — nunca travar a GUI
- Área de log única: exibe output do esptool e transita para serial monitor automaticamente
- Persistir configurações em JSON local

### Serial Monitor
- Fechar monitor antes de iniciar nova gravação (liberar porta)
- Tratar desconexão USB com mensagem amigável
- Baud rate monitor: 115200 (padrão, configurável)

## Key Files

- [Plano completo do projeto](.github/prompts/plan-esp32Flasher.prompt.md) — decisões de design, steps, verificação
