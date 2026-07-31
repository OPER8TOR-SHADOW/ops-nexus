from database import initialize_database
from gui.app import OPSNexus


def main():
    repository = initialize_database()
    repository.close()

    app = OPSNexus()
    app.mainloop()


if __name__ == "__main__":
    main()