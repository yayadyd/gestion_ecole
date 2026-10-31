"""
Façade de lecture des résultats scolaires (Plan 2 — phase D).

Aucun calcul de moyenne ici : les moyennes et rangs sont DÉJÀ calculés
par `services/moyennes.py`, `cycles.py` et `lycee_services.py` et stockés
dans les tables `Resultat*`. Cette façade se contente de :

  - lister les périodes disponibles (compositions mensuelles / trimestres) ;
  - normaliser les trois familles de résultats dans une seule structure ;
  - indiquer si une période est « calculée » ou « à calculer ».

Sections : '1er' (compositions), '2e' (trimestres), 'lycee' (trimestres).
"""
from decimal import Decimal

from django.urls import NoReverseMatch, reverse

from ..lycee_models import (
    ClasseLycee, InscriptionLycee, ResultatTrimestreLycee,
)
from ..models import (
    Classe, CompositionMensuelle, Inscription, ResultatMensuel,
    ResultatTrimestre, Section,
)

TRIMESTRES = (
    'Premier trimestre',
    'Deuxieme trimestre',
    'Troisieme trimestre',
)

SECTIONS_RESULTATS = (Section.PREMIER, Section.SECOND, Section.LYCEE)


# ---------------------------------------------------------------------
# Classes et effectifs
# ---------------------------------------------------------------------
def classes(annee, section):
    """Classes concernées par la section, pour le filtre."""
    if annee is None:
        return []
    if section == Section.LYCEE:
        qs = ClasseLycee.objects.filter(annee_scolaire=annee).order_by('niveau', 'serie', 'nom')
        return [{'id': c.id_classe, 'nom': str(c)} for c in qs]
    qs = Classe.objects.filter(cycle=section).order_by('nomClasse')
    return [{'id': c.idClasse, 'nom': c.nomClasse} for c in qs]


def nombre_inscriptions(annee, section):
    if annee is None:
        return 0
    if section == Section.LYCEE:
        return InscriptionLycee.objects.filter(annee_scolaire=annee).count()
    return Inscription.objects.filter(
        anneeScolaire=annee, classe__cycle=section,
    ).count()


# ---------------------------------------------------------------------
# Périodes
# ---------------------------------------------------------------------
def periodes(annee, section):
    """Liste des périodes disponibles pour la section."""
    if annee is None:
        return []
    if section == Section.PREMIER:
        return [
            {'code': str(c.idComposition), 'label': c.get_mois_display(), 'mois': c.mois}
            for c in CompositionMensuelle.objects
            .filter(anneeScolaire=annee).order_by('mois')
        ]
    if section in (Section.SECOND, Section.LYCEE):
        return [{'code': t, 'label': t, 'mois': None} for t in TRIMESTRES]
    return []


def _periode_defaut(annee, section, periodes_dispo):
    """Dernière période ayant des résultats, sinon première période."""
    if not periodes_dispo:
        return None
    if section == Section.PREMIER:
        derniere = (
            ResultatMensuel.objects
            .filter(inscription__anneeScolaire=annee)
            .select_related('composition')
            .order_by('-composition__mois')
            .first()
        )
        if derniere:
            return str(derniere.composition_id)
    elif section == Section.SECOND:
        derniere = (
            ResultatTrimestre.objects.filter(anneeScolaire=annee)
            .order_by('-date_calcul').first()
        )
        if derniere and derniere.trimestre in [p['code'] for p in periodes_dispo]:
            return derniere.trimestre
    elif section == Section.LYCEE:
        derniere = (
            ResultatTrimestreLycee.objects
            .filter(inscription__annee_scolaire=annee)
            .order_by('-date_calcul').first()
        )
        if derniere and derniere.trimestre in [p['code'] for p in periodes_dispo]:
            return derniere.trimestre
    return periodes_dispo[0]['code']


# ---------------------------------------------------------------------
# Lignes normalisées
# ---------------------------------------------------------------------
def _lien_bulletin(section, eleve_id, annee_scolaire, periode_code, composition_mois=None,
                   inscription_id=None):
    try:
        if section == Section.PREMIER:
            return reverse('fondamental:cycle1_bulletin_eleve', kwargs={
                'eleve_id': eleve_id,
                'annee_scolaire': annee_scolaire,
                'mois': composition_mois,
            })
        if section == Section.SECOND:
            return reverse('fondamental:cycle2_bulletin_eleve', kwargs={
                'eleve_id': eleve_id,
                'annee_scolaire': annee_scolaire,
                'trimestre': periode_code,
            })
        if section == Section.LYCEE:
            return reverse('lycee:bulletin_eleve', kwargs={
                'inscription_id': inscription_id,
                'trimestre': periode_code,
            })
    except NoReverseMatch:
        return None
    return None


def _lignes_1er(annee, composition, classe_id):
    qs = (ResultatMensuel.objects
          .filter(inscription__anneeScolaire=annee, composition=composition)
          .select_related('inscription__eleve', 'inscription__classe', 'composition'))
    if classe_id:
        qs = qs.filter(inscription__classe_id=classe_id)
    qs = qs.order_by('inscription__classe__nomClasse', 'rang',
                     'inscription__eleve__nomEleve')

    lignes = []
    for r in qs:
        eleve = r.inscription.eleve
        lignes.append({
            'eleve': f'{eleve.prenomEleve} {eleve.nomEleve}',
            'matricule': eleve.matricule,
            'classe': r.inscription.classe.nomClasse,
            'moyenne': r.moyenne_generale,
            'rang': r.rang,
            'appreciation': r.appreciation,
            'lien_bulletin': _lien_bulletin(
                Section.PREMIER, eleve.id, annee.anneeScolaire,
                str(composition.idComposition), composition.mois,
            ),
        })
    return lignes


def _lignes_2e(annee, trimestre, classe_id):
    qs = (ResultatTrimestre.objects
          .filter(anneeScolaire=annee, trimestre=trimestre)
          .select_related('inscription__eleve', 'inscription__classe'))
    if classe_id:
        qs = qs.filter(inscription__classe_id=classe_id)
    qs = qs.order_by('inscription__classe__nomClasse', 'rang',
                     'inscription__eleve__nomEleve')

    lignes = []
    for r in qs:
        eleve = r.inscription.eleve
        lignes.append({
            'eleve': f'{eleve.prenomEleve} {eleve.nomEleve}',
            'matricule': eleve.matricule,
            'classe': r.inscription.classe.nomClasse,
            'moyenne': r.moyenne_generale,
            'rang': r.rang,
            'appreciation': r.appreciation,
            'lien_bulletin': _lien_bulletin(
                Section.SECOND, eleve.id, annee.anneeScolaire, trimestre,
            ),
        })
    return lignes


def _lignes_lycee(annee, trimestre, classe_id):
    qs = (ResultatTrimestreLycee.objects
          .filter(inscription__annee_scolaire=annee, trimestre=trimestre)
          .select_related('inscription__eleve', 'inscription__classe'))
    if classe_id:
        qs = qs.filter(inscription__classe_id=classe_id)
    qs = qs.order_by('inscription__classe__nom', 'rang',
                     'inscription__eleve__nom')

    lignes = []
    for r in qs:
        eleve = r.inscription.eleve
        lignes.append({
            'eleve': f'{eleve.prenom} {eleve.nom}',
            'matricule': eleve.matricule,
            'classe': str(r.inscription.classe),
            'moyenne': r.moyenne_generale,
            'rang': r.rang,
            'appreciation': r.appreciation,
            'lien_bulletin': _lien_bulletin(
                Section.LYCEE, None, annee.anneeScolaire, trimestre,
                inscription_id=r.inscription_id,
            ),
        })
    return lignes


# ---------------------------------------------------------------------
# API principale
# ---------------------------------------------------------------------
def resultats(annee, section, periode=None, classe_id=None):
    """
    Résultats d'une section pour une période donnée.

    Retourne un dictionnaire prêt pour le template :
        periodes, periode, classes, lignes, nb_resultats,
        nb_inscriptions, moyenne_section, libelle_section, statut.
    """
    if section not in SECTIONS_RESULTATS:
        section = Section.PREMIER

    periodes_dispo = periodes(annee, section)
    codes = [p['code'] for p in periodes_dispo]
    if periode not in codes:
        periode = _periode_defaut(annee, section, periodes_dispo)

    lignes = []
    if annee is not None and periode:
        if section == Section.PREMIER:
            composition = CompositionMensuelle.objects.filter(
                idComposition=periode, anneeScolaire=annee).first()
            if composition:
                lignes = _lignes_1er(annee, composition, classe_id)
        elif section == Section.SECOND:
            lignes = _lignes_2e(annee, periode, classe_id)
        else:
            lignes = _lignes_lycee(annee, periode, classe_id)

    moyennes = [r['moyenne'] for r in lignes if r['moyenne'] is not None]
    moyenne_section = (
        (sum(moyennes, Decimal('0')) / len(moyennes)).quantize(Decimal('0.01'))
        if moyennes else None
    )

    libelle = next((p['label'] for p in periodes_dispo if p['code'] == periode), None)

    return {
        'section': section,
        'libelle_section': Section(section).label,
        'periodes': periodes_dispo,
        'periode': periode,
        'libelle_periode': libelle,
        'classes': classes(annee, section),
        'lignes': lignes,
        'nb_resultats': len(lignes),
        'nb_inscriptions': nombre_inscriptions(annee, section),
        'moyenne_section': moyenne_section,
        'statut': 'calculé' if lignes else ('à calculer' if periodes_dispo else 'aucune période'),
    }


def resume_global(annee):
    """Synthèse par section : une ligne par section + totaux."""
    lignes = []
    for section in SECTIONS_RESULTATS:
        donnees = resultats(annee, section)
        lignes.append({
            'section': section,
            'label': donnees['libelle_section'],
            'periode': donnees['libelle_periode'],
            'nb_resultats': donnees['nb_resultats'],
            'nb_inscriptions': donnees['nb_inscriptions'],
            'moyenne': donnees['moyenne_section'],
            'statut': donnees['statut'],
        })
    return {
        'lignes': lignes,
        'nb_resultats': sum(l['nb_resultats'] for l in lignes),
        'nb_inscriptions': sum(l['nb_inscriptions'] for l in lignes),
    }
