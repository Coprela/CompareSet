# CompareSET

Aplicação em Python para comparar revisões de arquivos PDF utilizando uma DLL nativa. O programa destaca as diferenças encontradas em um novo PDF gerado após a análise.

## Instalação

1. Certifique-se de ter o Python instalado.
2. Instale as dependências executando:

```bash
pip install -r requirements.txt
```

## Como executar

Após instalar as dependências, inicie a interface com:

```bash
python app.py
```

A DLL `CompareSet.Engine.dll` deve estar localizada na mesma pasta do `app.py` para que o aplicativo funcione corretamente.

## Gerar executável (opcional)

É possível criar um executável utilizando o [PyInstaller](https://pyinstaller.org/). Após instalar o PyInstaller (`pip install pyinstaller`), execute o seguinte comando a partir do diretório do projeto:

```bash
pyinstaller --onefile --noconsole app.py
```

O arquivo gerado ficará disponível na pasta `dist`.
