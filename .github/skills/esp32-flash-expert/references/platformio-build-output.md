# Estrutura de Build do PlatformIO (Arduino)

## Diretório de Output

Após compilar com `pio run`, os binários ficam em:

```
.pio/build/<env>/
├── bootloader.bin       # Second-stage bootloader (gerado pelo ESP-IDF)
├── partitions.bin       # Tabela de partições compilada
├── firmware.bin         # Aplicação do usuário (sketch + libs)
└── firmware.elf         # ELF para debug (não usado na gravação)
```

O `boot_app0.bin` fica no diretório de ferramentas do PlatformIO:

```
~/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin
```

## Como o Usuário Exporta os Binários

1. Compilar no PlatformIO: `pio run`
2. Copiar de `.pio/build/<env>/`:
   - `bootloader.bin`
   - `partitions.bin`
   - `firmware.bin`
3. Copiar `boot_app0.bin` do diretório de ferramentas do framework
4. Reunir os 4 arquivos em uma pasta para usar na GUI

**Atalho CLI do PlatformIO:**

```bash
# Mostra o comando completo de flash com todos os endereços
pio run -t upload --verbose
```

Esse verbose mostra exatamente os argumentos que o esptool recebe, incluindo endereços.

## platformio.ini — Configurações Relevantes

```ini
[env:esp32]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200        # Baud do Serial Monitor
upload_speed = 921600         # Baud do flash
board_build.partitions = default.csv  # Tabela de partições
```

O `upload_speed` e `monitor_speed` do platformio.ini são os mesmos defaults da GUI:

- Flash baud: 921600
- Monitor baud: 115200

## Merge de Binários (Alternativa)

O PlatformIO também pode gerar um binário único mergeado:

```bash
# Gera um único .bin com todos os segmentos
esptool --chip esp32 merge_bin -o merged.bin \
  --flash_mode dio --flash_size 4MB \
  0x1000 bootloader.bin \
  0x8000 partitions.bin \
  0xe000 boot_app0.bin \
  0x10000 firmware.bin
```

Esse binário único é gravado no endereço `0x0`. A GUI foca na gravação individual (4 arquivos separados) por ser o fluxo padrão do PlatformIO.
