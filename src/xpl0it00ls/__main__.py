import sys


def main():
    if "--gui" in sys.argv:
        from .app import main as gui_main
        gui_main()
    else:
        from .tui import main as tui_main
        tui_main()


if __name__ == "__main__":
    main()
