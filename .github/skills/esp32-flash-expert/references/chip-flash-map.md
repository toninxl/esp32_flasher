# Mapeamento de Flash por Chip ESP32

## Endereços de Gravação (PlatformIO Arduino)

| Chip     | Bootloader | Partitions | boot_app0 | Firmware | Flash Mode |
| -------- | ---------- | ---------- | --------- | -------- | ---------- |
| ESP32    | 0x1000     | 0x8000     | 0xe000    | 0x10000  | dio        |
| ESP32-S2 | 0x1000     | 0x8000     | 0xe000    | 0x10000  | dio        |
| ESP32-S3 | 0x0        | 0x8000     | 0xe000    | 0x10000  | dio        |
| ESP32-C3 | 0x0        | 0x8000     | 0xe000    | 0x10000  | dio        |

## Nome do Chip no esptool

O `--chip` do esptool usa nomes lowercase sem hífen:

| GUI (display) | esptool `--chip` |
| ------------- | ---------------- |
| ESP32         | esp32            |
| ESP32-S2      | esp32s2          |
| ESP32-S3      | esp32s3          |
| ESP32-C3      | esp32c3          |

## Diferenças Críticas entre Chips

### Bootloader Address

- **ESP32 / ESP32-S2**: Second-stage bootloader começa em `0x1000` (primeiro 4KB reservados para first-stage ROM bootloader)
- **ESP32-S3 / ESP32-C3**: Bootloader começa em `0x0` (arquitetura RISC-V no C3, novo layout no S3)

**ERRO COMUM**: Gravar bootloader no endereço errado = chip não boota. Se o usuário selecionar ESP32-S3 mas usar endereço 0x1000, o dispositivo não funcionará.

### Flash Size

- Maioria dos módulos: 4MB (ESP32-WROOM, ESP32-S3-WROOM)
- Alguns módulos: 8MB, 16MB (ESP32-S3-WROOM-2)
- `--flash_size detect` resolve automaticamente na maioria dos casos

### USB vs UART

- **ESP32**: Apenas UART via CP210x/CH340
- **ESP32-S2**: USB OTG nativo (CDC) + UART
- **ESP32-S3**: USB OTG nativo (CDC/JTAG) + UART
- **ESP32-C3**: USB Serial/JTAG integrado + UART

Para chips com USB nativo, a porta pode aparecer como "USB JTAG/serial debug unit" no device manager.

## Partições Comuns (PlatformIO)

### default.csv (1.2MB app, 1.5MB SPIFFS)

```
nvs,      data, nvs,     0x9000,  0x5000
otadata,  data, ota,     0xe000,  0x2000
app0,     app,  ota_0,   0x10000, 0x140000
app1,     app,  ota_1,   0x150000,0x140000
spiffs,   data, spiffs,  0x290000,0x170000
```

### huge_app.csv (3MB app, sem OTA)

```
nvs,      data, nvs,     0x9000,  0x5000
otadata,  data, ota,     0xe000,  0x2000
app0,     app,  ota_0,   0x10000, 0x300000
spiffs,   data, spiffs,  0x310000,0x0F0000
```

O `partitions.bin` é gerado pelo PlatformIO a partir do CSV. O endereço `0x8000` é fixo para todos os chips.
