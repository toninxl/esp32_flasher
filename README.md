# ESP32 Flasher

Ferramenta para gravar firmware em dispositivos ESP32 via porta serial.

## Funcionalidades

- Detecção automática da porta serial conectada ao ESP32
- Upload de firmware (arquivos `.bin`) para o dispositivo
- Suporte aos modos de gravação padrão do ESP32 (flash, erase)
- Interface simples de linha de comando

## Requisitos

- Python 3.8+
- [esptool](https://github.com/espressif/esptool) (`pip install esptool`)
- Driver USB-Serial do dispositivo (ex: CP210x, CH340)

## Instalação

```bash
git clone https://github.com/seu-usuario/esp32_flasher.git
cd esp32_flasher
pip install -r requirements.txt
```

## Uso

```bash
python flasher.py --port /dev/ttyUSB0 --firmware firmware.bin
```

### Opções

| Opção | Descrição |
|-------|-----------|
| `--port` | Porta serial do dispositivo (ex: `/dev/ttyUSB0`, `COM3`) |
| `--firmware` | Caminho para o arquivo `.bin` a ser gravado |
| `--baud` | Taxa de transmissão (padrão: `115200`) |
| `--erase` | Apaga a flash antes de gravar |

## Licença

MIT
