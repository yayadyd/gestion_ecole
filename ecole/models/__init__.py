"""
Package models de l'application ecole.

Découpage par domaine (Plan 2 — phase B) :
    base          AnneeScolaire, EcoleInfo, Licence
    scolarite     Classe, Eleve, Matiere, Inscription, Paiement, MatiereClasse
    finances      Catégories, Depense, Recette
    notes         Notes et résultats (1er cycle, 2e cycle)
    vie_scolaire  Certificats, emploi du temps

L'ordre d'import est significatif : une dépendance ne remonte jamais.
"""
from .base import *
from .scolarite import *
from .finances import *
from .notes import *
from .vie_scolaire import *
