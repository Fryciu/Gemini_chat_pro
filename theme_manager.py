import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt

# Definicje palet kolorów dla trybu jasnego i ciemnego
LIGHT_THEME_COLORS = {
    "bg": "#F0F0F0",  # Główne tło okna
    "fg": "#333333",  # Kolor tekstu
    "input_bg": "white", # Tło pól tekstowych
    "input_fg": "black", # Tekst w polach tekstowych
    "chat_bg": "white",  # Tło obszaru czatu
    "chat_fg": "black",  # Tekst w obszarze czatu
    "button_bg": "#E0E0E0", # Tło przycisków (dla Listbox i Text)
    "button_fg": "black",  # Tekst przycisków
    "border_color": "#CCCCCC", # Kolor ramki/granicy
    "highlight_color": "#A6D5FA", # Kolor zaznaczenia (np. w listboxach)
    "selected_bg": "#C0E0FF", # Tło zaznaczonego elementu
    "selected_fg": "black",   # Tekst zaznaczonego elementu
    # Kolory dla tagów w scrolledtext
    "user_prefix_fg": "#0066cc",
    "user_text_fg": "black",
    "bot_prefix_fg": "#009933",
    "bot_text_fg": "black",
    "error_fg": "#cc0000",
}

DARK_THEME_COLORS = {
    "bg": "#2B2B2B",  # Główne tło okna
    "fg": "#E0E0E0",  # Kolor tekstu
    "input_bg": "#3C3C3C", # Tło pól tekstowych
    "input_fg": "white", # Tekst w polach tekstowych
    "chat_bg": "#212121",  # Tło obszaru czatu
    "chat_fg": "#E0E0E0",  # Tekst w obszarze czatu
    "button_bg": "#4F4F4F", # Tło przycisków (dla Listbox i Text)
    "button_fg": "white",  # Tekst przycisków
    "border_color": "#555555", # Kolor ramki/granicy
    "highlight_color": "#5F7A9B", # Kolor zaznaczenia (np. w listboxach)
    "selected_bg": "#4A6E8A", # Tło zaznaczonego elementu
    "selected_fg": "white",   # Tekst zaznaczonego elementu
    # Kolory dla tagów w scrolledtext
    "user_prefix_fg": "#78A9FF", # Jaśniejszy niebieski
    "user_text_fg": "#E0E0E0",   # Biały/jasnoszary
    "bot_prefix_fg": "#7FC97F",  # Jaśniejsza zieleń
    "bot_text_fg": "#E0E0E0",    # Biały/jasnoszary
    "error_fg": "#FF6B6B",      # Jaśniejsza czerwień
}

def apply_theme_colors(root_window, widgets_to_style, theme_name):
    """
    Stosuje wybrane kolory motywu do wszystkich podanych widżetów.
    :param root_window: Główne okno Tkinter.
    :param widgets_to_style: Słownik zawierający referencje do widżetów aplikacji.
                             Klucze to nazwy widżetów, wartości to obiekty widżetów.
    :param theme_name: 'light' lub 'dark'.
    """
    colors = DARK_THEME_COLORS if theme_name == "dark" else LIGHT_THEME_COLORS
    style = ttk.Style()

    # Konfiguracja głównego okna
    root_window.configure(bg=colors["bg"])

    # Konfiguracja stylów dla widżetów ttk
    style.theme_use('default') # Resetuj do domyślnego, aby móc nadpisać style
    
    style.configure(".", background=colors["bg"], foreground=colors["fg"]) # Domyślny styl dla wszystkich widżetów ttk
    style.configure("TFrame", background=colors["bg"])
    style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
    style.configure("TButton", background=colors["button_bg"], foreground=colors["button_fg"],
                    bordercolor=colors["border_color"], lightcolor=colors["button_bg"], darkcolor=colors["button_bg"])
    style.map("TButton",
              background=[('active', colors["highlight_color"]), ('!disabled', colors["button_bg"])],
              foreground=[('active', colors["button_fg"]), ('!disabled', colors["button_fg"])])
    
    style.configure("TLabelframe", background=colors["bg"], foreground=colors["fg"],
                    bordercolor=colors["border_color"])
    style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["fg"])

    # === ZMIANA TUTAJ: Konfiguracja TEntry dla ttk.Entry ===
    style.configure("TEntry", 
                    fieldbackground=colors["input_bg"], 
                    foreground=colors["input_fg"], 
                    insertbackground=colors["input_fg"],
                    bordercolor=colors["border_color"]) # Dodano bordercolor dla spójności
    style.map("TEntry",
              fieldbackground=[('readonly', colors["input_bg"]), ('!disabled', colors["input_bg"])],
              foreground=[('readonly', colors["input_fg"]), ('!disabled', colors["input_fg"])])


    # Konfiguracja widżetów tk (nie-ttk) i scrolledtext (specjalne przypadki)
    # ScrolledText (chat_display)
    widgets_to_style["chat_display"].configure(bg=colors["chat_bg"], fg=colors["chat_fg"], insertbackground=colors["chat_fg"])
    
    # Konfiguracja tagów w scrolledtext (chat_display)
    widgets_to_style["chat_display"].tag_config('user_prefix', foreground=colors['user_prefix_fg'])
    widgets_to_style["chat_display"].tag_config('user_text', foreground=colors['user_text_fg'])
    widgets_to_style["chat_display"].tag_config('bot_prefix', foreground=colors['bot_prefix_fg'])
    widgets_to_style["chat_display"].tag_config('bot_text', foreground=colors['bot_text_fg'])
    widgets_to_style["chat_display"].tag_config('error', foreground=colors['error_fg'])

    # Tk.Listbox
    widgets_to_style["conversation_listbox"].configure(
        bg=colors["input_bg"], fg=colors["input_fg"],
        selectbackground=colors["selected_bg"], selectforeground=colors["selected_fg"],
        highlightbackground=colors["border_color"], highlightcolor=colors["highlight_color"]
    )
    widgets_to_style["preprompt_listbox"].configure(
        bg=colors["input_bg"], fg=colors["input_fg"],
        selectbackground=colors["selected_bg"], selectforeground=colors["selected_fg"],
        highlightbackground=colors["border_color"], highlightcolor=colors["highlight_color"]
    )

    # Konfiguracja matplotlib dla dark mode
    if theme_name == "dark":
        plt.rcParams.update({
            "figure.facecolor": colors["bg"],
            "axes.facecolor": colors["chat_bg"],
            "axes.edgecolor": colors["border_color"],
            "text.color": colors["fg"],
            "axes.labelcolor": colors["fg"],
            "xtick.color": colors["fg"],
            "ytick.color": colors["fg"],
            "grid.color": colors["border_color"],
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "savefig.facecolor": colors["bg"], # Kolor tła zapisanego obrazu
            "lines.color": colors["fg"], # Kolor linii na wykresach
            "patch.edgecolor": colors["fg"] # Kolor krawędzi łatek (np. słupków w histogramach)
        })
    else: # Resetuj do domyślnych dla trybu jasnego lub do preferowanych jasnych
        plt.rcParams.update(plt.rcParamsDefault) # Resetuj do domyślnych matplotlib
        # Możesz ustawić konkretne jasne kolory, jeśli domyślne nie są idealne
        plt.rcParams.update({
            "figure.facecolor": LIGHT_THEME_COLORS["bg"],
            "axes.facecolor": LIGHT_THEME_COLORS["chat_bg"],
            "axes.edgecolor": LIGHT_THEME_COLORS["border_color"],
            "text.color": LIGHT_THEME_COLORS["fg"],
            "axes.labelcolor": LIGHT_THEME_COLORS["fg"],
            "xtick.color": LIGHT_THEME_COLORS["fg"],
            "ytick.color": LIGHT_THEME_COLORS["fg"],
            "grid.color": LIGHT_THEME_COLORS["border_color"],
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "savefig.facecolor": LIGHT_THEME_COLORS["bg"],
            "lines.color": LIGHT_THEME_COLORS["fg"],
            "patch.edgecolor": LIGHT_THEME_COLORS["fg"]
        })

