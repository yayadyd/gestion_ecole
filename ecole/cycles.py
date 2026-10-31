# ecole/cycles.py
"""
Centralisation de toute la logique liée aux cycles (1er / 2e).
Une seule source de vérité pour éviter la duplication dans les vues.
"""
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP



# =====================================================================
# ARRONDI ET APPRÉCIATIONS — UNE SEULE SOURCE DE VÉRITÉ
# (cycles 1er et 2e ET lycée utilisent ces fonctions)
# =====================================================================
def arrondir_moyenne(valeur):
    """
    Arrondit une moyenne à 2 décimales, arrondi « scolaire » (12,345 → 12,35).
    Decimal.quantize utilisait par défaut l'arrondi bancaire (12,345 → 12,34).
    """
    return Decimal(str(valeur)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# Échelle sur 20 : la moyenne (10/20) est le seuil de passage → « Passable ».
SEUILS_APPRECIATION_SUR_20 = [
    (Decimal('16'), "Très Bien"),
    (Decimal('14'), "Bien"),
    (Decimal('12'), "Assez Bien"),
    (Decimal('10'), "Passable"),
    (Decimal('8'), "Insuffisant"),
]
APPRECIATION_PLANCHER = "Faible"


def appreciation_sur_20(moyenne):
    """
    Appréciation d'une moyenne sur 20.
    Le classement se fait sur la valeur ARRONDIE à 2 décimales, celle qui est
    affichée : 11,996 s'affiche « 12,00 » et doit donc être « Assez Bien ».
    """
    m = arrondir_moyenne(moyenne)
    for seuil, libelle in SEUILS_APPRECIATION_SUR_20:
        if m >= seuil:
            return libelle
    return APPRECIATION_PLANCHER


def appreciation_sur_10(moyenne):
    """Appréciation d'une moyenne sur 10 : même échelle, proportionnelle (÷ 2)."""
    return appreciation_sur_20(arrondir_moyenne(moyenne) * 2)



def attribuer_rangs(resultats_tries, moyenne=lambda r: r.moyenne_generale):
    """
    Attribue `r.rang` à des résultats DÉJÀ triés par moyenne décroissante.
    Les ex æquo partagent le même rang et le suivant est « sauté » :
    13,50 / 12,00 / 12,00 / 11,00  →  rangs 1, 2, 2, 4.
    La comparaison se fait sur la moyenne enregistrée (2 décimales).
    """
    rang_courant = 0
    moyenne_precedente = None
    for position, r in enumerate(resultats_tries, 1):
        m = moyenne(r)
        if m != moyenne_precedente:
            rang_courant = position
            moyenne_precedente = m
        r.rang = rang_courant
    return resultats_tries


class Cycle(Enum):
    PREMIER = '1er'
    SECOND = '2e'

    # ---------- Propriétés descriptives ----------
    @property
    def libelle(self):
        return "1er Cycle" if self == Cycle.PREMIER else "2e Cycle"

    @property
    def libelle_court(self):
        return "1er" if self == Cycle.PREMIER else "2e"

    @property
    def mode_evaluation(self):
        return "mensuel" if self == Cycle.PREMIER else "trimestriel"

    @property
    def a_coefficients(self):
        return self == Cycle.SECOND

    @property
    def a_note_classe(self):
        return self == Cycle.SECOND

    # ---------- Unités d'évaluation ----------
    @property
    def unites_evaluation(self):
        """Retourne [(clé, libellé), ...] : mois pour 1er, trimestres pour 2e."""
        from .models import Paiement, Evaluation
        if self == Cycle.PREMIER:
            return list(Paiement.MOIS_SCOLAIRES_ORDONNES)
        return list(Evaluation.TRIMESTRE)

    @property
    def libelle_unite(self):
        return "mois" if self == Cycle.PREMIER else "trimestre"

    # ---------- Modèles associés ----------
    @property
    def modele_note(self):
        from .models import Note, NoteMensuelle
        return Note if self == Cycle.SECOND else NoteMensuelle

    @property
    def modele_resultat(self):
        from .models import ResultatTrimestre, ResultatMensuel
        return ResultatTrimestre if self == Cycle.SECOND else ResultatMensuel

    @property
    def modele_detail(self):
        from .models import DetailResultat, DetailResultatMensuel
        return DetailResultat if self == Cycle.SECOND else DetailResultatMensuel

    # ---------- Formule de moyenne par matière ----------
    def calculer_moyenne_matiere(self, note_classe, note_compo, coef):
        """
        1er cycle : la note EST la moyenne de la matière (coef ignoré).
        2e cycle : (note_classe + note_compo * 2) / 3.
        """
        if self == Cycle.PREMIER:
            return Decimal(str(note_compo or 0))
        nc = Decimal(str(note_classe or 0))
        nc_compo = Decimal(str(note_compo or 0)) * Decimal('2')
        return (nc + nc_compo) / Decimal('3')

    # ---------- Note maximale du cycle ----------
    @property
    def note_max(self):
        """1er cycle : note sur 10. 2e cycle : note sur 20."""
        return 10 if self == Cycle.PREMIER else 20

    @property
    def seuil_passage(self):
        """Seuil de passage (moyenne suffisante)."""
        return 5 if self == Cycle.PREMIER else 10

    # ---------- Appréciation ----------
    def appreciation(self, moyenne):
        """
        1er cycle : moyenne sur 10. 2e cycle : moyenne sur 20.
        Même échelle que le lycée (voir appreciation_sur_20).
        """
        if self == Cycle.PREMIER:
            return appreciation_sur_10(moyenne)
        return appreciation_sur_20(moyenne)

    # ---------- Helpers de classe ----------
    @classmethod
    def from_classe(cls, classe):
        return cls(classe.cycle)


# Filtres matières par cycle (helpers réutilisables)
def matieres_du_cycle(cycle_value):
    from .models import Matiere
    return Matiere.objects.filter(cycle=cycle_value).order_by('nomMatiere')


def classes_du_cycle(cycle_value):
    from .models import Classe
    return Classe.objects.filter(cycle=cycle_value).order_by('nomClasse')


# =====================================================================
# ✅ FIX: Structure des tentatives 2e cycle centralisée ici (au lieu de views.py)
# =====================================================================
STRUCTURE_TENTATIVES_2E_CYCLE = {
    '7ème A': 2,
    '8ème A': 2,
    '9ème A': 3,
}


# =====================================================================
# ✅ FIX: Mois scolaires centralisés (évite la duplication dans views.py)
# =====================================================================
MOIS_SCOLAIRES = [
    (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre'),
    (1, 'Janvier'), (2, 'Février'), (3, 'Mars'),
    (4, 'Avril'), (5, 'Mai'), (6, 'Juin'),
]

MOIS_CALENDAIRES = [
    (1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
    (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
    (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre'),
]