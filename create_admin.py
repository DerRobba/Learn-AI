import user_storage as us
import getpass
import sys

def create_admin():
    print("--- Learn-AI: IT-Admin Erstellung ---")
    
    username = input("Benutzername: ").strip()
    if not username:
        print("Fehler: Benutzername darf nicht leer sein.")
        return

    password = getpass.getpass("Passwort: ")
    password_confirm = getpass.getpass("Passwort bestätigen: ")

    if password != password_confirm:
        print("Fehler: Die Passwörter stimmen nicht überein.")
        return

    if len(password) < 3:
        print("Fehler: Passwort muss mindestens 3 Zeichen lang sein.")
        return

    school = input("Schulname: ").strip()
    if not school:
        print("Fehler: Schulname darf nicht leer sein.")
        return

    # Create the user
    success = us.create_user(username, password, 'it-admin', school)

    if success:
        print(f"\nErfolg! IT-Admin '{username}' für die Schule '{school}' wurde erstellt.")
    else:
        print(f"\nFehler: Der IT-Admin konnte nicht erstellt werden.")
        print("Mögliche Gründe: Benutzername bereits vergeben oder es existiert bereits ein Admin für diese Schule.")

if __name__ == "__main__":
    try:
        create_admin()
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        sys.exit(0)
