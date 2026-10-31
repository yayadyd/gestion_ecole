"""
Agrégation comptable par section (Plan 2 — phase C).

Source de vérité UNIQUE pour tous les tableaux de bord et rapports.
Aucune vue ne doit agréger des montants elle-même.

Règle fondamentale :
    global == 1er + 2e + lycee + commun

Les paiements d'élèves n'ont pas de champ `section` : leur section est
dérivée de l'inscription (`inscription.classe.cycle`), et vaut 'lycee'
pour `PaiementLycee`. Les dépenses et recettes portent une section saisie.
"""
from decimal import Decimal

from django.db.models import Sum

from ..lycee_models import PaiementLycee
from ..models import Depense, Paiement, Recette, Section

ZERO = Decimal('0')

SECTIONS = (Section.PREMIER, Section.SECOND, Section.LYCEE, Section.COMMUN)


# ---------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------
def _total(qs):
    """Somme d'un queryset de montants, en Decimal (jamais None)."""
    return qs.aggregate(total=Sum('montant'))['total'] or ZERO


def section_valide(code):
    """Retourne le code de section s'il est valide, sinon None (= global)."""
    if not code:
        return None
    return code if code in Section.values else None


def _paiements_fondamental(annee, section):
    """Paiements du fondamental appartenant à la section demandée."""
    qs = Paiement.objects.filter(inscription__anneeScolaire=annee)
    if section in (Section.PREMIER, Section.SECOND):
        return qs.filter(inscription__classe__cycle=section)
    if section in (Section.LYCEE, Section.COMMUN):
        return qs.none()
    return qs  # global


def _paiements_lycee(annee, section):
    """Paiements du lycée appartenant à la section demandée."""
    if section in (None, Section.LYCEE):
        return PaiementLycee.objects.filter(inscription__annee_scolaire=annee)
    return PaiementLycee.objects.none()


def _recettes(annee, section):
    qs = Recette.objects.filter(anneeScolaire=annee)
    if section:
        qs = qs.filter(section=section)
    return qs


def _depenses(annee, section):
    qs = Depense.objects.filter(anneeScolaire=annee)
    if section:
        qs = qs.filter(section=section)
    return qs


def _ligne(code):
    return {
        'code': code,
        'label': Section(code).label,
        'recettes_paiements': ZERO,
        'recettes_autres': ZERO,
        'recettes': ZERO,
        'depenses': ZERO,
        'resultat': ZERO,
    }


# ---------------------------------------------------------------------
# État comptable par section
# ---------------------------------------------------------------------
def etat_comptable(annee):
    """
    Retourne l'état comptable complet de l'année scolaire.

    {
        'annee': AnneeScolaire | None,
        'sections': {'1er': {...}, '2e': {...}, 'lycee': {...}, 'commun': {...}},
        'global': {'recettes': D, 'depenses': D, 'resultat': D, ...},
    }
    """
    lignes = {code: _ligne(code) for code in SECTIONS}

    if annee is not None:
        # --- Paiements du fondamental, répartis par cycle ---
        par_cycle = {
            row['inscription__classe__cycle']: row['total']
            for row in Paiement.objects
            .filter(inscription__anneeScolaire=annee)
            .values('inscription__classe__cycle')
            .annotate(total=Sum('montant'))
        }
        lignes[Section.PREMIER]['recettes_paiements'] = par_cycle.get('1er', ZERO)
        lignes[Section.SECOND]['recettes_paiements'] = par_cycle.get('2e', ZERO)

        # --- Paiements du lycée ---
        lignes[Section.LYCEE]['recettes_paiements'] = _total(
            PaiementLycee.objects.filter(inscription__annee_scolaire=annee)
        )

        # --- Recettes hors paiements ---
        for row in (Recette.objects.filter(anneeScolaire=annee)
                    .values('section').annotate(total=Sum('montant'))):
            if row['section'] in lignes:
                lignes[row['section']]['recettes_autres'] = row['total']

        # --- Dépenses ---
        for row in (Depense.objects.filter(anneeScolaire=annee)
                    .values('section').annotate(total=Sum('montant'))):
            if row['section'] in lignes:
                lignes[row['section']]['depenses'] = row['total']

    for ligne in lignes.values():
        ligne['recettes'] = ligne['recettes_paiements'] + ligne['recettes_autres']
        ligne['resultat'] = ligne['recettes'] - ligne['depenses']

    total = {
        'recettes_paiements': sum((l['recettes_paiements'] for l in lignes.values()), ZERO),
        'recettes_autres': sum((l['recettes_autres'] for l in lignes.values()), ZERO),
        'recettes': sum((l['recettes'] for l in lignes.values()), ZERO),
        'depenses': sum((l['depenses'] for l in lignes.values()), ZERO),
    }
    total['resultat'] = total['recettes'] - total['depenses']

    return {'annee': annee, 'sections': lignes, 'global': total}


# ---------------------------------------------------------------------
# Détail (cartes, graphiques, listes)
# ---------------------------------------------------------------------
def detail_financier(annee, section=None):
    """Chiffres détaillés pour le tableau de bord d'une section (ou global)."""
    section = section_valide(section)
    resultat = {
        'recettes_frais': ZERO,
        'recettes_scolarite': ZERO,
        'recettes_autres': ZERO,
        'nb_recettes_autres': 0,
        'total_recettes': ZERO,
        'total_depenses': ZERO,
        'resultat': ZERO,
        'nb_paiements': 0,
        'nb_depenses': 0,
        'recettes_par_categorie': [],
        'depenses_par_categorie': [],
        'dernieres_depenses': [],
    }
    if annee is None:
        return resultat

    paiements_f = _paiements_fondamental(annee, section)
    paiements_l = _paiements_lycee(annee, section)
    recettes_qs = _recettes(annee, section)
    depenses_qs = _depenses(annee, section)

    resultat['recettes_frais'] = (
        _total(paiements_f.filter(est_inscription=True))
        + _total(paiements_l.filter(est_inscription=True))
    )
    resultat['recettes_scolarite'] = (
        _total(paiements_f.filter(est_inscription=False))
        + _total(paiements_l.filter(est_inscription=False))
    )
    resultat['nb_paiements'] = paiements_f.count() + paiements_l.count()

    resultat['recettes_autres'] = _total(recettes_qs)
    resultat['nb_recettes_autres'] = recettes_qs.count()
    resultat['recettes_par_categorie'] = list(
        recettes_qs.values('categorie__nom').annotate(total=Sum('montant')).order_by('-total')
    )

    resultat['total_depenses'] = _total(depenses_qs)
    resultat['nb_depenses'] = depenses_qs.count()
    par_categorie = list(
        depenses_qs.values('categorie__nom').annotate(total=Sum('montant')).order_by('-total')
    )
    total_depenses = resultat['total_depenses']
    for item in par_categorie:
        item['pourcentage'] = (
            round(float(item['total']) / float(total_depenses) * 100, 1)
            if total_depenses else 0
        )
    resultat['depenses_par_categorie'] = par_categorie

    resultat['total_recettes'] = (
        resultat['recettes_frais'] + resultat['recettes_scolarite'] + resultat['recettes_autres']
    )
    resultat['resultat'] = resultat['total_recettes'] - total_depenses

    resultat['dernieres_depenses'] = list(
        depenses_qs.select_related('categorie').order_by('-date_depense', '-id')[:5]
    )
    return resultat


def evolution_mensuelle(annee, section=None):
    """Série mensuelle (12 mois scolaires) recettes / dépenses."""
    from ..utils.dates import get_mois_annee_scolaire

    section = section_valide(section)
    serie = []
    if annee is None:
        return serie

    paiements_f = _paiements_fondamental(annee, section)
    paiements_l = _paiements_lycee(annee, section)
    recettes_qs = _recettes(annee, section)
    depenses_qs = _depenses(annee, section)

    for num_mois, _nom, annee_reelle, label in get_mois_annee_scolaire(annee):
        paiements_mois = (
            _total(paiements_f.filter(
                date_paiement__month=num_mois, date_paiement__year=annee_reelle))
            + _total(paiements_l.filter(
                date_paiement__month=num_mois, date_paiement__year=annee_reelle))
        )
        recettes_mois = paiements_mois + _total(recettes_qs.filter(
            date_recette__month=num_mois, date_recette__year=annee_reelle))
        depenses_mois = _total(depenses_qs.filter(
            date_depense__month=num_mois, date_depense__year=annee_reelle))

        serie.append({
            'label': label,
            'mois': num_mois,
            'annee': annee_reelle,
            'recettes': float(recettes_mois),
            'depenses': float(depenses_mois),
        })
    return serie


def sections_disponibles():
    """Sections comptables disponibles selon les modules activés (EcoleInfo)."""
    from ..models import EcoleInfo, Section
    try:
        ecole = EcoleInfo.get_solo()
        act_fond = ecole.activer_fondamental
        act_lycee = ecole.activer_lycee
    except Exception:
        act_fond = True
        act_lycee = True
    codes = []
    if act_fond:
        codes += [Section.PREMIER, Section.SECOND]
    if act_lycee:
        codes += [Section.LYCEE]
    codes += [Section.COMMUN]
    return codes


def sections_choix_liste(section_active=None, inclure_global=True):
    """Liste de choix de section (dict) filtrée par modules activés."""
    from ..models import Section
    codes = sections_disponibles()
    choix = []
    if inclure_global:
        choix.append({'code': 'global', 'label': 'Global', 'actif': section_active is None})
    for c in codes:
        choix.append({'code': c, 'label': Section(c).label, 'actif': section_active == c})
    return choix
