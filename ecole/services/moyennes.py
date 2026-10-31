# ecole/services/moyennes.py
"""
Calcul unifié des moyennes (1er et 2e cycle) — version en lot.

Règles (identiques pour les deux cycles et le lycée) :
- une matière SANS note est ignorée : elle ne compte ni au numérateur ni au
  dénominateur de la moyenne générale ;
- les matières proviennent de MatiereClasse POUR L'ANNÉE CONCERNÉE
  (à défaut : toutes les matières du cycle) ;
- les moyennes sont arrondies à 2 décimales, arrondi scolaire (x,xx5 → haut).

Performance : un calcul de classe = quelques requêtes (inscriptions, notes,
résultats existants) + écritures en lot, quel que soit le nombre de notes.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ..cycles import Cycle, arrondir_moyenne, attribuer_rangs
from ..models import (
    Note, NoteMensuelle, ResultatTrimestre, ResultatMensuel,
    DetailResultat, DetailResultatMensuel,
    Inscription, Matiere, MatiereClasse,
)

LIBELLE_NON_SAISIE = "Non saisie"


# =====================================================================
# MATIÈRES D'UNE CLASSE (POUR UNE ANNÉE)
# =====================================================================
def _get_matieres_classe(classe, cycle, annee):
    """
    Matières d'une classe pour l'année `annee`.

    ✅ FIX: filtre par année (avant, les matières de TOUTES les années étaient
    prises : doublons, et matières abandonnées qui faussaient les moyennes).
    Sans configuration pour cette année : toutes les matières du cycle.
    """
    qs = MatiereClasse.objects.filter(
        classe=classe, annee_scolaire=annee
    ).select_related('matiere').order_by('ordre_affichage', 'matiere__nomMatiere')

    vues = set()
    matieres = []
    for mc in qs:
        if mc.matiere_id not in vues:
            vues.add(mc.matiere_id)
            matieres.append(mc.matiere)

    if matieres:
        return matieres
    return list(Matiere.objects.filter(cycle=cycle.value).order_by('nomMatiere'))


# =====================================================================
# CALCULS PURS (sans accès base : faciles à tester)
# =====================================================================
def _calcul_trimestriel(matieres, notes_de_l_eleve):
    """
    2e cycle. `notes_de_l_eleve` : {matiere_id: note}.
    Retourne (moyenne_generale | None, details).
    """
    cycle = Cycle.SECOND
    total_coef = Decimal('0')
    total_moy_coef = Decimal('0')
    details = []

    for matiere in matieres:
        coef = Decimal(str(matiere.coef or 1))
        note = notes_de_l_eleve.get(matiere.idMatiere)

        if note is None:
            # Matière non saisie : affichée sur le bulletin mais IGNORÉE du
            # calcul. coef=0 pour que le total des coefficients du bulletin
            # reste cohérent avec la moyenne.
            details.append({
                'matiere': matiere,
                'note_classe': Decimal('0'), 'note_compo': Decimal('0'),
                'moyenne_generale': Decimal('0'), 'moyenne_coefficientee': Decimal('0'),
                'coef': Decimal('0'), 'appreciation': LIBELLE_NON_SAISIE,
            })
            continue

        note_classe = Decimal(str(note.noteClasse or 0))
        note_compo = Decimal(str(note.note or 0))
        moyenne = cycle.calculer_moyenne_matiere(note_classe, note_compo, coef)
        moy_coef = moyenne * coef
        total_coef += coef
        total_moy_coef += moy_coef

        details.append({
            'matiere': matiere,
            'note_classe': note_classe,
            'note_compo': note_compo * 2,
            'moyenne_generale': moyenne,
            'moyenne_coefficientee': moy_coef,
            'coef': coef,
            'appreciation': cycle.appreciation(moyenne),
        })

    if total_coef == 0:
        return None, details
    return arrondir_moyenne(total_moy_coef / total_coef), details


def _calcul_mensuel(matieres, notes_de_l_eleve):
    """1er cycle. `notes_de_l_eleve` : {matiere_id: note}. Retourne (moyenne | None, details)."""
    cycle = Cycle.PREMIER
    total = Decimal('0')
    nb = 0
    details = []

    for matiere in matieres:
        note = notes_de_l_eleve.get(matiere.idMatiere)
        if note is None:
            details.append({'matiere': matiere, 'note': Decimal('0'),
                            'appreciation': LIBELLE_NON_SAISIE})
            continue
        valeur = Decimal(str(note.note))
        total += valeur
        nb += 1
        details.append({'matiere': matiere, 'note': valeur,
                        'appreciation': cycle.appreciation(valeur)})

    if nb == 0:
        return None, details
    return arrondir_moyenne(total / nb), details


# =====================================================================
# ENREGISTREMENT EN LOT (commun aux deux cycles)
# =====================================================================
def _persister(modele_resultat, modele_detail, inscriptions, filtre, calculs, fabriquer_detail):
    """
    Écrit résultats + détails en lot.

    filtre   : champs identifiant l'unité (ex. {'trimestre': ..., 'anneeScolaire': ...})
    calculs  : {inscription_id: (moyenne, details)} — uniquement les élèves
               ayant au moins une note.
    Retourne {inscription_id: résultat}.
    """
    ids = [ins.pk for ins in inscriptions]
    maintenant = timezone.now()

    with transaction.atomic():
        existants = {
            r.inscription_id: r
            for r in modele_resultat.objects.filter(inscription_id__in=ids, **filtre)
        }

        # Élève sans aucune note : l'ancien résultat n'a plus de sens.
        obsoletes = [r.pk for iid, r in existants.items() if iid not in calculs]
        if obsoletes:
            modele_resultat.objects.filter(pk__in=obsoletes).delete()

        a_creer, a_maj = [], []
        for ins in inscriptions:
            if ins.pk not in calculs:
                continue
            moyenne = calculs[ins.pk][0]
            r = existants.get(ins.pk)
            if r is not None:
                r.moyenne_generale = moyenne
                r.date_calcul = maintenant
                a_maj.append(r)
            else:
                a_creer.append(modele_resultat(
                    inscription=ins, moyenne_generale=moyenne, **filtre
                ))

        if a_creer:
            modele_resultat.objects.bulk_create(a_creer, batch_size=200)
        if a_maj:
            modele_resultat.objects.bulk_update(
                a_maj, ['moyenne_generale', 'date_calcul'], batch_size=200
            )

        # Relecture : donne les identifiants quelle que soit la version de SQLite
        # (bulk_create ne les renseigne pas toujours).
        resultats = {
            r.inscription_id: r
            for r in modele_resultat.objects.filter(inscription_id__in=ids, **filtre)
        }

        modele_detail.objects.filter(
            resultat_id__in=[r.pk for r in resultats.values()]
        ).delete()

        details = []
        for iid, (_, liste) in calculs.items():
            resultat = resultats[iid]
            details.extend(fabriquer_detail(resultat, d) for d in liste)
        if details:
            modele_detail.objects.bulk_create(details, batch_size=200)

    return resultats


def _detail_trimestriel(resultat, d):
    return DetailResultat(
        resultat=resultat, matiere=d['matiere'],
        note_classe=d['note_classe'], note_compo=d['note_compo'],
        moyenne_generale=d['moyenne_generale'],
        moyenne_coefficientee=d['moyenne_coefficientee'],
        coef=d['coef'], appreciation=d['appreciation'],
    )


def _detail_mensuel(resultat, d):
    return DetailResultatMensuel(
        resultat=resultat, matiere=d['matiere'],
        note=d['note'], appreciation=d['appreciation'],
    )


# =====================================================================
# POINTS D'ENTRÉE
# =====================================================================
def _calculer(classe, inscriptions, unite_evaluation, annee):
    """Calcule et enregistre. Retourne {inscription_id: résultat}."""
    cycle = Cycle.from_classe(classe)
    inscriptions = list(inscriptions)
    if not inscriptions:
        return {}

    matieres = _get_matieres_classe(classe, cycle, annee)
    if not matieres:
        return {}

    eleve_ids = [ins.eleve_id for ins in inscriptions]
    notes_par_eleve = {}  # eleve_id -> {matiere_id: note}

    if cycle == Cycle.PREMIER:
        notes = NoteMensuelle.objects.filter(
            eleve_id__in=eleve_ids,
            composition=unite_evaluation,
            matiere_id__in=[m.idMatiere for m in matieres],
        )
        calcul, filtre = _calcul_mensuel, {'composition': unite_evaluation}
        modele_res, modele_det, fabrique = ResultatMensuel, DetailResultatMensuel, _detail_mensuel
    else:
        notes = Note.objects.filter(
            eleve_id__in=eleve_ids,
            anneeScolaire=annee,
            evaluation__nomEvaluation=unite_evaluation,
            matiere_id__in=[m.idMatiere for m in matieres],
        )
        calcul = _calcul_trimestriel
        filtre = {'trimestre': unite_evaluation, 'anneeScolaire': annee}
        modele_res, modele_det, fabrique = ResultatTrimestre, DetailResultat, _detail_trimestriel

    for n in notes:
        notes_par_eleve.setdefault(n.eleve_id, {})[n.matiere_id] = n

    calculs = {}
    for ins in inscriptions:
        moyenne, details = calcul(matieres, notes_par_eleve.get(ins.eleve_id, {}))
        if moyenne is not None:
            calculs[ins.pk] = (moyenne, details)
        # sinon : aucune note → pas de résultat (et l'ancien est supprimé)

    return _persister(modele_res, modele_det, inscriptions, filtre, calculs, fabrique)


def calculer_moyennes_classe_bulk(classe, unite_evaluation, annee, inscriptions=None):
    """
    Calcule les moyennes de TOUTE une classe en lot.
    `unite_evaluation` : CompositionMensuelle (1er cycle) ou trimestre (2e cycle).
    Retourne le nombre de résultats calculés.
    """
    if inscriptions is None:
        inscriptions = Inscription.objects.filter(
            classe=classe, anneeScolaire=annee
        ).select_related('eleve')
    return len(_calculer(classe, inscriptions, unite_evaluation, annee))


def calculer_moyennes_inscription(inscription, unite_evaluation, annee):
    """Calcule et enregistre les moyennes d'UNE inscription (retourne le résultat ou None)."""
    resultats = _calculer(inscription.classe, [inscription], unite_evaluation, annee)
    return resultats.get(inscription.pk)


# =====================================================================
# CLASSEMENT
# =====================================================================
def classer_inscriptions(inscription_qs, unite_evaluation):
    """
    Classe les inscriptions par moyenne décroissante (une seule écriture en lot).
    Les ex æquo partagent le même rang (1, 2, 2, 4) ; l'ordre de tri entre eux
    est déterministe (nom puis prénom) pour un affichage stable.
    """
    premiere = inscription_qs.select_related('classe').first()
    if not premiere:
        return []

    cycle = Cycle.from_classe(premiere.classe)
    modele = cycle.modele_resultat
    filtre_unite = (
        {'composition': unite_evaluation} if cycle == Cycle.PREMIER
        else {'trimestre': unite_evaluation}
    )

    resultats = list(
        modele.objects.filter(inscription__in=inscription_qs, **filtre_unite)
        .select_related('inscription__eleve')
    )

    tries = sorted(
        resultats,
        key=lambda r: (
            -r.moyenne_generale,
            r.inscription.eleve.nomEleve,
            r.inscription.eleve.prenomEleve,
        ),
    )
    attribuer_rangs(tries)  # ex æquo : même rang (1, 2, 2, 4)

    if tries:
        modele.objects.bulk_update(tries, ['rang'], batch_size=200)
    return tries