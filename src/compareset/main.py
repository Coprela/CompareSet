def main():
    """Entry point fino do CompareSet."""
    try:
        from .frontend.main_window import run_app  # se existir
        return run_app()
    except Exception:
        print("CompareSet main loaded. Integrate GUI run logic here.")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
