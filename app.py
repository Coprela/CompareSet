import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import threading
import os
import json
from PIL import Image, ImageTk
from dll_loader import carregar_dll, chamar_comparador
from pdf_marker import gerar_pdf_com_destaques

class CompareSetApp:
    def __init__(self, master):
        self.master = master
        master.title("CompareSet - Comparador Vetorial de PDFs")
        master.configure(bg="white")
        master.resizable(False, False)
        self.centralizar_janela(master, 500, 350)

        self.pdf_antigo_path = ""
        self.pdf_novo_path = ""
        self.output_pdf = ""

        resources_dir = os.path.join(os.path.dirname(__file__), "Imagem")
        icon_path = os.path.join(resources_dir, "Icon janela.ico")
        try:
            master.iconbitmap(icon_path)
        except Exception as e:
            print(f"Erro ao carregar ícone: {e}")

        logo_path = os.path.join(resources_dir, "logo.png")
        try:
            logo = Image.open(logo_path)
            logo = logo.resize((200, 40), Image.LANCZOS)
            self.logo_image = ImageTk.PhotoImage(logo)
        except Exception as e:
            self.logo_image = None
            print(f"Erro ao carregar logo: {e}")

        self.outer_frame = tk.Frame(
            master,
            bg="white",
            highlightbackground="black",
            highlightcolor="black",
            highlightthickness=2
        )
        self.outer_frame.pack(expand=True, fill="both")

        if self.logo_image:
            self.label_logo = tk.Label(self.outer_frame, image=self.logo_image, bg="white")
            self.label_logo.pack(pady=(10, 5))

        self.label_title = tk.Label(
            self.outer_frame,
            text="CompareSet",
            bg="white",
            fg="#471F6F",
            font=("Arial", 14, "bold")
        )
        self.label_title.pack(pady=5)

        self.frame_selecao = tk.Frame(self.outer_frame, bg="white")
        self.frame_selecao.pack(pady=5)
        self.frame_selecao.grid_columnconfigure(0, weight=1)
        self.frame_selecao.grid_columnconfigure(1, weight=1)

        self.widget_width = 30
        self.widget_height = 1
        self.shared_font = ("Arial", 10)

        self.entry_antigo = tk.Entry(self.frame_selecao, width=self.widget_width, font=self.shared_font, justify='center')
        self.entry_antigo.grid(row=0, column=0, padx=5, pady=5, ipady=5)

        self.button_antigo = tk.Button(
            self.frame_selecao,
            text="Selecionar revisão antiga",
            command=self.selecionar_pdf_antigo,
            bg="#bd0003", fg="white",
            height=self.widget_height,
            width=self.widget_width,
            font=self.shared_font
        )
        self.button_antigo.grid(row=0, column=1, padx=5, pady=5)

        self.entry_novo = tk.Entry(self.frame_selecao, width=self.widget_width, font=self.shared_font, justify='center')
        self.entry_novo.grid(row=1, column=0, padx=5, pady=5, ipady=5)

        self.button_novo = tk.Button(
            self.frame_selecao,
            text="Selecionar nova revisão",
            command=self.selecionar_pdf_novo,
            bg="#009929", fg="white",
            height=self.widget_height,
            width=self.widget_width,
            font=self.shared_font
        )
        self.button_novo.grid(row=1, column=1, padx=5, pady=5)

        self.button_comparar = tk.Button(
            self.outer_frame,
            text="Comparar Revisões",
            command=self.iniciar_comparacao,
            bg="#471F6F", fg="white",
            height=self.widget_height,
            width=self.widget_width,
            font=self.shared_font
        )
        self.button_comparar.pack(pady=10)

        self.progress_bar = ttk.Progressbar(self.outer_frame, orient="horizontal", mode="determinate", length=400)
        self.progress_bar['maximum'] = 100
        self.progress_bar['value'] = 0

        self.label_credit = tk.Label(self.outer_frame, text="Desenvolvido por DOT-FUE", bg="white", font=("Arial", 8, "italic"), fg="gray")
        self.label_credit.pack(side="bottom", pady=(5, 5))

        self.label_version = tk.Label(self.outer_frame, text="Versão 2025.0.1 [Beta]", bg="white", font=("Arial", 8), fg="gray")
        self.label_version.place(relx=1.0, rely=1.0, anchor="se", x=-5, y=-5)

    def centralizar_janela(self, janela, largura, altura):
        janela.update_idletasks()
        x = (janela.winfo_screenwidth() // 2) - (largura // 2)
        y = (janela.winfo_screenheight() // 2) - (altura // 2)
        janela.geometry(f"{largura}x{altura}+{x}+{y}")

    def selecionar_pdf_antigo(self):
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if path:
            self.pdf_antigo_path = path
            self.entry_antigo.delete(0, tk.END)
            self.entry_antigo.insert(0, os.path.basename(path))

    def selecionar_pdf_novo(self):
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if path:
            self.pdf_novo_path = path
            self.entry_novo.delete(0, tk.END)
            self.entry_novo.insert(0, os.path.basename(path))

    def iniciar_comparacao(self):
        if not self.pdf_antigo_path or not self.pdf_novo_path:
            messagebox.showerror("Erro", "Selecione ambos os PDFs para comparação.")
            return

        output_pdf = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")], title="Salvar PDF de comparação")
        if not output_pdf:
            return

        self.output_pdf = output_pdf
        self.progress_bar['value'] = 0
        self.progress_bar.pack(pady=10)

        self.compare_thread = threading.Thread(target=self.executar_comparacao)
        self.compare_thread.start()
        self.master.after(100, self.update_progress)

    def executar_comparacao(self):
        try:
            dll = carregar_dll()
            status = chamar_comparador(dll, self.pdf_antigo_path, self.pdf_novo_path, "log.json")
            if status == 0:
                with open("log.json", "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    gerar_pdf_com_destaques(self.pdf_antigo_path, self.pdf_novo_path, dados, self.output_pdf)
            else:
                messagebox.showerror("Erro", "Erro ao executar a comparação via DLL.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro durante a comparação:\n{e}")

    def update_progress(self):
        if self.compare_thread.is_alive():
            if self.progress_bar['value'] < 95:
                self.progress_bar['value'] += 1
            self.master.after(100, self.update_progress)
        else:
            self.progress_bar['value'] = 100
            self.master.after(500, self.finalizar_comparacao)

    def finalizar_comparacao(self):
        self.progress_bar.pack_forget()
        messagebox.showinfo("Sucesso", f"PDF de comparação gerado com sucesso:\n{self.output_pdf}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CompareSetApp(root)
    root.mainloop()
