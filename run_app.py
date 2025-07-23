from compareset.ui.main_window import main
from dotenv import load_dotenv


def _load_env() -> None:
    """Load configuration from a .env file if present."""
    try:
        load_dotenv()
    except Exception:
        # Failing to load the file should not prevent startup
        pass


if __name__ == "__main__":
    _load_env()
    main()
