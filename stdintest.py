import sys
import time

# Cross-platform character input function
if sys.platform == "win32":
    import msvcrt

    def get_char():
        if msvcrt.kbhit():
            return msvcrt.getwch()  # getwch returns Unicode character
        return None

    def setup_raw_mode():
        # No setup required on Windows
        return None

else:
    import tty
    import termios
    import select

    def get_char():
        fd = sys.stdin.fileno()
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None

    class RawMode:
        def __enter__(self):
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setraw(self.fd)

        def __exit__(self, exc_type, exc_val, exc_tb):
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def setup_raw_mode():
        return RawMode()


def run_loop():
    print("Type something (Ctrl+C to exit):")
    while True:
        ch = get_char()
        if ch:
            print(f"You typed: {repr(ch)}")
        time.sleep(0.1)


def main():
    raw_mode = setup_raw_mode()
    if raw_mode:
        with raw_mode:
            run_loop()
    else:
        run_loop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting.")
