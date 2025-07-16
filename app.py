import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
from tkinter import ttk
import threading
import os
from PIL import Image, ImageTk
from pdf_marker import gerar_pdf_com_destaques
from comparador import comparar_pdfs


def arquivo_em_uso(caminho: str) -> bool:
    try:
        with open(caminho, "rb+"):
            return False
    except Exception:
        return True

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
        self.color_add = (0, 0.8, 0)
        self.color_remove = (1, 0, 0)
        self.opacity = 0.4

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

        # Opções de destaque
        self.frame_opcoes = tk.Frame(self.outer_frame, bg="white")
        self.frame_opcoes.pack(pady=5)

        self.button_cor_add = tk.Button(
            self.frame_opcoes,
            text="Cor de Adição",
            command=self.selecionar_cor_add,
            bg=self.rgb_to_hex(self.color_add),
            fg="white",
            width=15,
        )
        self.button_cor_add.grid(row=0, column=0, padx=5)

        self.button_cor_remove = tk.Button(
            self.frame_opcoes,
            text="Cor de Remoção",
            command=self.selecionar_cor_remove,
            bg=self.rgb_to_hex(self.color_remove),
            fg="white",
            width=15,
        )
        self.button_cor_remove.grid(row=0, column=1, padx=5)

        self.opacity_scale = tk.Scale(
            self.frame_opcoes,
            from_=0.1,
            to=1.0,
            resolution=0.05,
            orient="horizontal",
            label="Opacidade",
            length=150,
        )
        self.opacity_scale.set(self.opacity)
        self.opacity_scale.grid(row=0, column=2, padx=5)

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
        self.progress_value = 0

        self.label_credit = tk.Label(self.outer_frame, text="Desenvolvido por DOT-FUE", bg="white", font=("Arial", 8, "italic"), fg="gray")
        self.label_credit.pack(side="bottom", pady=(5, 5))

        self.label_version = tk.Label(self.outer_frame, text="Versão 2025.0.1 [Beta]", bg="white", font=("Arial", 8), fg="gray")
        self.label_version.place(relx=1.0, rely=1.0, anchor="se", x=-5, y=-5)

        self.button_license = tk.Button(
            self.outer_frame,
            text="Licença",
            command=self.mostrar_licenca,
            bg="white",
            fg="blue",
            font=("Arial", 8, "underline"),
            relief="flat",
            borderwidth=0,
            cursor="hand2"
        )
        self.button_license.place(relx=0.0, rely=1.0, anchor="sw", x=5, y=-5)

    def centralizar_janela(self, janela, largura, altura):
        janela.update_idletasks()
        x = (janela.winfo_screenwidth() // 2) - (largura // 2)
        y = (janela.winfo_screenheight() // 2) - (altura // 2)
        janela.geometry(f"{largura}x{altura}+{x}+{y}")

    def mostrar_licenca(self):
        """Exibe o texto da licença em uma janela de aviso."""
        license_path = os.path.join(os.path.dirname(__file__), "LICENSE")
        try:
            with open(license_path, "r", encoding="utf-8") as f:
                texto = f.read()
        except Exception:
            texto = "Arquivo de licença n\u00e3o encontrado."
        messagebox.showinfo("Licen\u00e7a", texto)

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

    def rgb_to_hex(self, color):
        r, g, b = color
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

    def selecionar_cor_add(self):
        cor = colorchooser.askcolor(color=self.rgb_to_hex(self.color_add))[0]
        if cor:
            self.color_add = tuple(v/255 for v in cor)
            self.button_cor_add.configure(bg=self.rgb_to_hex(self.color_add))

    def selecionar_cor_remove(self):
        cor = colorchooser.askcolor(color=self.rgb_to_hex(self.color_remove))[0]
        if cor:
            self.color_remove = tuple(v/255 for v in cor)
            self.button_cor_remove.configure(bg=self.rgb_to_hex(self.color_remove))

    def set_progress(self, value: float):
        """Store progress value for the UI thread to consume."""
        self.progress_value = value

    def iniciar_comparacao(self):
        if not self.pdf_antigo_path or not self.pdf_novo_path:
            messagebox.showerror("Erro", "Selecione ambos os PDFs para comparação.")
            return

        if arquivo_em_uso(self.pdf_antigo_path) or arquivo_em_uso(self.pdf_novo_path):
            messagebox.showwarning("Arquivo em uso", "O PDF está aberto em outro programa. Feche antes de continuar.")
            return

        output_pdf = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")], title="Salvar PDF de comparação")
        if not output_pdf:
            return

        if output_pdf in (self.pdf_antigo_path, self.pdf_novo_path):
            messagebox.showerror("Erro", "Escolha um nome de arquivo diferente do PDF de entrada.")
            return

        self.output_pdf = output_pdf
        self.opacity = self.opacity_scale.get()
        self.progress_value = 0
        self.progress_bar['value'] = 0
        self.progress_bar.pack(pady=10)

        self.compare_thread = threading.Thread(target=self.executar_comparacao)
        self.compare_thread.start()
        self.button_comparar.config(state=tk.DISABLED)
        self.master.after(100, self.update_progress)

    def executar_comparacao(self):
        try:
            dados = comparar_pdfs(
                self.pdf_antigo_path,
                self.pdf_novo_path,
                progress_callback=lambda p: self.set_progress(p / 2)
            )
            gerar_pdf_com_destaques(
                self.pdf_antigo_path,
                self.pdf_novo_path,
                dados["removidos"],
                dados["adicionados"],
                self.output_pdf,
                color_add=self.color_add,
                color_remove=self.color_remove,
                opacity=self.opacity,
                progress_callback=lambda p: self.set_progress(50 + p / 2),
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Erro durante a comparação:\n{e}")

    def update_progress(self):
        if self.compare_thread.is_alive():
            self.progress_bar['value'] = self.progress_value
            self.master.after(100, self.update_progress)
        else:
            self.progress_bar['value'] = 100
            self.master.after(500, self.finalizar_comparacao)

    def finalizar_comparacao(self):
        self.progress_bar.pack_forget()
        self.button_comparar.config(state=tk.NORMAL)
        messagebox.showinfo("Sucesso", f"PDF de comparação gerado com sucesso:\n{self.output_pdf}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CompareSetApp(root)
    root.mainloop()
