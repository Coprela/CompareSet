import argparse
from comparador import comparar_pdfs
from pdf_marker import gerar_pdf_com_destaques


def main(argv=None):
    """Command-line interface for CompareSet."""
    parser = argparse.ArgumentParser(
        description="Compare two PDF revisions and generate a highlighted PDF"
    )
    parser.add_argument("old_pdf", help="path to the older PDF revision")
    parser.add_argument("new_pdf", help="path to the newer PDF revision")
    parser.add_argument(
        "output_pdf",
        help="path where the comparison PDF will be written",
    )

    args = parser.parse_args(argv)

    data = comparar_pdfs(args.old_pdf, args.new_pdf)
    gerar_pdf_com_destaques(
        args.old_pdf,
        args.new_pdf,
        data["removidos"],
        data["adicionados"],
        args.output_pdf,
    )


if __name__ == "__main__":
    main()
