"""Entry point para executar a aplicação via `python -m esp32_flasher`."""

from esp32_flasher.gui import ESP32FlasherApp


def main():
    """Inicializa e executa a aplicação GUI."""
    app = ESP32FlasherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
