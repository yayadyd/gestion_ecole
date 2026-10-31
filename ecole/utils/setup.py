# ecole/utils/setup.py
"""
Utilitaires pour la sécurité du setup initial.

Génère et vérifie une clé de setup unique qui empêche
l'accès non autorisé à l'assistant de configuration.
"""
import os
import secrets


def _get_user_data_dir():
    """Retourne le dossier de données utilisateur."""
    import sys
    if getattr(sys, 'frozen', False):
        user_data_dir = os.path.join(os.path.expanduser("~"), ".gestion_ecole_data")
    else:
        from django.conf import settings
        user_data_dir = getattr(settings, 'USER_DATA_DIR', None)
        if not user_data_dir:
            user_data_dir = os.path.join(os.path.expanduser("~"), ".gestion_ecole_data")
    os.makedirs(user_data_dir, exist_ok=True)
    return user_data_dir


def _get_setup_key_path():
    """Retourne le chemin du fichier de clé de setup."""
    return os.path.join(_get_user_data_dir(), 'setup_key.txt')


def generer_cle_setup(force=False):
    """
    Génère une clé de setup unique (une seule fois).
    
    Args:
        force: si True, régénère la clé même si elle existe déjà.
    
    Returns:
        La clé générée (str)
    """
    path = _get_setup_key_path()
    
    if os.path.exists(path) and not force:
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except Exception:
            pass
    
    # Générer une nouvelle clé
    cle = secrets.token_urlsafe(32)
    try:
        with open(path, 'w') as f:
            f.write(cle)
    except Exception as e:
        print(f"⚠️ Impossible d'écrire la clé de setup : {e}")
    
    return cle


def get_cle_setup():
    """Lit la clé de setup depuis le fichier."""
    path = _get_setup_key_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except Exception:
        return None


def verifier_cle_setup(request):
    """
    Vérifie que la clé dans l'URL (ou POST) correspond.
    ✅ FIX: Refuse l'accès si la clé est absente du fichier (sauf 1ère installation).
    """
    from .models import EcoleInfo
    
    cle_attendue = get_cle_setup()
    
    # Si aucune clé n'existe et que l'école n'est pas configurée, c'est la 1ère installation.
    if not cle_attendue:
        try:
            ecole = EcoleInfo.get_solo()
            if not ecole.setup_complete and not ecole.nom:
                return True  # Première installation
        except Exception:
            return True
        return False  # Si l'école existe mais pas la clé, on refuse par sécurité.

    cle_fournie = request.GET.get('key') or request.POST.get('key')
    return cle_fournie == cle_attendue