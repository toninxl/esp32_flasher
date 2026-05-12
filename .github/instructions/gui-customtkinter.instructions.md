---
description: "Use when creating or modifying the GUI interface with CustomTkinter. Covers layout, threading, log area, dark mode, widget patterns for the ESP32 Flasher."
applyTo: "**/gui.py"
---
# GUI CustomTkinter — Padrões

## Layout da Janela Principal

Organizar em seções verticais com `CTkFrame`:

1. **Conexão**: dropdown porta serial + botão refresh, dropdown chip, campo baud rate flash (921600)
2. **Arquivos**: 4 linhas — cada uma com campo endereço (pré-preenchido), campo caminho + botão "Selecionar..."
   - boot_app0.bin é opcional
3. **Opções**: checkbox "Limpar flash antes de gravar", checkbox "Abrir monitor serial após gravar", campo baud rate monitor (115200)
4. **Botões**: "Gravar Firmware", "Limpar Flash", "Atualizar Portas", "Monitor Serial" (toggle)
5. **Log / Monitor Serial**: `CTkTextbox` única com scroll — exibe output do esptool e transita para serial monitor
6. **Barra de Status**: label com status (Pronto / Gravando... / Monitor Serial / Erro)

## Threading

```python
# NUNCA bloquear a main thread — usar threading para todas as operações I/O
import threading

def start_flash(self):
    thread = threading.Thread(target=self._flash_worker, daemon=True)
    thread.start()

def _flash_worker(self):
    # Operação de flash — roda em thread separada
    # Atualizar GUI via self.after() ou queue
    self.after(0, lambda: self.log_append("Gravando..."))
```

## Log Area

- `CTkTextbox` com `state="disabled"` — habilitar apenas para inserir texto
- Sempre fazer scroll automático para o fim
- Mesma área para output do esptool e serial monitor (fluxo contínuo)

```python
def log_append(self, text: str):
    self.log_text.configure(state="normal")
    self.log_text.insert("end", text + "\n")
    self.log_text.see("end")
    self.log_text.configure(state="disabled")
```

## Endereços por Chip

Atualizar endereços automaticamente quando chip muda no dropdown:

```python
CHIP_ADDRESSES = {
    "ESP32":    {"bootloader": "0x1000", "partitions": "0x8000", "boot_app0": "0xe000", "firmware": "0x10000"},
    "ESP32-S2": {"bootloader": "0x1000", "partitions": "0x8000", "boot_app0": "0xe000", "firmware": "0x10000"},
    "ESP32-S3": {"bootloader": "0x0",    "partitions": "0x8000", "boot_app0": "0xe000", "firmware": "0x10000"},
    "ESP32-C3": {"bootloader": "0x0",    "partitions": "0x8000", "boot_app0": "0xe000", "firmware": "0x10000"},
}
```

## Persistência de Configurações

Salvar/carregar configurações em JSON local (`config.json`):
- Última porta serial usada
- Últimos caminhos de arquivos
- Baud rates (flash e monitor)
- Chip selecionado
- Estado dos checkboxes

## Transição Flash → Serial Monitor

Após "Hard resetting via RTS pin..." no log:
1. Detectar essa string no output do esptool
2. Se checkbox "Abrir monitor serial" ativa, iniciar `SerialMonitor` automaticamente
3. Continuar exibindo dados na mesma área de log — fluxo contínuo

## Anti-patterns

- NÃO usar `time.sleep()` na main thread
- NÃO acessar widgets diretamente de threads secundárias — usar `self.after()`
- NÃO criar janela modal para log — usar a área integrada
