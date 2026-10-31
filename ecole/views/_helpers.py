"""Fonctions utilitaires internes partagées par les vues."""
from ._deps import *

# ✅ __all__ : sans lui, `from ._helpers import *` n'importe PAS les noms
# commençant par `_` (ex. `_moyenne_annuelle_inscription`,
# `_moyenne_bulletin`). Les vues `documents.py` et `cycle2.py` les
# appellent directement, ce qui provoquait un NameError au runtime.
__all__ = [
    '_annee_defaut',
    '_calculer_moyennes_tendances',
    '_classes_doublees_affichage',
    '_construire_fiche_suivi_data',
    '_construire_historique_ecoles',
    '_construire_lignes_proposition',
    '_construire_matieres_et_details',
    '_construire_moyennes_par_tentative_chronologique',
    '_flash_compteurs',
    '_inscriptions_niveau_fiche',
    '_matieres_classe_annee',
    '_moyenne_annuelle_inscription',
    '_moyenne_bulletin',
    '_safe_csv',
    '_stats_classe',
    '_stats_resultats',
    '_trouver_annee_precedente',
]


def _annee_defaut():
    annee_actuelle = date.today().year
    if date.today().month >= 8:
        return f"{annee_actuelle}-{annee_actuelle + 1}"
    return f"{annee_actuelle - 1}-{annee_actuelle}"


def _calculer_moyennes_tendances(moyennes_par_position, matieres):
    tendances = {m.idMatiere: m.tendance for m in matieres}

    resultats = []
    for moyennes in moyennes_par_position:
        moyennes_litteraires = []
        moyennes_scientifiques = []

        for matiere_id, moyenne in moyennes.items():
            tendance = tendances.get(matiere_id)
            if tendance == 'litteraire':
                moyennes_litteraires.append(moyenne)
            elif tendance == 'scientifique':
                moyennes_scientifiques.append(moyenne)

        resultats.append({
            'litteraire': (
                arrondir_moyenne(sum(moyennes_litteraires) / len(moyennes_litteraires))
                if moyennes_litteraires else None
            ),
            'scientifique': (
                arrondir_moyenne(sum(moyennes_scientifiques) / len(moyennes_scientifiques))
                if moyennes_scientifiques else None
            ),
        })

    return resultats


def _classes_doublees_affichage(eleve):
    doublees = [c for c in [eleve.redoublement_1, eleve.redoublement_2, eleve.redoublement_3] if c]
    return ", ".join(doublees) if doublees else "Néant"


def _construire_fiche_suivi_data(eleve):
    trimestres_ordre = [key for key, _ in Evaluation.TRIMESTRE]
    data_par_classe = {}
    toutes_matieres = {}

    for nom_classe, nb_tentatives_max in STRUCTURE_TENTATIVES_2E_CYCLE.items():
        inscriptions = list(
            _inscriptions_niveau_fiche(eleve, PREFIXES_NIVEAU_FICHE[nom_classe])
            .select_related('anneeScolaire')
            .order_by('anneeScolaire__anneeScolaire')
        )

        tentatives = []
        for i in range(nb_tentatives_max):
            if i < len(inscriptions):
                inscription = inscriptions[i]
                grille_matiere = {}
                for idx, trimestre_key in enumerate(trimestres_ordre):
                    resultat = ResultatTrimestre.objects.filter(
                        inscription=inscription, trimestre=trimestre_key
                    ).prefetch_related('details__matiere').first()
                    if resultat:
                        for detail in resultat.details.all():
                            # ✅ « Non saisie » n'est PAS une note de 0
                            if detail.matiere.tendance and detail.appreciation != LIBELLE_NON_SAISIE:
                                toutes_matieres[detail.matiere_id] = detail.matiere
                                if detail.matiere_id not in grille_matiere:
                                    grille_matiere[detail.matiere_id] = [None, None, None]
                                grille_matiere[detail.matiere_id][idx] = detail.moyenne_generale

                moyennes_annuelles = {}
                for matiere_id, valeurs in grille_matiere.items():
                    notes_valides = [v for v in valeurs if v is not None]
                    if notes_valides:
                        moyennes_annuelles[matiere_id] = arrondir_moyenne(
                            sum(notes_valides) / len(notes_valides)
                        )

                tentatives.append({
                    'annee': inscription.anneeScolaire.anneeScolaire,
                    'grille': grille_matiere,
                    'moyennes_annuelles': moyennes_annuelles,
                    'existe': True,
                })
            else:
                tentatives.append({'annee': '', 'grille': {}, 'moyennes_annuelles': {}, 'existe': False})

        data_par_classe[nom_classe] = tentatives

    matieres_triees = sorted(
        toutes_matieres.values(),
        key=lambda m: (
            m.tendance or 'zzz',
            m.nomMatiere
        )
    )
    return data_par_classe, matieres_triees


def _construire_historique_ecoles(eleve, ecole, data_par_classe):
    lignes = []
    for nom_classe in ['7ème A', '8ème A', '9ème A']:
        for tentative in data_par_classe.get(nom_classe, []):
            if tentative['existe']:
                lignes.append({
                    'ecole': ecole.nom,
                    'cours': nom_classe,
                    'annee': tentative['annee'],
                    'cap': ecole.circonscription or '',
                    'ae': ecole.academie or '',
                })
    lignes.sort(key=lambda l: l['annee'])
    return lignes


def _construire_lignes_proposition(classe, annee):
    inscriptions = Inscription.objects.filter(
        classe=classe, anneeScolaire=annee
    ).select_related('eleve')

    lignes = []
    est_1er_cycle = classe.cycle == '1er'

    for inscription in inscriptions:
        eleve = inscription.eleve

        if est_1er_cycle:
            resultats = ResultatMensuel.objects.filter(
                inscription=inscription
            ).values_list('moyenne_generale', flat=True)
            moyennes = [float(m) for m in resultats if m is not None]
        else:
            resultats = ResultatTrimestre.objects.filter(
                inscription=inscription, anneeScolaire=annee
            ).values_list('moyenne_generale', flat=True)
            moyennes = [float(m) for m in resultats if m is not None]

        moyenne_annuelle = (
            round(sum(moyennes) / len(moyennes), 2)
            if moyennes else None
        )

        if moyenne_annuelle is not None:
            seuil = 5 if est_1er_cycle else 10
            prop_cons = "Passant" if moyenne_annuelle >= seuil else "Redoublant"
        else:
            prop_cons = None

        lignes.append({
            'eleve': eleve,
            'moyenne_annuelle': moyenne_annuelle,
            'prop_cons': prop_cons,
        })

    lignes.sort(key=lambda x: (x['moyenne_annuelle'] is None, -(x['moyenne_annuelle'] or 0)))

    for i, ligne in enumerate(lignes, 1):
        ligne['rang'] = i

    return lignes


def _construire_matieres_et_details(resultats, attr='details'):
    matieres_vues = {}
    for resultat in resultats:
        details_dict = {}
        for detail in getattr(resultat, attr).all():
            details_dict[detail.matiere_id] = detail
            matieres_vues.setdefault(detail.matiere_id, detail.matiere)
        resultat.details_dict = details_dict
    matieres = sorted(matieres_vues.values(), key=lambda m: m.nomMatiere)
    return matieres, matieres_vues


def _construire_moyennes_par_tentative_chronologique(eleve):
    trimestres_ordre = [key for key, _ in Evaluation.TRIMESTRE]
    toutes_inscriptions = Inscription.objects.filter(
        Q(classe__nomClasse__startswith='7ème') |
        Q(classe__nomClasse__startswith='8ème') |
        Q(classe__nomClasse__startswith='9ème'),
        eleve=eleve, classe__cycle=Cycle.SECOND.value,
    ).select_related('anneeScolaire', 'classe').order_by('anneeScolaire__anneeScolaire')

    resultats_par_position = []
    for inscription in toutes_inscriptions[:3]:
        moyennes = {}
        for trimestre_key in trimestres_ordre:
            resultat = ResultatTrimestre.objects.filter(
                inscription=inscription, trimestre=trimestre_key
            ).prefetch_related('details__matiere').first()
            if resultat:
                for detail in resultat.details.all():
                    if detail.matiere.tendance and detail.appreciation != LIBELLE_NON_SAISIE:
                        moyennes.setdefault(detail.matiere_id, []).append(detail.moyenne_generale)

        moyennes_annuelles = {
            mid: arrondir_moyenne(sum(vals) / len(vals))
            for mid, vals in moyennes.items() if vals
        }
        resultats_par_position.append(moyennes_annuelles)

    while len(resultats_par_position) < 3:
        resultats_par_position.append({})
    return resultats_par_position


def _flash_compteurs(request, compteurs, note_max=20):
    message = (
        f"{compteurs['inserees']} nouvelle(s), {compteurs['maj']} mise(s) à jour, "
        f"{compteurs['supprimees']} supprimée(s)."
    )
    if compteurs.get('invalides'):
        message += (
            f" ⚠️ {compteurs['invalides']} valeur(s) invalide(s) ignorée(s) "
            f"(doit être entre 0 et {note_max})."
        )
        messages.warning(request, message)
    else:
        messages.success(request, message)


def _inscriptions_niveau_fiche(eleve, prefixe):
    return Inscription.objects.filter(
        eleve=eleve,
        classe__cycle=Cycle.SECOND.value,
        classe__nomClasse__startswith=prefixe,
    )


def _matieres_classe_annee(classe, annee_id=None):
    """
    Matières d'une classe pour UNE année : celle demandée, sinon la plus récente.
    ✅ FIX: avant, les matières de toutes les années configurées étaient mélangées.
    """
    annee = None
    if annee_id:
        try:
            annee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
        except (ValueError, TypeError):
            annee = None
    if annee is None:
        annee = AnneeScolaire.objects.order_by('-anneeScolaire').first()

    qs = MatiereClasse.objects.filter(classe=classe)
    if annee is not None:
        qs = qs.filter(annee_scolaire=annee)
    qs = qs.select_related('matiere').order_by('ordre_affichage', 'matiere__nomMatiere')
    return [mc.matiere for mc in qs]


def _moyenne_annuelle_inscription(inscription):
    resultats = ResultatTrimestre.objects.filter(inscription=inscription)
    moyennes = [r.moyenne_generale for r in resultats]
    if moyennes:
        return round(sum(moyennes) / len(moyennes), 2)
    return None


def _moyenne_bulletin(resultat, total_moy_coef, total_coef):
    """
    Moyenne générale affichée sur un bulletin.
    ✅ On affiche la valeur ENREGISTRÉE (celle qui sert au classement), au lieu
    de la recalculer depuis les lignes de détail (écarts d'arrondi possibles).
    """
    if resultat is not None and resultat.moyenne_generale is not None:
        return float(resultat.moyenne_generale)
    return round(total_moy_coef / total_coef, 2) if total_coef > 0 else 0


def _safe_csv(value):
    if value is None:
        return ''
    s = str(value)
    if s and s[0] in ('=', '+', '-', '@'):
        return "'" + s
    return s


def _stats_classe(modele_resultat, classe, filtre_extra, resultat_eleve=None):
    if not resultat_eleve:
        return {}
    qs = modele_resultat.objects.filter(inscription__classe=classe, **filtre_extra)
    moyenne_classe = qs.aggregate(Avg('moyenne_generale'))['moyenne_generale__avg'] or 0
    nb = qs.count()
    return {
        'moyenne_classe': round(moyenne_classe, 2),
        'nb_eleves': nb,
        'rang': resultat_eleve.rang,
        'effectif': nb,
    }


def _stats_resultats(resultats):
    if not resultats:
        return None
    moyennes = [r.moyenne_generale for r in resultats]
    return {
        'moyenne_classe': round(sum(moyennes) / len(moyennes), 2),
        'meilleure_moyenne': max(moyennes),
        'nb_eleves': len(resultats),
    }


def _trouver_annee_precedente(annee):
    """Retourne l'année scolaire précédente ou None."""
    try:
        annee_debut = annee.get_annee_debut()
        annee_precedente_str = f"{annee_debut - 1}-{annee_debut}"
        return AnneeScolaire.objects.filter(
            anneeScolaire=annee_precedente_str
        ).first()
    except Exception:
        return None


