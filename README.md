# CompareSet Viewer (PCF)

CompareSet Viewer é um controle PowerApps Component Framework que compara duas versões de um PDF técnico, destaca inclusões e remoções e gera um PDF final com as diferenças.

## Principais recursos

- Upload de dois PDFs (antigo e novo) diretamente no navegador.
- Processamento 100% client-side utilizando `pdfjs-dist`, `pdf-lib` e `upng-js`.
- Renderização em *Web Worker* com `OffscreenCanvas` para preservar a responsividade.
- Overlay vermelho para remoções e verde para adições.
- Exportação do PDF final em Base64 e download direto.

## Scripts

```bash
npm install
npm start -- --https
npm run build
```

O comando `npm run build` gera o pacote importável pelo Power Apps em `out/CompareSetViewer/CompareSetViewer_1_0_0.zip`.
