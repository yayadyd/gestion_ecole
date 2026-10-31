# ecole/utils/licence.py
"""
Utilitaires pour la gestion des licences.

- Dossier de données persistant (même logique en développement et en mode
  packagé PyInstaller OU Nuitka).
- Empreinte de la machine (stable : jamais aléatoire d'un appel à l'autre).
- « Témoin » de première utilisation : empêche de relancer l'essai de 30 jours
  en supprimant la base de données, ou de le prolonger en reculant l'horloge.
"""
import hashlib
import hmac
import json
import os
import platform
import shutil
import sys
import uuid
from datetime import date, datetime, timedelta

DUREE_ESSAI_JOURS = 30


# =====================================================================
# DOSSIER DE DONNÉES
# =====================================================================
def _est_package():
    """
    True si l'application est packagée.
    ✅ FIX: Nuitka ne définit PAS sys.frozen (seul PyInstaller le fait) ;
    un module compilé par Nuitka possède en revanche `__compiled__`.
    """
    if getattr(sys, 'frozen', False):
        return True
    if '__compiled__' in globals():
        return True
    principal = sys.modules.get('__main__')
    return principal is not None and hasattr(principal, '__compiled__')


def _racine_projet():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_user_data_dir():
    """
    Dossier persistant des données. Priorité :
    1. variable d'environnement GESTION_ECOLE_DATA_DIR
    2. settings.USER_DATA_DIR (si défini)
    3. packagé (PyInstaller / Nuitka) : ~/.gestion_ecole_data
    4. développement : racine du projet
    """
    dossier = os.environ.get('GESTION_ECOLE_DATA_DIR')

    if not dossier:
        try:
            from django.conf import settings
            dossier = getattr(settings, 'USER_DATA_DIR', None)
        except Exception:
            dossier = None

    if not dossier:
        if _est_package():
            dossier = os.path.join(os.path.expanduser("~"), ".gestion_ecole_data")
        else:
            dossier = _racine_projet()

    dossier = str(dossier)
    os.makedirs(dossier, exist_ok=True)
    return dossier


# Ancien nom conservé (compatibilité avec d'éventuels appels existants)
_get_user_data_dir = get_user_data_dir


# =====================================================================
# EMPREINTE DE LA MACHINE
# =====================================================================
_cache_empreinte = None


def _lire_ou_creer_machine_id(dossier):
    """
    Identifiant persistant de cette installation (fichier .machine_id).

    - Reprend l'ancien fichier s'il se trouvait ailleurs (anciennes versions
      Nuitka qui l'écrivaient à côté de l'exécutable) : les licences déjà
      payées restent valides.
    - Si l'écriture est impossible, la valeur de repli est DÉTERMINISTE
      (jamais un UUID aléatoire, qui invaliderait la licence à chaque requête).
    """
    chemin = os.path.join(dossier, '.machine_id')

    if os.path.exists(chemin):
        try:
            with open(chemin, 'r') as f:
                valeur = f.read().strip()
            if valeur:
                return valeur
        except Exception:
            pass

    # Migration depuis l'ancien emplacement (racine du projet / dossier d'install)
    ancien = os.path.join(_racine_projet(), '.machine_id')
    if os.path.abspath(ancien) != os.path.abspath(chemin) and os.path.exists(ancien):
        try:
            with open(ancien, 'r') as f:
                valeur = f.read().strip()
            if valeur:
                try:
                    shutil.copyfile(ancien, chemin)
                except Exception:
                    pass
                return valeur
        except Exception:
            pass

    nouveau = str(uuid.uuid4())
    try:
        with open(chemin, 'w') as f:
            f.write(nouveau)
        return nouveau
    except Exception:
        # Écriture impossible : valeur stable dérivée de la machine.
        base = f"repli|{platform.node()}|{platform.system()}|{platform.machine()}"
        return hashlib.sha256(base.encode()).hexdigest()[:36]


def _mac_stable():
    """
    Adresse MAC, ou 0 si Python n'en a trouvé aucune.
    ✅ FIX: sans carte réseau, uuid.getnode() renvoie une valeur ALÉATOIRE
    (bit « multicast » à 1) différente à chaque appel → empreinte instable.
    """
    n = uuid.getnode()
    return 0 if (n >> 40) & 1 else n


def get_machine_fingerprint():
    """
    Empreinte unique de cette machine : machine_id persistant + MAC + hostname
    + système. Calculée une fois par processus.
    """
    global _cache_empreinte
    if _cache_empreinte is not None:
        return _cache_empreinte

    machine_id = _lire_ou_creer_machine_id(get_user_data_dir())
    data = f"{machine_id}|{_mac_stable()}|{platform.node()}|{platform.system()}"
    _cache_empreinte = hashlib.sha256(data.encode()).hexdigest()
    return _cache_empreinte


def get_code_machine():
    """
    Code machine à communiquer au vendeur pour obtenir une licence :
    16 caractères par groupes de 4, ex. « A1B2-C3D4-E5F6-0718 ».
    """
    e = get_machine_fingerprint()[:16].upper()
    return '-'.join(e[i:i + 4] for i in range(0, 16, 4))


def get_machine_id_lisible():
    """Retourne les 8 premiers caractères de l'empreinte, en majuscules."""
    return get_machine_fingerprint()[:8].upper()


# =====================================================================
# TÉMOIN DE PREMIÈRE UTILISATION (anti-réinitialisation de l'essai)
# =====================================================================
# Clé de signature : obscurcit le témoin (ce n'est PAS une sécurité
# cryptographique : le code étant sur la machine du client).
_CLE_TEMOIN = hashlib.sha256(b"gestion-ecole|temoin|v1").digest()
_NOM_FICHIER_TEMOIN = '.licence_temoin'
_REG_SOUS_CLE = r"Software\GestionEcole"
_REG_VALEUR = "g"

_cache_date = {'jour': None, 'effective': None, 'premiere': None}


def _temoin_actif():
    """Inactif en développement (DEBUG) pour pouvoir recréer des bases d'essai."""
    if os.environ.get('GESTION_ECOLE_SANS_TEMOIN') == '1':
        return False
    try:
        from django.conf import settings
        return not settings.DEBUG
    except Exception:
        return True


def _signer(premiere, derniere):
    msg = f"{premiere}|{derniere}".encode()
    return hmac.new(_CLE_TEMOIN, msg, hashlib.sha256).hexdigest()


def _encoder(premiere, derniere):
    return json.dumps({'p': premiere, 'd': derniere, 's': _signer(premiere, derniere)})


def _decoder(texte):
    """Retourne (premiere, derniere) en `date`, ou None si invalide/falsifié."""
    try:
        o = json.loads(texte)
        if not hmac.compare_digest(o['s'], _signer(o['p'], o['d'])):
            return None
        return date.fromisoformat(o['p']), date.fromisoformat(o['d'])
    except Exception:
        return None


def _lire_fichier():
    try:
        with open(os.path.join(get_user_data_dir(), _NOM_FICHIER_TEMOIN), 'r') as f:
            return _decoder(f.read())
    except Exception:
        return None


def _ecrire_fichier(texte):
    try:
        with open(os.path.join(get_user_data_dir(), _NOM_FICHIER_TEMOIN), 'w') as f:
            f.write(texte)
    except Exception:
        pass


def _lire_registre():
    """Second emplacement (Windows) : le supprimer demande de le connaître."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_SOUS_CLE) as cle:
            valeur, _ = winreg.QueryValueEx(cle, _REG_VALEUR)
        return _decoder(valeur)
    except Exception:
        return None


def _ecrire_registre(texte):
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_SOUS_CLE) as cle:
            winreg.SetValueEx(cle, _REG_VALEUR, 0, winreg.REG_SZ, texte)
    except Exception:
        pass


def _aujourdhui_reel():
    from django.utils import timezone
    return timezone.now().date()


def _etat_temoin(aujourdhui):
    """
    Lit les témoins valides (fichier + registre), les fusionne et les met à jour.
    Retourne (première_utilisation, dernière_date_vue).
    """
    lus = [t for t in (_lire_fichier(), _lire_registre()) if t is not None]

    if lus:
        premiere = min(t[0] for t in lus)
        derniere = max(t[1] for t in lus)
    else:
        premiere, derniere = aujourdhui, aujourdhui

    nouvelle_derniere = max(derniere, aujourdhui)

    # Réécriture seulement si quelque chose a changé (au plus une fois par jour)
    if len(lus) < 2 or nouvelle_derniere != derniere or any(t != (premiere, nouvelle_derniere) for t in lus):
        texte = _encoder(premiere.isoformat(), nouvelle_derniere.isoformat())
        _ecrire_fichier(texte)
        _ecrire_registre(texte)

    return premiere, nouvelle_derniere


def date_effective():
    """
    Date à utiliser pour juger l'essai : max(aujourd'hui, dernière date vue).
    ✅ Reculer l'horloge du PC ne redonne donc aucun jour d'essai.
    (Ne concerne que la période d'essai ; une licence payée n'est pas affectée.)
    """
    aujourdhui = _aujourdhui_reel()

    if not _temoin_actif():
        return aujourdhui

    if _cache_date['jour'] == aujourdhui and _cache_date['effective'] is not None:
        return _cache_date['effective']

    premiere, derniere = _etat_temoin(aujourdhui)
    _cache_date.update(jour=aujourdhui, effective=derniere, premiere=premiere)
    return derniere


def debut_essai_reel():
    """
    Date de la toute première utilisation de l'application sur ce poste.
    ✅ Une base recréée reprend cette date : supprimer db.sqlite3 ne relance
    plus 30 jours d'essai.
    """
    aujourdhui = _aujourdhui_reel()
    if not _temoin_actif():
        return aujourdhui
    date_effective()  # alimente le cache
    return _cache_date['premiere'] or aujourdhui