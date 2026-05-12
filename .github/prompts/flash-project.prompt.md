---
description: "Implementa o projeto ESP32 Flasher GUI completo ou uma fase específica. Gera todos os arquivos Python (flasher, GUI, serial monitor), requirements.txt e build.spec seguindo o plano do projeto."
agent: "Esp32-Flash-Builder"
argument-hint: "Fase a implementar (ex: 'todas', 'Fase 1', 'Fase 2', 'gui.py') ou deixe vazio para todas"
---

Implemente o ESP32 Flasher GUI seguindo o [plano do projeto](./plan-esp32Flasher.prompt.md).

## Instrução

Leia o plano completo e implemente a(s) fase(s) solicitada(s) pelo usuário. Se nenhuma fase específica for indicada, implemente **todas as fases na ordem** (1 → 2 → 3 → 3.5 → 4).

### Referências obrigatórias — ler ANTES de codar:

- [Convenções do projeto](../.github/copilot-instructions.md)
- [Plano completo](./plan-esp32Flasher.prompt.md)
- [Skill ESP32 Flash Expert](../.github/skills/esp32-flash-expert/SKILL.md)

### Checklist por fase:

**Fase 1 — Estrutura**

- [ ] `esp32_flasher/__init__.py`
- [ ] `esp32_flasher/__main__.py`
- [ ] `requirements.txt`

**Fase 2 — Flash**

- [ ] `esp32_flasher/flasher.py` — classe `ESP32Flasher`, subprocess, detecção de portas

**Fase 3 — GUI**

- [ ] `esp32_flasher/gui.py` — CustomTkinter, layout completo, threading, persistência JSON

**Fase 3.5 — Serial Monitor**

- [ ] `esp32_flasher/serial_monitor.py` — pyserial em thread, desconexão USB

**Fase 4 — Build**

- [ ] `build.spec` — PyInstaller onefile, hidden imports

### Após cada arquivo criado:

1. Validar sintaxe: `python -m py_compile <arquivo>`
2. Marcar como concluído no todo list
3. Informar o que foi criado e o próximo passo
