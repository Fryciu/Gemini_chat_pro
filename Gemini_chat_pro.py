import os
import json
import tkinter as tk
from tkinter import (
    ttk, scrolledtext, messagebox, 
    filedialog, simpledialog
)
from datetime import datetime
from threading import Thread
import google.generativeai as genai
from google.api_core import retry
import matplotlib.pyplot as plt
import re
import io
from PIL import Image, ImageTk 
from pathlib import Path
import uuid 

# Importuj moduł do zarządzania motywem
import theme_manager 

class GeminiChatApp:
    def __init__(self, root):
        # Konfiguracja głównego okna
        self.root = root
        self.root.title("Gemini Chat Pro")
        self.root.geometry("1000x700")
        
        # Inicjalizacja ścieżek konfiguracyjnych
        self.init_paths()
        
        # Wczytanie konfiguracji aplikacji (w tym stanu dark mode)
        # To musi być PRZED setup_ui, ponieważ setup_ui może używać wartości z config
        self.init_config() 

        # Zmienne stanu
        self.conversation_history = []
        self.current_conversation_id = None 
        self.conversations_metadata = [] 
        self.rendered_images = [] 
        self.model = None 
        self.api_key = None 
        # Ustaw początkowy limit tokenów z config.json lub domyślnie 65536
        self.max_output_tokens_limit = tk.IntVar(value=self.config.get('max_output_tokens', 65536))

        # Inicjalizacja interfejsu (pasek statusu musi być przed init_gemini)
        self.setup_ui()
        
        # Konfiguracja Gemini API (po ustawieniu paska statusu)
        self.init_gemini()
        
        # Po załadowaniu UI i danych, upewnij się, że jest jakaś aktywna konwersacja
        self.load_conversation_list() 
        if not self.conversations_metadata:
            self.create_new_conversation(initial_load=True) 
        elif self.current_conversation_id is None or not any(c['id'] == self.current_conversation_id for c in self.conversations_metadata):
            self.current_conversation_id = self.conversations_metadata[0]['id']
            self.load_conversation_history(self.current_conversation_id)
            self.display_current_conversation_messages()
            self.update_conversations_listbox_selection()

        # Ustaw początkowy motyw po załadowaniu konfiguracji i stworzeniu widżetów
        # Zbieramy wszystkie widżety, które chcemy stylizować dynamicznie
        self.all_app_widgets = {
            "root": self.root, # Root window
            "main_frame": self.main_frame,
            "left_panel": self.left_panel,
            "right_panel": self.right_panel,
            "conv_frame": self.conv_frame,
            "preprompt_frame": self.preprompt_frame,
            "conversation_listbox": self.conversation_listbox,
            "preprompt_listbox": self.preprompt_listbox,
            "chat_display": self.chat_display,
            "user_input": self.user_input,
            "system_prompt": self.system_prompt,
            "status_bar": self.status_bar 
        }
        # POPRAWIONA LINIA: Przekazujemy self.root jako pierwszy argument
        theme_manager.apply_theme_colors(self.root, self.all_app_widgets, "dark" if self.dark_mode_enabled.get() else "light")


    def init_paths(self):
        """Inicjalizuje ścieżki do plików konfiguracyjnych"""
        self.app_data_dir = Path(__file__).parent
        os.makedirs(self.app_data_dir, exist_ok=True)
        
        self.preprompts_file = os.path.join(
            self.app_data_dir, 
            "preprompts.json"
        )
        self.conversations_dir = os.path.join(
            self.app_data_dir, 
            "conversations"
        )
        os.makedirs(self.conversations_dir, exist_ok=True)
        self.api_key_file = os.path.join(self.app_data_dir, "api_key.txt")
        self.config_file = os.path.join(self.app_data_dir, "config.json") # Plik konfiguracyjny

    def init_config(self):
        """Ładuje konfigurację aplikacji z pliku."""
        self.config = {}
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
        except Exception as e:
            messagebox.showwarning(
                "Ostrzeżenie",
                f"Nie można wczytać konfiguracji aplikacji:\n{str(e)}"
            )
        
        # Inicjalizacja zmiennej dla trybu ciemnego
        self.dark_mode_enabled = tk.BooleanVar(value=self.config.get('dark_mode', False))
        # trace_add("write", ...) zostanie dodane po utworzeniu self.status_var
        # Upewnij się, że max_output_tokens_limit jest również zapisywany
        
    def save_config(self, *args): # Dodajemy *args, bo trace_add przekazuje argumenty
        """Zapisuje konfigurację aplikacji do pliku."""
        try:
            self.config['dark_mode'] = self.dark_mode_enabled.get()
            self.config['max_output_tokens'] = self.max_output_tokens_limit.get() # Zapisz limit tokenów
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(
                    self.config, 
                    f, 
                    indent=2, 
                    ensure_ascii=False
                )
        except Exception as e:
            print(f"Błąd zapisu konfiguracji: {e}") # Do debugowania

    def init_gemini(self):
        """Konfiguruje połączenie z Gemini API i ładuje klucz API"""
        self.api_key = None 
        self.model = None 

        if os.path.exists(self.api_key_file):
            try:
                with open(self.api_key_file, 'r') as f:
                    self.api_key = f.read().strip()
                if self.api_key:
                    genai.configure(api_key=self.api_key) 
                    self.model = genai.GenerativeModel("gemini-1.5-flash") # Updated model to 1.5-flash
                    self.status_var.set("Połączono z Gemini API.")
                else:
                    self.status_var.set("Brak klucza API w pliku. Ustaw w menu Ustawienia.")
            except Exception as e:
                messagebox.showerror(
                    "Błąd inicjalizacji API", 
                    f"Nie można wczytać klucza API z pliku:\n{str(e)}"
                )
                self.status_var.set("Błąd ładowania klucza API z pliku.")
        else:
            self.status_var.set("Plik klucza API nie istnieje. Ustaw w menu Ustawienia.")
        
    def setup_ui(self):
        """Konfiguruje cały interfejs użytkownika"""
        self.style = ttk.Style() # Inicjalizacja stylu ttk
        self.setup_menu()
        self.setup_main_frames()
        self.setup_config_panel()
        self.setup_chat_panel()
        self.setup_status_bar() # Pasek statusu ustawiany jest tutaj

        # Dodaj trace_add po inicjalizacji self.status_var
        self.dark_mode_enabled.trace_add("write", self.save_config)
        self.max_output_tokens_limit.trace_add("write", self.save_config)
        
        # Ładowanie danych
        self.load_preprompts()


    def setup_menu(self):
        """Konfiguruje menu główne"""
        menubar = tk.Menu(self.root)
        
        # Menu Plik
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Nowa konwersacja", 
            command=self.create_new_conversation, 
            accelerator="Ctrl+N"
        )
        file_menu.add_command(
            label="Zapisz konwersację", 
            command=self.save_conversation, 
            accelerator="Ctrl+S"
        )
        file_menu.add_command(
            label="Zmień nazwę konwersacji",
            command=self.rename_current_conversation 
        )
        file_menu.add_command(
            label="Eksportuj jako...", 
            command=self.export_conversation
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Zakończ", 
            command=self.confirm_exit
        )
        menubar.add_cascade(label="Plik", menu=file_menu)
        
        # Menu Preprompty
        preprompts_menu = tk.Menu(menubar, tearoff=0)
        preprompts_menu.add_command(
            label="Zapisz obecny preprompt", 
            command=self.save_current_preprompt
        )
        preprompts_menu.add_command(
            label="Zarządzaj prepromptami", 
            command=self.show_preprompts_manager
        )
        menubar.add_cascade(label="Preprompty", menu=preprompts_menu)

        # Menu Ustawienia
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(
            label="Ustaw klucz API",
            command=self.set_api_key
        )
        settings_menu.add_command(
            label="Ustaw limit tokenów wyjściowych...",
            command=self.open_token_limit_settings 
        )
        settings_menu.add_checkbutton( # Opcja dla trybu ciemnego
            label="Tryb Ciemny",
            variable=self.dark_mode_enabled,
            command=self.toggle_dark_mode # Wywołaj funkcję przełączającą
        )
        menubar.add_cascade(label="Ustawienia", menu=settings_menu)
        
        self.root.config(menu=menubar)
        
        # Skróty klawiaturowe
        self.root.bind("<Control-n>", lambda e: self.create_new_conversation()) 
        self.root.bind("<Control-s>", lambda e: self.save_conversation())

    def setup_main_frames(self):
        """Konfiguruje główne obszary interfejsu"""
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.left_panel = ttk.Frame(self.main_frame, width=250)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.left_panel.pack_propagate(False) # Zapobiega kurczeniu się lewego panelu
        
        self.right_panel = ttk.Frame(self.main_frame)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def setup_config_panel(self):
        """Konfiguruje lewy panel ustawień"""
        self.conv_frame = ttk.LabelFrame( # Zapisz jako atrybut instancji
            self.left_panel, 
            text="Konwersacje",
            padding=10
        )
        self.conv_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.conversation_listbox = tk.Listbox(
            self.conv_frame, 
            height=10,
            selectmode=tk.SINGLE
        )
        self.conversation_listbox.pack(fill=tk.X)
        self.conversation_listbox.bind(
            "<<ListboxSelect>>", 
            self.on_conversation_select
        )
        
        conv_buttons_frame = ttk.Frame(self.conv_frame)
        conv_buttons_frame.pack(fill=tk.X, pady=(5,0))

        ttk.Button(
            conv_buttons_frame, 
            text="Nowa",
            command=self.create_new_conversation 
        ).pack(side=tk.LEFT, expand=True, padx=(0,2))
        ttk.Button(
            conv_buttons_frame,
            text="Zmień nazwę",
            command=self.rename_current_conversation 
        ).pack(side=tk.LEFT, expand=True, padx=(0,2))
        ttk.Button(
            conv_buttons_frame,
            text="Usuń",
            command=self.delete_selected_conversation
        ).pack(side=tk.LEFT, expand=True)
        
        self.preprompt_frame = ttk.LabelFrame( # Zapisz jako atrybut instancji
            self.left_panel, 
            text="Preprompty",
            padding=10
        )
        self.preprompt_frame.pack(fill=tk.BOTH, expand=True)
        
        self.preprompt_listbox = tk.Listbox(
            self.preprompt_frame, 
            height=10
        )
        self.preprompt_listbox.pack(fill=tk.BOTH, expand=True)
        self.preprompt_listbox.bind(
            "<<ListboxSelect>>", 
            self.on_preprompt_select
        )
        
        btn_frame = ttk.Frame(self.preprompt_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(
            btn_frame,
            text="Zastosuj",
            command=self.apply_selected_preprompt
        ).pack(side=tk.LEFT, expand=True)
        ttk.Button(
            btn_frame,
            text="Usuń",
            command=self.delete_selected_preprompt
        ).pack(side=tk.LEFT, expand=True)

    def setup_chat_panel(self):
        """Konfiguruje prawy panel czatu"""
        self.config_frame = ttk.Frame(self.right_panel) # Zapisz jako atrybut instancji
        self.config_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            self.config_frame, # Zmieniono na self.config_frame
            text="Prompt systemowy:"
        ).pack(side=tk.LEFT)
        
        self.system_prompt = ttk.Entry(
            self.config_frame, # Zmieniono na self.config_frame
            width=50
        )
        self.system_prompt.pack(
            side=tk.LEFT, 
            fill=tk.X, 
            expand=True, 
            padx=5
        )
        self.system_prompt.insert(
            0, 
            "Jesteś pomocnym asystentem. Odpowiadaj w języku polskim."
        )
        
        self.chat_display = scrolledtext.ScrolledText(
            self.right_panel,
            wrap=tk.WORD,
            font=('Arial', 11), 
            state='disabled'
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Konfiguracja tagów - kolory będą ustawiane przez apply_theme_colors
        self.chat_display.tag_config('user_prefix', font=('Arial', 11, 'bold'))
        self.chat_display.tag_config('user_text', font=('Arial', 11))
        self.chat_display.tag_config('bot_prefix', font=('Arial', 11, 'bold'))
        self.chat_display.tag_config('bot_text', font=('Arial', 11))
        self.chat_display.tag_config('error', font=('Arial', 11))
        
        input_frame = ttk.Frame(self.right_panel)
        input_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.user_input = ttk.Entry(
            input_frame,
            font=('Arial', 11)
        )
        self.user_input.pack(
            side=tk.LEFT, 
            fill=tk.X, 
            expand=True, 
            padx=(0, 5)
        )
        self.user_input.bind(
            "<Return>", 
            lambda e: self.send_message()
        )
        
        ttk.Button(
            input_frame,
            text="Wyślij",
            command=self.send_message
        ).pack(side=tk.RIGHT)

    def setup_status_bar(self):
        """Konfiguruje pasek statusu"""
        self.status_var = tk.StringVar()
        self.status_var.set("Gotowy")
        
        self.status_bar = ttk.Label( # Zapisz jako atrybut instancji
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_bar.pack(fill=tk.X)

    # === Metody zarządzania prepromptami ===
    def load_preprompts(self):
        """Wczytuje preprompty z pliku"""
        self.preprompts = {}
        try:
            if os.path.exists(self.preprompts_file):
                with open(self.preprompts_file, 'r', encoding='utf-8') as f:
                    self.preprompts = json.load(f)
        except Exception as e:
            messagebox.showwarning(
                "Ostrzeżenie",
                f"Nie można wczytać prepromptów:\n{str(e)}"
            )
        
        self.preprompt_listbox.delete(0, tk.END)
        for name in sorted(self.preprompts.keys()):
            self.preprompt_listbox.insert(tk.END, name)

    def save_preprompts(self):
        """Zapisuje preprompty do pliku"""
        try:
            with open(self.preprompts_file, 'w', encoding='utf-8') as f:
                json.dump(
                    self.preprompts, 
                    f, 
                    indent=2, 
                    ensure_ascii=False
                )
            return True
        except Exception as e:
            messagebox.showerror(
                "Błąd",
                f"Nie można zapisać prepromptów:\n{str(e)}"
            )
            return False

    def save_current_preprompt(self):
        """Zapisuje bieżący prompt jako nowy preprompt"""
        current_prompt = self.system_prompt.get().strip()
        if not current_prompt:
            messagebox.showwarning(
                "Puste pole",
                "Prompt systemowy jest pusty!"
            )
            return
            
        name = simpledialog.askstring(
            "Zapisz preprompt",
            "Podaj nazwę dla tego prepromptu:"
        )
        
        if name:
            if name in self.preprompts:
                if not messagebox.askyesno(
                    "Potwierdzenie",
                    f"Preprompt '{name}' już istnieje. Nadpisać?"
                ):
                    return
                    
            self.preprompts[name] = current_prompt
            if self.save_preprompts():
                self.load_preprompts()
                messagebox.showinfo(
                    "Sukces",
                    f"Zapisano preprompt '{name}'"
                )

    def on_preprompt_select(self, event):
        """Obsługuje wybór prepromptu z listy"""
        selection = self.preprompt_listbox.curselection()
        if selection:
            selected_name = self.preprompt_listbox.get(selection[0])
            selected_prompt = self.preprompts.get(selected_name, "")
            self.system_prompt.delete(0, tk.END)
            self.system_prompt.insert(0, selected_prompt)

    def apply_selected_preprompt(self):
        """Stosuje wybrany preprompt"""
        selection = self.preprompt_listbox.curselection()
        if selection:
            self.on_preprompt_select(None)

    def delete_selected_preprompt(self):
        """Usuwa wybrany preprompt"""
        selection = self.preprompt_listbox.curselection()
        if not selection:
            return
            
        selected_name = self.preprompt_listbox.get(selection[0])
        if messagebox.askyesno(
            "Potwierdzenie",
            f"Czy na pewno chcesz usunąć preprompt '{selected_name}'?"
        ):
            del self.preprompts[selected_name]
            if self.save_preprompts():
                self.load_preprompts()

    def show_preprompts_manager(self):
        """Pokazuje zaawansowane okno zarządzania prepromptami"""
        manager = tk.Toplevel(self.root)
        manager.title("Zarządzanie prepromptami")
        manager.geometry("600x400")
        
        # Zapisz widżety tego okna do stylizacji
        manager_widgets = {
            "root": manager, # Użyj Toplevel jako "root" dla tej funkcji
            "editor": scrolledtext.ScrolledText(
                manager,
                wrap=tk.WORD,
                font=('Arial', 11)
            )
        }
        manager_widgets["editor"].pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        manager_widgets["editor"].insert(tk.END, self.system_prompt.get())
        
        btn_frame = ttk.Frame(manager)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(
            btn_frame,
            text="Zapisz jako nowy",
            command=lambda: self.save_from_editor(
                manager_widgets["editor"],
                manager,
                new=True
            )
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            btn_frame,
            text="Aktualizuj obecny",
            command=lambda: self.save_from_editor(
                manager_widgets["editor"],
                manager,
                new=False
            )
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            btn_frame,
            text="Anuluj",
            command=manager.destroy
        ).pack(side=tk.RIGHT)

        # Zastosuj motyw do Toplevel
        theme_manager.apply_theme_colors(manager_widgets["root"], manager_widgets, 
                                         "dark" if self.dark_mode_enabled.get() else "light")


    def save_from_editor(self, editor, window, new=False):
        """Zapisuje prompt z edytora"""
        content = editor.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning(
                "Puste pole",
                "Prompt systemowy jest pusty!"
            )
            return
            
        if new:
            self.save_custom_preprompt(content, window)
        else:
            self.update_current_preprompt(content, window)

    def save_custom_preprompt(self, content, window):
        """Zapisuje nowy preprompt z edytora"""
        name = simpledialog.askstring(
            "Zapisz preprompt",
            "Podaj nazwę dla tego prepromptu:",
            parent=window
        )
        
        if name:
            self.preprompts[name] = content
            if self.save_preprompts():
                self.load_preprompts()
                window.destroy()
                messagebox.showinfo(
                    "Sukces",
                    f"Zapisano preprompt '{name}'"
                )

    def update_current_preprompt(self, content, window):
        """Aktualizuje obecny preprompt"""
        selection = self.preprompt_listbox.curselection()
        if not selection:
            messagebox.showwarning(
                "Brak wyboru",
                "Nie wybrano prepromptu do aktualizacji!"
            )
            return
            
        selected_name = self.preprompt_listbox.get(selection[0])
        self.preprompts[selected_name] = content
        if self.save_preprompts():
            self.load_preprompts()
            window.destroy()
            messagebox.showinfo(
                "Sukces",
                f"Zaktualizowano preprompt '{selected_name}'"
            )

    # === Metody zarządzania konwersacjami ===
    def load_conversation_list(self):
        """
        Wczytuje listę zapisanych konwersacji (ID i nazwy)
        na podstawie plików w katalogu conversations_dir.
        """
        self.conversations_metadata = []
        try:
            for filename in os.listdir(self.conversations_dir):
                if filename.endswith('.json'):
                    file_id = os.path.splitext(filename)[0]
                    filepath = os.path.join(self.conversations_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            conversation_name = data.get("name", file_id) 
                            self.conversations_metadata.append({"id": file_id, "name": conversation_name})
                    except json.JSONDecodeError as e:
                        print(f"Błąd odczytu pliku JSON: {filename} - {e}")
                        self.status_var.set(f"Błąd odczytu: {filename}")
                    except Exception as e:
                        print(f"Nieoczekiwany błąd podczas ładowania {filename}: {e}")
                        self.status_var.set(f"Błąd: {filename}")
        except Exception as e:
            messagebox.showwarning(
                "Ostrzeżenie",
                f"Nie można wczytać listy konwersacji:\n{str(e)}"
            )
        
        self.conversations_metadata.sort(key=lambda x: x['name'].lower())
        
        self.conversation_listbox.delete(0, tk.END)
        for conv_meta in self.conversations_metadata:
            self.conversation_listbox.insert(tk.END, conv_meta['name'])
        
        self.update_conversations_listbox_selection()

    def update_conversations_listbox_selection(self):
        """Zaznacza aktywną konwersację w Listboxie."""
        self.conversation_listbox.selection_clear(0, tk.END)
        if self.current_conversation_id:
            for i, conv_meta in enumerate(self.conversations_metadata):
                if conv_meta['id'] == self.current_conversation_id:
                    self.conversation_listbox.selection_set(i)
                    self.conversation_listbox.see(i) 
                    break

    def create_new_conversation(self, initial_load=False): 
        """
        Rozpoczyna nową konwersację.
        initial_load=True oznacza, że jest to wywołanie z __init__
        i nie pytamy o zapisanie starej konwersacji, jeśli jest pusta.
        """
        if self.conversation_history and not initial_load:
            if not messagebox.askyesno(
                "Potwierdzenie",
                "Czy na pewno chcesz rozpocząć nową konwersację?\n"
                "Niezapisane zmiany w obecnej konwersacji zostaną utracone."
            ):
                return
        
        new_conv_name = simpledialog.askstring(
            "Nowa konwersacja",
            "Podaj nazwę dla nowej konwersacji:",
            initialvalue="Nowa Konwersacja"
        )
        if not new_conv_name:
            if not initial_load: 
                return
            else: 
                new_conv_name = "Nowa Konwersacja"

        new_id = str(uuid.uuid4()) 

        filepath = os.path.join(self.conversations_dir, f"{new_id}.json")
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "id": new_id,
                    "name": new_conv_name,
                    "system_prompt": self.system_prompt.get(),
                    "history": [],
                    "created_at": datetime.now().isoformat(),
                    "last_modified": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się utworzyć nowej konwersacji: {e}")
            return
            
        self.conversation_history = []
        self.current_conversation_id = new_id
        self.chat_display.config(state='normal')
        self.chat_display.delete('1.0', tk.END)
        self.chat_display.config(state='disabled')
        self.status_var.set(f"Nowa konwersacja: '{new_conv_name}'")
        self.rendered_images = [] 
        
        self.load_conversation_list() 
        self.update_conversations_listbox_selection() 

    def save_conversation(self):
        """
        Zapisuje aktualnie aktywną konwersację do pliku JSON.
        Używa current_conversation_id do określenia nazwy pliku.
        Jeśli current_conversation_id jest None (nowa konwersacja przed pierwszym zapisem),
        prosi o nazwę i generuje UUID.
        """
        if not self.conversation_history and not self.current_conversation_id:
            messagebox.showwarning(
                "Pusta konwersacja",
                "Nie ma nic do zapisania! Utwórz najpierw wiadomości."
            )
            return False

        conversation_name = self.get_conversation_name_by_id(self.current_conversation_id) if self.current_conversation_id else None

        if not self.current_conversation_id:
            new_conv_name = simpledialog.askstring(
                "Zapisz konwersację",
                "Podaj nazwę dla tej konwersacji:",
                initialvalue=f"Konwersacja {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            if not new_conv_name:
                messagebox.showwarning("Anulowano", "Zapisanie konwersacji anulowane.")
                return False
            
            new_id = str(uuid.uuid4())
            self.current_conversation_id = new_id
            conversation_name = new_conv_name
            
            self.conversations_metadata.append({"id": new_id, "name": conversation_name})
            self.conversations_metadata.sort(key=lambda x: x['name'].lower()) 
            self.update_conversations_listbox_selection() 
        
        filename = f"{self.current_conversation_id}.json"
        filepath = os.path.join(self.conversations_dir, filename)
        
        try:
            created_at = self._get_creation_date_from_file(filepath)

            data = {
                "id": self.current_conversation_id,
                "name": conversation_name, 
                "system_prompt": self.system_prompt.get(),
                "history": self.conversation_history,
                "created_at": created_at,
                "last_modified": datetime.now().isoformat()
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.status_var.set(f"Konwersacja '{conversation_name}' zapisana.")
            self.load_conversation_list() 
            return True
            
        except Exception as e:
            messagebox.showerror(
                "Błąd",
                f"Nie można zapisać konwersacji:\n{str(e)}"
            )
            return False

    def _get_creation_date_from_file(self, filepath):
        """Pobiera datę 'created_at' z istniejącego pliku, jeśli istnieje."""
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("created_at", datetime.now().isoformat())
            except (json.JSONDecodeError, IOError):
                pass
        return datetime.now().isoformat()

    def load_selected_conversation(self):
        """Ładuje wybraną konwersację z Listboxa."""
        selection_index = self.conversation_listbox.curselection()
        if not selection_index:
            messagebox.showwarning("Wybór konwersacji", "Proszę wybrać konwersację z listy.")
            return

        index = selection_index[0]
        selected_name_from_listbox = self.conversation_listbox.get(index)
        
        selected_conv_id = None
        for conv_meta in self.conversations_metadata:
            if conv_meta['name'] == selected_name_from_listbox:
                selected_conv_id = conv_meta['id']
                break

        if selected_conv_id and self.current_conversation_id != selected_conv_id:
            if self.conversation_history and messagebox.askyesno(
                "Zapisz konwersację?",
                "Czy chcesz zapisać obecną konwersację przed załadowaniem innej?"
            ):
                self.save_conversation() 

            self.current_conversation_id = selected_conv_id
            self.load_conversation_history(self.current_conversation_id)
            self.display_current_conversation_messages()
            self.status_var.set(f"Załadowano konwersację: '{selected_name_from_listbox}'")
        elif not selected_conv_id:
            messagebox.showerror("Błąd", "Nie znaleziono ID dla wybranej konwersacji.")

    def load_conversation_history(self, conv_id):
        """Ładuje pełną historię i system_prompt dla danej konwersacji."""
        filepath = os.path.join(self.conversations_dir, f"{conv_id}.json")
        self.conversation_history = []
        self.system_prompt.delete(0, tk.END) 
        self.system_prompt.insert(0, "Jesteś pomocnym asystentem. Odpowiadaj w języku polskim.") 

        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.conversation_history = data.get("history", [])
                    self.system_prompt.delete(0, tk.END)
                    self.system_prompt.insert(0, data.get("system_prompt", "Jesteś pomocnym asystentem. Odpowiadaj w języku polskim."))
                    self.status_var.set(f"Wczytano historię dla {self.get_conversation_name_by_id(conv_id)}.")
                    # Usuń stare referencje do obrazów
                    self.rendered_images = []
            except json.JSONDecodeError as e:
                messagebox.showerror("Błąd wczytywania", f"Błąd odczytu historii konwersacji z {filepath}: {e}")
                self.status_var.set(f"Błąd wczytywania historii: {filepath}")
            except Exception as e:
                messagebox.showerror("Błąd", f"Nieoczekiwany błąd podczas ładowania historii: {e}")
        else:
            self.status_var.set(f"Plik historii {filepath} nie istnieje. Rozpoczynanie nowej historii.")
            self.conversation_history = []
            self.system_prompt.delete(0, tk.END)
            self.system_prompt.insert(0, "Jesteś pomocnym asystentem. Odpowiadaj w języku polskim.")
            self.rendered_images = [] 
        
        # Wyświetl historię po załadowaniu
        self.display_current_conversation_messages()


    def display_current_conversation_messages(self):
        """Odświeża okno czatu, wyświetlając całą historię konwersacji."""
        self.chat_display.config(state='normal')
        self.chat_display.delete('1.0', tk.END)
        self.rendered_images = [] 
        
        for message in self.conversation_history:
            sender = message['role']
            for part in message['parts']:
                if 'text' in part:
                    # Używamy nowej, ulepszonej funkcji display_message
                    self.display_message("user" if sender == "user" else "bot", part['text'], is_new_entry=False)
        
        self.chat_display.config(state='disabled')
        self.chat_display.see(tk.END)


    def get_conversation_name_by_id(self, conv_id):
        """Zwraca przyjazną nazwę konwersacji na podstawie jej ID."""
        for conv_meta in self.conversations_metadata:
            if conv_meta['id'] == conv_id:
                return conv_meta['name']
        return conv_id 

    def rename_current_conversation(self):
        """Umożliwia zmianę nazwy aktywnej konwersacji."""
        if not self.current_conversation_id:
            messagebox.showwarning("Brak konwersacji", "Nie wybrano konwersacji do zmiany nazwy.")
            return

        current_name = self.get_conversation_name_by_id(self.current_conversation_id) if self.current_conversation_id else None

        if not current_name: 
            current_name = self.current_conversation_id

        new_name = simpledialog.askstring(
            "Zmień nazwę konwersacji",
            f"Wprowadź nową nazwę dla '{current_name}':",
            initialvalue=current_name
        )

        if new_name and new_name.strip() != "" and new_name.strip() != current_name:
            new_name = new_name.strip()
            
            for conv_meta in self.conversations_metadata:
                if conv_meta['id'] == self.current_conversation_id:
                    conv_meta['name'] = new_name
                    break
            
            self.save_conversation() 

            self.load_conversation_list() 
            self.status_var.set(f"Zmieniono nazwę konwersacji na '{new_name}'.")
        elif new_name is not None and new_name.strip() == "":
            messagebox.showwarning("Pusta nazwa", "Nazwa konwersacji nie może być pusta.")

    def delete_selected_conversation(self):
        """Usuwa wybraną konwersację i jej plik."""
        selection_index = self.conversation_listbox.curselection()
        if not selection_index:
            messagebox.showwarning("Wybór konwersacji", "Proszę wybrać konwersację do usunięcia.")
            return
        
        index = selection_index[0]
        selected_name_from_listbox = self.conversation_listbox.get(index)

        selected_conv_id = None
        for conv_meta in self.conversations_metadata:
            if conv_meta['name'] == selected_name_from_listbox:
                selected_conv_id = conv_meta['id']
                break
        
        if not selected_conv_id:
            messagebox.showerror("Błąd", "Nie znaleziono ID dla wybranej konwersacji do usunięcia.")
            return

        if messagebox.askyesno(
            "Potwierdzenie usunięcia", 
            f"Czy na pewno chcesz usunąć konwersację '{selected_name_from_listbox}'?\n"
            "Spowoduje to trwałe usunięcie pliku."
        ):
            filepath_to_delete = os.path.join(self.conversations_dir, f"{selected_conv_id}.json")
            try:
                if os.path.exists(filepath_to_delete):
                    os.remove(filepath_to_delete)
                    self.status_var.set(f"Usunięto konwersację: '{selected_name_from_listbox}'.")
                    
                    if self.current_conversation_id == selected_conv_id:
                        self.conversation_history = []
                        self.current_conversation_id = None
                        self.chat_display.config(state='normal')
                        self.chat_display.delete('1.0', tk.END)
                        self.chat_display.config(state='disabled')
                        self.rendered_images = []
                    
                    self.load_conversation_list() 

                    if self.conversations_metadata and self.current_conversation_id is None:
                        self.current_conversation_id = self.conversations_metadata[0]['id']
                        self.load_conversation_history(self.current_conversation_id)
                        self.display_current_conversation_messages()
                        self.update_conversations_listbox_selection()
                    elif not self.conversations_metadata:
                        self.create_new_conversation(initial_load=True) 

                else:
                    messagebox.showwarning("Błąd", "Plik konwersacji nie istnieje.")
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie można usunąć konwersacji:\n{str(e)}")

    def on_conversation_select(self, event):
        """Obsługuje wybór konwersacji z Listboxa."""
        selection_index = self.conversation_listbox.curselection()
        if selection_index:
            self.load_selected_conversation()


    # === Metody API i czatu ===

    def set_api_key(self):
        """Otwiera okno dialogowe do ustawienia klucza API i zapisuje go."""
        new_api_key = simpledialog.askstring(
            "Ustaw klucz API",
            "Wprowadź swój klucz API Gemini:",
            show='*' 
        )
        if new_api_key:
            try:
                with open(self.api_key_file, 'w') as f:
                    f.write(new_api_key.strip())
                # Ponownie zainicjuj API, aby użyć nowego klucza
                self.init_gemini() 
                if self.model: # Sprawdź, czy model został poprawnie skonfigurowany
                    messagebox.showinfo("Sukces", "Klucz API został pomyślnie ustawiony i API skonfigurowane.")
                else:
                    messagebox.showwarning("Ostrzeżenie", "Klucz API został zapisany, ale nie udało się skonfigurować modelu Gemini. Sprawdź, czy klucz jest poprawny.")
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie można zapisać klucza API lub skonfigurować Gemini API:\n{str(e)}")
                self.status_var.set("Błąd ustawiania klucza API.")
        else:
            messagebox.showwarning("Anulowano", "Nie ustawiono klucza API.")

    def open_token_limit_settings(self):
        """Otwiera okno dialogowe do ustawienia limitu tokenów wyjściowych."""
        current_limit = self.max_output_tokens_limit.get()
        new_limit_str = simpledialog.askstring(
            "Limit tokenów wyjściowych",
            f"Wprowadź maksymalny limit tokenów dla odpowiedzi AI:\n(Obecny limit: {current_limit})\n"
            "Większe wartości mogą wiązać się z wyższymi kosztami i dłuższymi odpowiedziami.",
            initialvalue=str(current_limit)
        )
        
        if new_limit_str:
            try:
                new_limit = int(new_limit_str)
                if new_limit > 0:
                    self.max_output_tokens_limit.set(new_limit)
                    self.status_var.set(f"Limit tokenów wyjściowych ustawiono na: {new_limit}")
                    messagebox.showinfo("Sukces", f"Limit tokenów wyjściowych ustawiono na {new_limit}.")
                else:
                    messagebox.showwarning("Nieprawidłowa wartość", "Limit tokenów musi być liczbą całkowitą większą od zera.")
            except ValueError:
                messagebox.showwarning("Nieprawidłowa wartość", "Proszę wprowadzić prawidłową liczbę całkowitą dla limitu tokenów.")
        elif new_limit_str is not None: 
            messagebox.showwarning("Brak wartości", "Nie wprowadzono wartości dla limitu tokenów.")

    def toggle_dark_mode(self):
        """Przełącza tryb ciemny i stosuje odpowiednie kolory."""
        is_dark = self.dark_mode_enabled.get()
        theme = "dark" if is_dark else "light"
        theme_manager.apply_theme_colors(self.root, self.all_app_widgets, theme)
        self.save_config() # Zapisz zmieniony stan trybu ciemnego


    def display_message(self, sender, text, is_new_entry=True):
        """
        Wyświetla wiadomość z obsługą LaTeX.
        is_new_entry: True jeśli wiadomość jest nowa (z czatu), False jeśli ładowana z historii.
        """
        self.chat_display.config(state='normal')

        # Wybierz odpowiednie tagi na podstawie nadawcy
        prefix_tag = 'user_prefix' if sender == 'user' else 'bot_prefix'
        message_tag = 'user_text' if sender == 'user' else 'bot_text'
        if sender == 'error': # Specjalny przypadek dla błędów
            prefix_tag = 'error'
            message_tag = 'error'

        self.chat_display.insert(tk.END, f"{sender.capitalize()}: ", prefix_tag)
        
        # Regex do dzielenia przez delimitery LaTeX ($...$ dla inline, $$...$$ dla bloku)
        parts = re.split(r'(\$\$[^$]+\$\$|\$[^$]+\$)', text)

        for part in parts:
            if part.startswith('$$') and part.endswith('$$'):
                latex_content = part[2:-2].strip()
                self.insert_latex_image(latex_content, block_mode=True)
            elif part.startswith('$') and part.endswith('$'):
                latex_content = part[1:-1].strip()
                self.insert_latex_image(latex_content, block_mode=False)
            else:
                self.chat_display.insert(tk.END, part, message_tag)
        
        self.chat_display.insert(tk.END, '\n\n') # Dodaj odstęp po każdej wiadomości
        self.chat_display.config(state='disabled')
        self.chat_display.see(tk.END)


    def insert_latex_image(self, latex_expression, block_mode=False):
        """Generates and inserts a LaTeX image into the chat display."""
        try:
            # Set matplotlib figure and axes colors based on current theme
            is_dark_mode = self.dark_mode_enabled.get()
            bg_color = theme_manager.DARK_THEME_COLORS["chat_bg"] if is_dark_mode else theme_manager.LIGHT_THEME_COLORS["chat_bg"]
            text_color = theme_manager.DARK_THEME_COLORS["chat_fg"] if is_dark_mode else theme_manager.LIGHT_THEME_COLORS["chat_fg"]

            # Create a temporary figure and axes
            fig, ax = plt.subplots(figsize=(6, 0.5) if not block_mode else (8, 1))
            
            # Use `usetex=True` for LaTeX rendering. This requires a LaTeX distribution to be installed.
            # Using `$$` for display mode equations or `$` for inline mode equations.
            latex_text = f"$${latex_expression}$$" if block_mode else f"${latex_expression}$"
            
            # Add the text directly to the figure, not axes, for better control of background
            text_obj = fig.text(0.5, 0.5, latex_text, ha='center', va='center', fontsize=12, color=text_color)
            
            # Set background color of the figure
            fig.patch.set_facecolor(bg_color)
            ax.set_facecolor(bg_color) # Ensure axes background also matches

            # Hide axes
            ax.axis('off')
            
            # Get the bounding box of the rendered text
            fig.canvas.draw()
            bbox = text_obj.get_window_extent(renderer=fig.canvas.get_renderer())
            
            # Pad the bounding box slightly
            bbox_padded = bbox.expanded(1.2, 1.2) # Add some padding around the text
            
            # Convert to image
            buf = io.BytesIO()
            # Use bbox_inches='tight' to crop the image to the content
            fig.savefig(buf, format='png', bbox_inches=bbox_padded, dpi=300) 
            buf.seek(0)
            
            image = Image.open(buf)
            photo = ImageTk.PhotoImage(image)
            
            self.rendered_images.append(photo) # Keep a reference!
            
            # Insert image into Text widget
            if block_mode:
                self.chat_display.insert(tk.END, '\n') # New line for block mode
                self.chat_display.image_create(tk.END, image=photo, padx=10, pady=5)
                self.chat_display.insert(tk.END, '\n') # New line after block mode image
            else:
                self.chat_display.image_create(tk.END, image=photo)
            
            plt.close(fig) # Close the figure to free up memory

        except Exception as e:
            error_message = f"Błąd renderowania LaTeX: {e}. Upewnij się, że masz zainstalowany LaTeX (np. MiKTeX/TeX Live) oraz pakiety `pdflatex` i `dvipng` w PATH."
            self.chat_display.insert(tk.END, f"[Błąd renderowania LaTeX: {e}]\n", 'error')
            print(error_message) # Print to console for debugging

    def send_message(self):
        """Wysyła wiadomość do modelu Gemini w osobnym wątku."""
        user_text = self.user_input.get().strip()
        if not user_text: 
            return
        
        # Sprawdź, czy model jest zainicjalizowany
        if not self.model:
            self.display_message("error", "Błąd: Model AI nie jest skonfigurowany. Proszę ustawić klucz API w menu 'Ustawienia'.")
            self.status_var.set("Błąd: brak klucza API")
            return

        if not self.current_conversation_id:
            if not self.save_conversation():
                return 
        
        self.display_message("user", user_text) # Zmieniono sender na "user"
        self.conversation_history.append({"role": "user", "parts": [{"text": user_text}]})
        
        self.save_conversation()

        self.status_var.set("Wysyłanie...")
        Thread(target=self._get_gemini_response, args=(user_text,)).start()
        
        self.user_input.delete(0, tk.END)

    def _get_gemini_response(self, user_message):
        """Pobiera odpowiedź od modelu Gemini."""
        try:
            if not self.model:
                self.root.after(0, self.display_message, "error", "Błąd: Model AI nie jest skonfigurowany. Sprawdź klucz API.")
                self.root.after(0, self.status_var.set, "Błąd modelu AI")
                return

            chat_history_for_model = []
            if self.system_prompt.get().strip():
                chat_history_for_model.append({"role": "user", "parts": [{"text": self.system_prompt.get().strip()}]})
                chat_history_for_model.append({"role": "model", "parts": [{"text": "Rozumiem."}]})

            for msg in self.conversation_history:
                chat_history_for_model.append(msg)
            
            chat = self.model.start_chat(history=chat_history_for_model)

            generation_config = genai.types.GenerationConfig(
                max_output_tokens=self.max_output_tokens_limit.get()
            )
            
            response = chat.send_message(
                user_message,
                request_options={"retry": retry.Retry(predicate=retry.if_transient_error)},
                generation_config=generation_config 
            )
            
            ai_response = response.text
            self.conversation_history.append({"role": "model", "parts": [{"text": ai_response}]})
            self.root.after(0, self.display_message, "bot", ai_response) # Zmieniono sender na "bot"
            self.root.after(0, self.status_var.set, "Gotowy")
            
            self.root.after(0, self.save_conversation)

        except Exception as e:
            error_message = f"Błąd komunikacji z Gemini API: {str(e)}"
            self.root.after(0, self.display_message, "error", error_message) # Zmieniono sender na "error"
            self.root.after(0, self.status_var.set, "Błąd API")

    def export_conversation(self):
        """Eksportuje bieżącą konwersację do pliku tekstowego."""
        if not self.conversation_history:
            messagebox.showwarning("Pusta konwersacja", "Nie ma nic do wyeksportowania!")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Pliki tekstowe", "*.txt"), ("Wszystkie pliki", "*.*")],
            title="Eksportuj konwersację jako"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"Prompt systemowy: {self.system_prompt.get()}\n\n")
                    for message in self.conversation_history:
                        sender = message['role']
                        text_content = ""
                        for part in message['parts']:
                            if 'text' in part:
                                text_content += part['text']
                        f.write(f"{sender.capitalize()}: {text_content}\n\n")
                messagebox.showinfo("Sukces", "Konwersacja wyeksportowana pomyślnie.")
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie można wyeksportować konwersacji:\n{str(e)}")

    def confirm_exit(self):
        """Potwierdzenie wyjścia z aplikacji."""
        if messagebox.askyesno(
            "Zakończ",
            "Czy na pewno chcesz zakończyć aplikację?\n"
            "Upewnij się, że wszystkie konwersacje są zapisane."
        ):
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = GeminiChatApp(root)
    root.mainloop()

