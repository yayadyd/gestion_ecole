# ecole/utils/dates.py
"""
Utilitaires pour la gestion des dates scolaires.

Une année scolaire 2024-2025 couvre :
- Septembre 2024 → Août 2025 (12 mois)
"""
from datetime import date


# Mois dans l'ordre scolaire (Sept → Août)
MOIS_ORDRE_SCOLAIRE = [
    (9, 'Septembre'),
    (10, 'Octobre'),
    (11, 'Novembre'),
    (12, 'Décembre'),
    (1, 'Janvier'),
    (2, 'Février'),
    (3, 'Mars'),
    (4, 'Avril'),
    (5, 'Mai'),
    (6, 'Juin'),
    (7, 'Juillet'),
    (8, 'Août'),
]


def get_mois_annee_scolaire(annee_scolaire_obj):
    """
    Retourne la liste des 12 mois de l'année scolaire,
    avec leur année réelle.

    Args:
        annee_scolaire_obj : instance d'AnneeScolaire

    Returns:
        Liste de tuples (num_mois, nom_mois, annee, label)
        Ex pour 2024-2025 :
        [
            (9, 'Septembre', 2024, 'Septembre 2024'),
            (10, 'Octobre', 2024, 'Octobre 2024'),
            ...
            (8, 'Août', 2025, 'Août 2025'),
        ]
    """
    annee_debut = annee_scolaire_obj.get_annee_debut()
    annee_fin = annee_scolaire_obj.get_annee_fin()

    resultat = []
    for num, nom in MOIS_ORDRE_SCOLAIRE:
        # Sept-Déc → année de début
        # Jan-Août → année de fin
        annee = annee_debut if num >= 9 else annee_fin
        resultat.append((num, nom, annee, f"{nom} {annee}"))

    return resultat


def get_annee_reelle_mois(mois, annee_scolaire_obj):
    """
    Retourne l'année réelle pour un mois donné dans une année scolaire.

    Ex : pour 2024-2025, mois=10 (Octobre) → 2024
         pour 2024-2025, mois=1 (Janvier) → 2025
    """
    annee_debut = annee_scolaire_obj.get_annee_debut()
    annee_fin = annee_scolaire_obj.get_annee_fin()

    if mois in (9, 10, 11, 12):
        return annee_debut
    return annee_fin