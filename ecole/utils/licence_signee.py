# ecole/utils/licence_signee.py
"""
Licence signée (Ed25519) : une licence « payée » ne peut plus être fabriquée
en modifiant la base de données ; il faut une clé émise par le vendeur
(avec sa clé privée) et liée à CETTE machine.

Format de la clé : "GE1." + base64url(charge utile JSON) + "." + base64url(signature)
Charge utile : {"v":1,"m":<code machine>,"c":<client>,"t":"payee",
                "e":<date d'expiration ISO ou null>,"i":<date d'émission>,"n":<n°>}

La clé activée est conservée dans le dossier de données (licence.key) :
elle survit donc à la suppression ou à la réinstallation de la base.
"""
import base64
import json
import os
from datetime import date

from . import ed25519
from .licence import get_user_data_dir, get_machine_fingerprint, date_effective

PREFIXE = "GE1."
NOM_FICHIER_CLE = "licence.key"

_cache = {'signature_fichier': None, 'info': None}


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------
def _cle_publique():
    """Clé publique (32 octets) ou None. Priorité : settings, puis cle_publique.py."""
    b64 = None
    try:
        from django.conf import settings
        b64 = getattr(settings, 'LICENCE_CLE_PUBLIQUE', None)
    except Exception:
        pass
    if not b64:
        try:
            from . import cle_publique
            b64 = cle_publique.CLE_PUBLIQUE_B64
        except Exception:
            b64 = None
    if not b64:
        return None
    try:
        brute = _b64d(b64)
        return brute if len(brute) == 32 else None
    except Exception:
        return None


def signature_obligatoire():
    """
    True si le mode « payée » exige une clé signée (le simple champ
    mode='payee' en base ne suffit plus).

    Activation : variable d'environnement GESTION_ECOLE_LICENCE_SIGNEE=1
    ou settings.LICENCE_SIGNEE_OBLIGATOIRE = True.
    Par défaut False : les clients déjà payés avant ce système continuent
    de fonctionner (« mode 'payee' » en base).
    """
    if os.environ.get('GESTION_ECOLE_LICENCE_SIGNEE') == '1':
        return True
    try:
        from django.conf import settings
        return bool(getattr(settings, 'LICENCE_SIGNEE_OBLIGATOIRE', False))
    except Exception:
        return False


# ---------------------------------------------------------------------
# Encodage
# ---------------------------------------------------------------------
def _b64e(octets):
    return base64.urlsafe_b64encode(octets).decode().rstrip('=')


def _b64d(texte):
    texte = texte.strip()
    return base64.urlsafe_b64decode(texte + '=' * (-len(texte) % 4))


def nettoyer(cle):
    """Retire espaces et retours à la ligne (une clé collée depuis WhatsApp est souvent coupée)."""
    return ''.join((cle or '').split())


def code_machine_attendu():
    """Les 16 premiers caractères de l'empreinte (ce que la clé signée doit contenir)."""
    return get_machine_fingerprint()[:16].upper()


def fabriquer_cle(secret, code_machine, client, expire=None, numero="", emise=None):
    """
    Construit une clé signée (côté VENDEUR : nécessite la clé privée).
    `expire` : date ou None (None = licence illimitée).
    """
    charge = {
        'v': 1,
        'm': code_machine.replace('-', '').replace(' ', '').upper(),
        'c': client,
        't': 'payee',
        'e': expire.isoformat() if expire else None,
        'i': (emise or date.today()).isoformat(),
        'n': numero,
    }
    octets = json.dumps(charge, ensure_ascii=False, sort_keys=True,
                        separators=(',', ':')).encode('utf-8')
    return PREFIXE + _b64e(octets) + '.' + _b64e(ed25519.sign(secret, octets))


# ---------------------------------------------------------------------
# Vérification
# ---------------------------------------------------------------------
def verifier_cle(cle, code_machine=None, public=None):
    """
    Vérifie une clé. Retourne (True, info) ou (False, message d'erreur).
    `info` = {'client', 'expire' (date|None), 'emise' (date), 'numero'}.
    N'examine PAS l'expiration (voir cle_signee_valide).
    """
    cle = nettoyer(cle)
    public = public or _cle_publique()
    if public is None:
        return False, "Aucune clé publique de licence n'est configurée dans cette version."

    if not cle.startswith(PREFIXE):
        return False, "Format de clé invalide."
    try:
        corps = cle[len(PREFIXE):]
        charge_b64, signature_b64 = corps.split('.')
        octets = _b64d(charge_b64)
        signature = _b64d(signature_b64)
    except Exception:
        return False, "Clé illisible (incomplète ou mal copiée)."

    if not ed25519.verify(public, octets, signature):
        return False, "Signature invalide : cette clé n'a pas été émise par le vendeur."

    try:
        charge = json.loads(octets.decode('utf-8'))
        if charge.get('v') != 1 or charge.get('t') != 'payee':
            return False, "Version de clé non reconnue."
        info = {
            'client': charge.get('c', ''),
            'expire': date.fromisoformat(charge['e']) if charge.get('e') else None,
            'emise': date.fromisoformat(charge['i']),
            'numero': charge.get('n', ''),
        }
        code_cle = str(charge['m']).upper()
    except Exception:
        return False, "Contenu de la clé invalide."

    attendu = (code_machine or code_machine_attendu()).replace('-', '').upper()
    if code_cle != attendu:
        return False, "Cette clé a été émise pour une autre machine."

    return True, info


# ---------------------------------------------------------------------
# Clé installée sur ce poste
# ---------------------------------------------------------------------
def _chemin_cle():
    return os.path.join(get_user_data_dir(), NOM_FICHIER_CLE)


def installer_cle(cle):
    """Vérifie puis enregistre la clé sur ce poste. Retourne (ok, info|message)."""
    ok, resultat = verifier_cle(cle)
    if not ok:
        return False, resultat

    if resultat['expire'] and date_effective() > resultat['expire']:
        return False, f"Cette licence a expiré le {resultat['expire'].strftime('%d/%m/%Y')}."

    try:
        with open(_chemin_cle(), 'w') as f:
            f.write(nettoyer(cle))
    except Exception:
        return False, "Impossible d'enregistrer la licence (dossier de données non accessible)."

    _cache.update(signature_fichier=None, info=None)
    return True, resultat


def cle_signee_valide():
    """
    Informations de la licence signée installée si elle est valide AUJOURD'HUI
    (signature, machine, expiration), sinon None. Résultat mis en cache : la
    signature n'est recalculée que si le fichier change.
    """
    chemin = _chemin_cle()
    try:
        st = os.stat(chemin)
    except OSError:
        _cache.update(signature_fichier=None, info=None)
        return None

    marque = (st.st_mtime_ns, st.st_size)
    if _cache['signature_fichier'] != marque:
        info = None
        try:
            with open(chemin, 'r') as f:
                ok, resultat = verifier_cle(f.read())
            if ok:
                info = resultat
        except Exception:
            info = None
        _cache.update(signature_fichier=marque, info=info)

    info = _cache['info']
    if info and info['expire'] and date_effective() > info['expire']:
        return None
    return info