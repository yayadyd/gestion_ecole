# run_server.py
import os
import sys

# ============================================================
# REDIRECTION STDOUT/STDERR (AVANT TOUT)
# ============================================================
USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".gestion_ecole_data")
os.makedirs(USER_DATA_DIR, exist_ok=True)

LOG_FILE = os.path.join(USER_DATA_DIR, 'gestion_ecole.log')

# Rediriger stdout et stderr
try:
    sys.stdout = open(LOG_FILE, 'a', encoding='utf-8', buffering=1)
    sys.stderr = sys.stdout
except Exception:
    pass

# Maintenant on peut importer le reste
import signal
import webbrowser
import threading
import time
import traceback


PORT = 8000

# ============================================================
# IDENTIFIANTS SUPPORT
# ============================================================
SUPPORT_USERNAME = "systeme"
SUPPORT_PASSWORD = "fatos1234"
SUPPORT_EMAIL = "support@ton-entreprise.ml"


def log(message):
    """Écrit dans le fichier de log."""
    try:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {message}")
        sys.stdout.flush()
    except Exception:
        pass


def executer_migrations():
    """Exécute les migrations Django avec capture d'erreurs."""
    try:
        log("Préparation de Django...")
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_ecole.settings')
        django.setup()
        log("Django initialisé")

        # Vérifier le chemin de la base
        from django.conf import settings
        db_path = settings.DATABASES['default']['NAME']
        log(f"Base de données : {db_path}")

        # Vérifier que la base existe
        if not os.path.exists(db_path):
            log("Base inexistante, création...")

        # Exécuter les migrations
        log("Exécution des migrations...")
        from django.core.management import call_command
        call_command('migrate', '--noinput', verbosity=2)
        log("Migrations terminées avec succès")

        return True

    except Exception as e:
        log(f"ERREUR migrations : {e}")
        log(traceback.format_exc())
        return False


def creer_superuser_support():
    """Crée le superuser support."""
    try:
        log("Vérification du compte support...")

        from django.contrib.auth.models import User

        user, created = User.objects.get_or_create(
            username=SUPPORT_USERNAME,
            defaults={
                'email': SUPPORT_EMAIL,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )

        if created:
            user.set_password(SUPPORT_PASSWORD)
            user.save()
            log(f"Compte support créé : {SUPPORT_USERNAME}")
        else:
            changed = False
            if not user.is_superuser:
                user.is_superuser = True
                changed = True
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True
            if changed:
                user.save()
                log(f"Compte support mis à jour : {SUPPORT_USERNAME}")
            else:
                log(f"Compte support existe déjà : {SUPPORT_USERNAME}")

        try:
            from ecole.models import ProfilUtilisateur
            ProfilUtilisateur.get_or_create_pour_user(user)
        except Exception:
            pass

        return True

    except Exception as e:
        log(f"Erreur création compte support : {e}")
        log(traceback.format_exc())
        return False


def preparer_cle_setup():
    """
    Prépare la clé de setup (génération si nécessaire).
    
    ✅ NOUVEAU : La clé est affichée dans le NAVIGATEUR (via /setup/cle/)
    au lieu d'une boîte de dialogue Windows.
    
    Cette fonction :
    - Génère la clé si elle n'existe pas
    - Logue la clé dans le fichier de log (au cas où)
    - Ne fait RIEN si le setup est déjà complété
    """
    try:
        from ecole.utils.setup import generer_cle_setup, get_cle_setup
        from ecole.models import EcoleInfo

        # Vérifier si le setup est déjà complété
        ecole = EcoleInfo.get_solo()
        if ecole.setup_complete:
            log("✅ Setup déjà complété — pas de clé nécessaire")
            return

        # Générer la clé si elle n'existe pas
        cle = get_cle_setup()
        if not cle:
            cle = generer_cle_setup()
            log(f"🔑 Clé de setup générée : {cle}")
            log(f"   → Accessible via http://127.0.0.1:{PORT}/setup/cle/")
        else:
            log(f"🔑 Clé de setup existante : {cle[:16]}...")
            log(f"   → Accessible via http://127.0.0.1:{PORT}/setup/cle/")

    except Exception as e:
        log(f"⚠️ Erreur préparation clé setup : {e}")
        log(traceback.format_exc())


def open_browser():
    """Ouvre le navigateur après un délai."""
    time.sleep(3)
    try:
        webbrowser.open(f'http://127.0.0.1:{PORT}')
    except Exception as e:
        log(f"⚠️ Erreur ouverture navigateur : {e}")


def main():
    log("=" * 70)
    log("Démarrage de Gestion École")
    log("=" * 70)

    # 1. Migrations
    if not executer_migrations():
        log("❌ Migrations échouées, arrêt")
        time.sleep(5)
        return

    # 2. Compte support
    creer_superuser_support()

    # ✅ 3. Préparer la clé de setup (génération uniquement, pas d'affichage)
    preparer_cle_setup()

    # 4. Ouvrir le navigateur
    #    → Le middleware redirige automatiquement vers /setup/cle/ si nécessaire
    threading.Thread(target=open_browser, daemon=True).start()

    # 5. Démarrer le serveur
    log(f"Serveur démarre sur http://127.0.0.1:{PORT}")

    try:
        from waitress.server import create_server
        from gestion_ecole.wsgi import application

        server = create_server(application, host='127.0.0.1', port=PORT, threads=8)
    except OSError as e:
        log(f"ERREUR port {PORT} occupé : {e}")
        webbrowser.open(f'http://127.0.0.1:{PORT}')
        return
    except Exception as e:
        log(f"ERREUR création serveur : {e}")
        log(traceback.format_exc())
        return

    def signal_handler(sig, frame):
        log("Arrêt du serveur")
        try:
            server.close()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        server.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log(f"ERREUR serveur : {e}")
        log(traceback.format_exc())


if __name__ == '__main__':
    main()