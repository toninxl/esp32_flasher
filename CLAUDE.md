# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Desktop GUI application (Python + CustomTkinter) that wraps `esptool.py` to flash firmware onto ESP32 devices. Designed for PlatformIO/Arduino-generated binaries. Supports ESP32, ESP32-S2, ESP32-S3, and ESP32-C3.

## Commands

```bash
pip install -r requirements.txt    # Install dependencies
python -m esp32_flasher             # Run the application
pip install pyinstaller && pyinstaller build.spec  # Build standalone .exe → dist/ESP32_Flasher.exe
```

There are no tests or linting configured in this project.

## Architecture

Three modules orchestrated by `gui.py`:

- **gui.py** — Main window (`ESP32FlasherApp` extends `CTk`). Orchestrates everything: calls flasher for flashing, serial_monitor for port reading. All blocking work runs in daemon threads; GUI updates go through `self.after(0, callback)`.
- **flasher.py** — `ESP32Flasher` wraps esptool. Two execution modes: **subprocess** (`subprocess.Popen` with line-by-line stdout capture) in development, **in-process** (`esptool.main()` with `redirect_stdout`) when frozen by PyInstaller (avoids bootloader re-entrancy).
- **serial_monitor.py** — `SerialMonitor` reads serial data in a background daemon thread, delivers lines to GUI via callback. Must be stopped before any flash operation to release the port.

Entry point: `__main__.py` → `ESP32FlasherApp().mainloop()`.

## Key Conventions

- **Language**: Python 3.8+ compatible. Docstrings and comments in Portuguese. Identifiers in English (snake_case for functions/vars, PascalCase for classes).
- **Threading**: Never block main thread. All I/O in daemon threads. Never access widgets from secondary threads — use `self.after()`.
- **Log area**: Single `CTkTextbox` shared by esptool output and serial monitor (continuous stream, auto-scroll).
- **Config persistence**: `~/.esp32_flasher/config.json` stores port, chip, baud rates, file paths, checkbox states.

## Chip Flash Address Map

| Chip | Bootloader | Partitions | boot_app0 | Firmware |
|------|-----------|------------|-----------|----------|
| ESP32 | 0x1000 | 0x8000 | 0xe000 | 0x10000 |
| ESP32-S2 | 0x1000 | 0x8000 | 0xe000 | 0x10000 |
| ESP32-S3 | 0x0 | 0x8000 | 0xe000 | 0x10000 |
| ESP32-C3 | 0x0 | 0x8000 | 0xe000 | 0x10000 |

## esptool Default Parameters

`--before default_reset --after hard_reset --flash_size detect --flash_mode dio -z --baud 921600`

Chip argument mapping: `ESP32→esp32`, `ESP32-S2→esp32s2`, `ESP32-S3→esp32s3`, `ESP32-C3→esp32c3` (lowercase, no hyphen).

## PyInstaller Gotcha

When frozen (`getattr(sys, 'frozen', False)` is true), esptool must be called in-process via `esptool.main(args)` instead of subprocess — subprocess would re-invoke the bundled exe's bootloader. The flasher module handles this automatically but any new esptool invocation paths must respect this dual mode.

## Dependencies

- **esptool** ≥4.0 — firmware flashing
- **pyserial** — serial communication
- **customtkinter** ≥5.0 — dark-mode GUI toolkit
- **tkinterdnd2** — optional drag-and-drop support for .bin files
