import requests
from requests.exceptions import RequestException
from json import JSONDecodeError

CURRENT_VERSION = "0.2.1-beta"

# ✅ URL corrigida (sem /refs/heads/)
VERSION_URL = "https://raw.githubusercontent.com/Coprela/Version-tracker/main/CompareSet_latest_version.json"

DEBUG = True


def fetch_latest_version(url: str) -> str:
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        try:
            data = response.json()
        except JSONDecodeError as e:
            if DEBUG:
                print(f"[ERRO] JSON inválido: {e}")
                print("[DEBUG] Conteúdo bruto recebido:")
                print(response.text)
            return ""

        latest = data.get("version")
        if isinstance(latest, str):
            return latest
        else:
            if DEBUG:
                print("[ERRO] Campo 'version' ausente ou não é string.")
    except RequestException as e:
        if DEBUG:
            print(f"[ERRO] Falha na requisição HTTP: {e}")
    except Exception as e:
        if DEBUG:
            print(f"[ERRO] Erro inesperado: {e}")
    return ""


def check_for_update():
    latest = fetch_latest_version(VERSION_URL)
    if latest:
        if latest != CURRENT_VERSION:
            print(f"Nova versão disponível: {latest}")
        else:
            print("Você já está usando a versão mais recente.")
    else:
        print("[ALERTA] Não foi possível obter a versão mais recente.")


if __name__ == "__main__":
    check_for_update()
