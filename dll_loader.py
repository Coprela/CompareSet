import os
import ctypes
from ctypes import c_char_p

def carregar_dll():
    dll_path = os.path.join(os.path.dirname(__file__), "CompareSet.Engine.dll")
    if not os.path.exists(dll_path):
        raise FileNotFoundError(f"Não encontrei a DLL em: {dll_path}")

    dll = ctypes.CDLL(dll_path)
    dll.ComparePDFs.argtypes = [c_char_p, c_char_p, c_char_p]
    dll.ComparePDFs.restype = ctypes.c_int
    return dll

def chamar_comparador(dll, caminho_old, caminho_new, caminho_saida_json):
    return dll.ComparePDFs(
        caminho_old.encode("utf-8"),
        caminho_new.encode("utf-8"),
        caminho_saida_json.encode("utf-8")
    )
