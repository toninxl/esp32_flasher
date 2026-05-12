---
description: "Use when configuring PyInstaller build, creating executables, or packaging the ESP32 Flasher GUI for distribution. Covers spec file, multi-architecture builds, and hidden imports."
applyTo: ["build.spec", "build.py"]
---
# PyInstaller Build — Padrões

## Spec File Essencial

```python
# build.spec
a = Analysis(
    ['esp32_flasher/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'esptool',
        'esptool.__init__',
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'customtkinter',
    ],
    # ...
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name='ESP32_Flasher',
    console=False,      # GUI — sem janela de console
    onefile=True,        # Executável único
)
```

## Hidden Imports

CustomTkinter e esptool têm imports dinâmicos que o PyInstaller não detecta:
- `customtkinter` — incluir o pacote inteiro como data
- `esptool` — incluir submodules (`esptool.targets`, `esptool.loader`, etc.)
- `serial.tools.list_ports` — detecção de portas

## Builds Multi-Arquitetura

| Build | Python | Executável | Compatibilidade |
|-------|--------|------------|----------------|
| x86 | Python 32-bit | `esp32_flasher_win32.exe` | Windows 32/64-bit |
| x64 | Python 64-bit | `esp32_flasher_win64.exe` | Windows 64-bit |

Alternativa simples: gerar apenas x86 (roda em ambas).

## Comandos

```bash
# Build padrão
pyinstaller build.spec

# Build com limpeza
pyinstaller --clean build.spec

# Testar executável
dist/ESP32_Flasher.exe
```

## Dicas

- Usar `console=False` para apps GUI (sem terminal)
- Testar em máquina sem Python para validar empacotamento
- Verificar que driver serial (CP210x, CH340) é requisito do USUÁRIO, não do executável
