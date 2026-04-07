# Plano: ESP32 Flasher GUI

## TL;DR

Criar uma aplicação GUI desktop em Python que encapsula o `esptool.py` para gravar firmware em dispositivos ESP32 de forma simplificada. O diferencial em relação ao Flash Download Tool da Espressif: reset automático via RTS pin, detecção automática de tamanho de flash, endereços pré-configurados, e opção de limpar a flash. Será distribuído como executável (.exe) via PyInstaller.

## Decisões

- **Não criar do zero**: usar `esptool` como biblioteca Python — é o mesmo motor usado pelo PlatformIO e Flash Download Tool
- **GUI com CustomTkinter**: visual moderno (dark mode, cantos arredondados) sobre Tkinter, executável leve (~20MB)
- **4 arquivos**: bootloader.bin (0x1000), partitions.bin (0x8000), boot_app0.bin (0xe000, opcional), firmware.bin (0x10000)
- **Endereços padrão pré-configurados** com opção de editar manualmente
- **Múltiplos chips**: ESP32, ESP32-S2, ESP32-S3, ESP32-C3 (dropdown de seleção)
- **Reset via RTS**: usar `--after hard_reset` do esptool (flag `--after hard-reset`)
- **Detecção de tamanho**: usar `--flash-size detect` do esptool

## Steps

### Fase 1: Estrutura do Projeto

1. Criar estrutura de diretórios:
   - `esp32_flasher/` — pacote principal
   - `esp32_flasher/gui.py` — interface gráfica CustomTkinter
   - `esp32_flasher/flasher.py` — lógica de flash (wrapper do esptool)
   - `esp32_flasher/__main__.py` — entry point
   - `requirements.txt` — dependências (esptool, pyserial, customtkinter)
   - `build.spec` ou `build.py` — configuração PyInstaller

2. Criar `requirements.txt` com:
   - `esptool>=4.0`
   - `pyserial`
   - `customtkinter>=5.0`

### Fase 2: Lógica de Flash (`flasher.py`)

3. Implementar classe `ESP32Flasher` com métodos:
   - `list_serial_ports()` — detectar portas seriais disponíveis (usando `esptool.get_port_list()` ou `serial.tools.list_ports`)
   - `flash(port, chip, baud, files_with_addresses, erase_before, flash_mode, flash_freq)` — executar gravação
   - `erase_flash(port, chip)` — limpar flash completa
   - Usar `esptool.main()` ou invocar `esptool` como subprocesso com os argumentos corretos

4. Parâmetros de flash:
   - `--chip`: selecionável (esp32, esp32s2, esp32s3, esp32c3)
   - `--before default_reset` — reset para entrar no bootloader
   - `--after hard_reset` — reset via RTS após gravação
   - `--flash-size detect` — detecção automática
   - `--flash-mode dio` — modo padrão
   - `-z` — compressão durante upload
   - Endereços: configuráveis com valores padrão

5. Capturar output do esptool e redirecionar para log na GUI (stdout/stderr)

### Fase 3: Interface Gráfica (`gui.py`)

6. Layout da janela principal:
   - **Seção Conexão**: dropdown porta serial (com botão refresh), dropdown chip ESP32, campo baud rate flash (default 921600)
   - **Seção Arquivos**: 4 linhas, cada uma com:
     - Campo de endereço (pré-preenchido: 0x1000, 0x8000, 0xe000, 0x10000)
     - Campo de caminho do arquivo com botão "Selecionar..."
     - boot_app0.bin marcado como opcional
   - **Seção Opções**: checkbox "Limpar flash antes de gravar", checkbox "Abrir monitor serial após gravar", campo baud rate do monitor (default 115200)
   - **Botões**: "Gravar Firmware", "Limpar Flash", "Atualizar Portas", "Monitor Serial" (toggle on/off manual)
   - **Área de Log / Monitor Serial**: text area ÚNICA com scroll — exibe output do esptool durante gravação e transita automaticamente para serial monitor após "Hard resetting via RTS pin..." (fluxo contínuo idêntico ao Upload and Monitor do PlatformIO)
   - **Barra de Status**: status atual (Pronto / Gravando... / Monitor Serial / Erro)

7. Funcionalidades da GUI:
   - Gravar: validar que arquivos obrigatórios foram selecionados, executar flash em thread separada (não travar GUI)
   - Log em tempo real: redirecionar stdout do esptool para text widget
   - **Serial Monitor pós-flash**: se checkbox ativa, ao concluir gravação com sucesso, abrir automaticamente a porta serial (pyserial) e exibir dados recebidos na mesma área de log — fluxo contínuo sem interrupção
   - **Serial Monitor standalone**: botão "Monitor Serial" para abrir/fechar monitor independentemente da gravação
   - Fechar monitor serial automaticamente antes de iniciar nova gravação (liberar a porta)
   - Tratar desconexão USB com mensagem amigável no log
   - Persistir últimas configurações (porta, caminhos, baud monitor) em arquivo JSON local

### Fase 3.5: Serial Monitor (`serial_monitor.py`)

7.5. Implementar classe `SerialMonitor`:
   - Abrir porta serial com pyserial no baud rate configurado (default 115200)
   - Ler dados em thread separada, decodificar UTF-8, enviar linhas para callback (text widget da GUI)
   - Métodos: `start(port, baud)`, `stop()`, `is_running`
   - Fechar conexão serial ao parar — liberar porta para próxima gravação
   - Tratar exceção de porta desconectada (USB removido) com mensagem no log

### Fase 4: Entry Point e Empacotamento

8. Criar `__main__.py` que inicializa a GUI

9. Configurar PyInstaller:
   - Spec file para gerar executável único (.exe Windows)
   - Incluir esptool como dependência embutida
   - Adicionar ícone do projeto (opcional)
   - **Gerar builds separados para Windows 32-bit (x86) e 64-bit (x64)** — garantir compatibilidade com máquinas antigas
   - Instruções no README para build de cada arquitetura

### Fase 5: README e Documentação

10. Atualizar README.md com:
    - Descrição do projeto
    - Screenshot da GUI
    - Instruções de uso
    - Instruções de build do executável
    - Requisitos

## Arquivos a criar/modificar

- `esp32_flasher/__init__.py` — pacote
- `esp32_flasher/__main__.py` — entry point
- `esp32_flasher/gui.py` — interface CustomTkinter (~350 linhas)
- `esp32_flasher/flasher.py` — lógica de gravação (~100 linhas)
- `esp32_flasher/serial_monitor.py` — monitor serial (~60 linhas)
- `requirements.txt` — dependências
- `README.md` — documentação (já existe, atualizar)
- `build.spec` — config PyInstaller

## Verificação

1. Testar detecção de portas seriais — executar e verificar que lista as portas corretamente
2. Testar GUI — abrir a aplicação, verificar layout, botões, seleção de arquivos
3. Testar flash — conectar ESP32, selecionar arquivos reais, gravar e verificar mensagem "Hard resetting via RTS pin..."
4. Testar erase — usar opção de limpar flash
5. Testar serial monitor pós-flash — marcar checkbox, gravar, verificar que após "Hard resetting..." o output serial do ESP32 aparece na mesma janela de log
6. Testar serial monitor standalone — abrir/fechar monitor sem gravar
7. Testar re-flash com monitor ativo — verificar que o monitor fecha, grava, e reabre automaticamente
8. Testar build — `pyinstaller build.spec` e verificar que executável funciona sem Python instalado
9. Testar com diferentes chips (ESP32, ESP32-S3, etc.)

## Considerações

1. **CustomTkinter**: escolhido por oferecer visual moderno (dark mode, widgets arredondados) mantendo o executável leve (~20MB). É uma camada sobre Tkinter — mesma API, sem dependências pesadas. Superior ao Tkinter puro (visual datado) e ao PyQt (executável ~50-70MB).
2. **esptool como lib vs subprocesso**: Usar como subprocesso é mais simples para capturar output e evitar conflitos internos. Usar como lib dá mais controle. **Recomendação: subprocesso** para simplicidade e log fiel.
3. **Endereço do bootloader por chip**: ESP32/S2/S3 usam 0x1000, ESP32-C3/C5/P4 usam 0x0 ou 0x2000. O endereço padrão deve mudar automaticamente quando o chip é selecionado.
4. **Compatibilidade 32-bit e 64-bit**: O executável deve funcionar em Windows x86 (32-bit) e x64 (64-bit). Para isso:
   - Usar Python 32-bit para gerar o build x86 (roda em ambas as arquiteturas, mas é mais lento em 64-bit)
   - Usar Python 64-bit para gerar o build x64 (melhor performance em sistemas modernos)
   - Disponibilizar ambos os executáveis na release (`esp32_flasher_win32.exe` e `esp32_flasher_win64.exe`)
   - Todas as dependências (esptool, pyserial) são pure Python ou possuem wheels para ambas as arquiteturas
   - **Alternativa simples**: gerar apenas o build 32-bit, que roda nativamente em ambas as arquiteturas (com pequena perda de performance em 64-bit)
