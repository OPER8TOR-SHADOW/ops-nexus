import customtkinter as ctk

# ---------------------------------
# Theme
# ---------------------------------

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

ACCENT = "#C00000"

# ---------------------------------
# Main Window
# ---------------------------------

app = ctk.CTk()
app.title("OPS Nexus")
app.geometry("1280x720")
app.minsize(1100, 650)

# ---------------------------------
# Sidebar
# ---------------------------------

sidebar = ctk.CTkFrame(
    app,
    width=240,
    corner_radius=0
)

sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)

logo = ctk.CTkLabel(
    sidebar,
    text="OPS\nNEXUS",
    font=("Segoe UI", 30, "bold"),
    justify="center"
)

logo.pack(pady=(30, 40))

buttons = [
    "🏠 Dashboard",
    "🚀 Build Listing",
    "📦 Inventory",
    "🖼 Images",
    "💰 Pricing",
    "📊 Statistics",
    "⚙ Settings",
]

for text in buttons:

    btn = ctk.CTkButton(
        sidebar,
        text=text,
        height=42,
        fg_color="transparent",
        hover_color="#2A2A2A",
        anchor="w"
    )

    btn.pack(fill="x", padx=15, pady=5)

# ---------------------------------
# Main Area
# ---------------------------------

main = ctk.CTkFrame(app)

main.pack(
    side="right",
    fill="both",
    expand=True,
    padx=15,
    pady=15
)

title = ctk.CTkLabel(
    main,
    text="Dashboard",
    font=("Segoe UI", 34, "bold")
)

title.pack(anchor="w", padx=20, pady=(20, 10))

subtitle = ctk.CTkLabel(
    main,
    text="Welcome back to OPS Nexus",
    font=("Segoe UI", 18)
)

subtitle.pack(anchor="w", padx=20)

# ---------------------------------
# Status Cards
# ---------------------------------

cards = ctk.CTkFrame(main)

cards.pack(fill="x", padx=20, pady=30)

titles = [
    ("Pokémon API", "🟢 Connected"),
    ("GitHub", "🟢 Ready"),
    ("Inventory", "🟢 Loaded"),
    ("eBay CSV", "🟢 Ready"),
]

for name, status in titles:

    card = ctk.CTkFrame(cards, width=180, height=110)

    card.pack(side="left", padx=10)

    card.pack_propagate(False)

    ctk.CTkLabel(
        card,
        text=name,
        font=("Segoe UI", 18, "bold")
    ).pack(pady=(18, 8))

    ctk.CTkLabel(
        card,
        text=status,
        font=("Segoe UI", 14)
    ).pack()

# ---------------------------------
# Build Button
# ---------------------------------

build = ctk.CTkButton(
    main,
    text="🚀 BUILD LISTING",
    height=55,
    font=("Segoe UI", 20, "bold"),
    fg_color=ACCENT,
    hover_color="#990000"
)

build.pack(padx=20, pady=20, fill="x")

# ---------------------------------
# Log
# ---------------------------------

log = ctk.CTkTextbox(
    main,
    height=260
)

log.pack(
    fill="both",
    expand=True,
    padx=20,
    pady=(10,20)
)

log.insert("end", "Welcome to OPS Nexus\n")
log.insert("end", "System ready.\n")
log.insert("end", "Waiting for command...\n")

app.mainloop()