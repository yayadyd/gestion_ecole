# ecole/utils/cartes.py
"""
Validation des paramètres de personnalisation des cartes scolaires
(couleur et image de fond) reçus par l'URL.

Empêche :
- la traversée de répertoire via ?fond=../../...
- les couleurs invalides qui font planter ReportLab (HexColor)
- l'injection de contenu arbitraire dans les gabarits de prévisualisation
"""
import re

_RE_COULEUR = re.compile(r'^#[0-9a-fA-F]{6}$')
# Nom de fichier simple : lettres, chiffres, _ et -, extension image facultative.
_RE_FOND = re.compile(r'^[A-Za-z0-9_\-]+(\.(jpg|jpeg|png))?$')


def couleur_valide(valeur, defaut):
    """Retourne `valeur` si c'est un code #RRGGBB valide, sinon `defaut`."""
    valeur = (valeur or '').strip()
    return valeur if _RE_COULEUR.match(valeur) else defaut


def fond_valide(valeur, defaut):
    """Retourne `valeur` si c'est un nom de fichier image simple, sinon `defaut`."""
    valeur = (valeur or '').strip()
    return valeur if _RE_FOND.match(valeur) else defaut