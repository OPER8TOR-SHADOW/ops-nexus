import customtkinter as ctk

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


def show_menu():

    selected = {"option": None}

    app = ctk.CTk()
    app.title("OPS Collectables Toolkit")
    app.geometry("500x650")
    app.resizable(False, False)

    title = ctk.CTkLabel(
        app,
        text="OPS Collectables Toolkit",
        font=("Segoe UI", 28, "bold"),
    )

    title.pack(pady=30)

    subtitle = ctk.CTkLabel(
        app,
        text="Choose an option",
        font=("Segoe UI", 16),
    )

    subtitle.pack(pady=(0, 20))

    def choose(option):
        selected["option"] = option
        app.destroy()

    buttons = [

        ("🚀 Import Pokémon Set", "import"),
        ("🔍 Search Inventory", "search"),
        ("📊 View Statistics", "stats"),
        ("📄 Generate Spreadsheet", "spreadsheet"),
        ("📦 Generate eBay CSV", "csv"),
        ("💰 Pricing Manager", "pricing"),
        ("⚙ Settings", "settings"),
        ("❌ Exit", "exit"),

    ]

    for text, value in buttons:

        button = ctk.CTkButton(
            app,
            text=text,
            width=320,
            height=42,
            font=("Segoe UI", 16),
            command=lambda v=value: choose(v),
        )

        button.pack(pady=8)

    app.mainloop()

    return selected["option"]