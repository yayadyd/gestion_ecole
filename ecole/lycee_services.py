# ecole/lycee_services.py
"""
Services du Lycée - Logique métier centralisée.

Contient :
- Calcul des moyennes par matière et par trimestre
- Classement des élèves
- Statistiques de classe
- Génération des bulletins PDF (avec en-tête, Série, Matricule)
- Gestion des paiements (échéances, montants attendus)
- Génération PDF de l'emploi du temps
"""
import io
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from .services.paiements import _repartir, _allouer_paiements
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY


from collections import defaultdict

from django.db import transaction
from django.utils import timezone
from django.db.models import Avg

from .cycles import appreciation_sur_20, arrondir_moyenne, attribuer_rangs

from .lycee_models import (
    NoteLycee, ResultatTrimestreLycee, DetailResultatLycee,
    CoefficientLycee, MatiereLycee, InscriptionLycee, PaiementLycee,
    PlageHoraireLycee, EmploiTempsLycee, CreneauEmploiTempsLycee,
    MatiereClasseLycee,
)
from .utils.pdf_generator import (
    _style_arabe,
    _preparer_arabe,
    _enregistrer_police_arabe,
    _faire_callback_entete,
    _construire_entete_3_zones,
)

logger = logging.getLogger(__name__)

# =====================================================================
# 1. CALCUL DES MOYENNES
# =====================================================================

def calculer_moyenne_matiere(note_classe, note_composition):
    """
    Moyenne d'une matière au lycée : (Composition × 2 + Note de classe) / 3,
    arrondie à 2 décimales (même valeur que celle affichée).
    """
    nc = Decimal(str(note_classe or 0))
    ncomp = Decimal(str(note_composition or 0)) * Decimal('2')
    return arrondir_moyenne((ncomp + nc) / Decimal('3'))


def get_coefficient(matiere, niveau, serie):
    """Coefficient d'une matière pour un niveau et une série (1 requête)."""
    try:
        coef = CoefficientLycee.objects.get(
            matiere=matiere, niveau=niveau, serie=serie or ''
        )
        return coef.coefficient
    except CoefficientLycee.DoesNotExist:
        return Decimal('1.0')


def _charger_coefficients(niveau, serie):
    """Tous les coefficients d'un niveau/série en UNE requête : {matiere_id: coef}."""
    return {
        c.matiere_id: c.coefficient
        for c in CoefficientLycee.objects.filter(niveau=niveau, serie=serie or '')
    }


def appreciation_lycee(moyenne):
    """Appréciation d'une moyenne sur 20 (échelle unique de l'application)."""
    return appreciation_sur_20(moyenne)


def _calculer_lycee(classe, inscriptions, trimestre):
    """
    Calcule et enregistre les résultats d'un trimestre, EN LOT :
    coefficients chargés une fois, toutes les notes en une requête,
    écritures groupées. Retourne {inscription_id: résultat}.

    Règle : une matière sans note n'existe pas (elle est ignorée).
    """
    inscriptions = list(inscriptions)
    if not inscriptions:
        return {}

    ids = [ins.pk for ins in inscriptions]
    coefs = _charger_coefficients(classe.niveau, classe.serie)

    notes_par_inscription = defaultdict(list)
    for note in NoteLycee.objects.filter(inscription_id__in=ids, trimestre=trimestre):
        notes_par_inscription[note.inscription_id].append(note)

    calculs = {}
    for ins in inscriptions:
        total_coef = Decimal('0')
        total_moy_coef = Decimal('0')
        details = []

        for note in notes_par_inscription.get(ins.pk, []):
            coef = coefs.get(note.matiere_id, Decimal('1.0'))
            moyenne_matiere = calculer_moyenne_matiere(note.note_classe, note.note_composition)
            moy_coef = moyenne_matiere * coef
            total_coef += coef
            total_moy_coef += moy_coef
            details.append({
                'matiere_id': note.matiere_id,
                'note_classe': note.note_classe,
                'note_composition': note.note_composition,
                'moyenne_matiere': moyenne_matiere,
                'coefficient': coef,
                'moyenne_coefficientee': moy_coef,
                'appreciation': appreciation_lycee(moyenne_matiere),
            })

        if total_coef == 0:
            continue

        moyenne_generale = arrondir_moyenne(total_moy_coef / total_coef)
        calculs[ins.pk] = {
            'moyenne_generale': moyenne_generale,
            'total_coefficients': total_coef,
            'total_notes_coefficientees': total_moy_coef,
            'appreciation': appreciation_lycee(moyenne_generale),
            'details': details,
        }

    maintenant = timezone.now()
    champs = ['moyenne_generale', 'total_coefficients',
              'total_notes_coefficientees', 'appreciation', 'date_calcul']

    with transaction.atomic():
        existants = {
            r.inscription_id: r
            for r in ResultatTrimestreLycee.objects.filter(
                inscription_id__in=ids, trimestre=trimestre
            )
        }

        # Élève sans aucune note : l'ancien résultat n'a plus de sens.
        obsoletes = [r.pk for iid, r in existants.items() if iid not in calculs]
        if obsoletes:
            ResultatTrimestreLycee.objects.filter(pk__in=obsoletes).delete()

        a_creer, a_maj = [], []
        for ins in inscriptions:
            c = calculs.get(ins.pk)
            if c is None:
                continue
            r = existants.get(ins.pk)
            if r is not None:
                for champ in champs[:-1]:
                    setattr(r, champ, c[champ])
                r.date_calcul = maintenant
                a_maj.append(r)
            else:
                a_creer.append(ResultatTrimestreLycee(
                    inscription=ins, trimestre=trimestre,
                    **{champ: c[champ] for champ in champs[:-1]},
                ))

        if a_creer:
            ResultatTrimestreLycee.objects.bulk_create(a_creer, batch_size=200)
        if a_maj:
            ResultatTrimestreLycee.objects.bulk_update(a_maj, champs, batch_size=200)

        # Relecture : identifiants fiables quelle que soit la version de SQLite.
        resultats = {
            r.inscription_id: r
            for r in ResultatTrimestreLycee.objects.filter(
                inscription_id__in=ids, trimestre=trimestre
            )
        }

        DetailResultatLycee.objects.filter(
            resultat_id__in=[r.pk for r in resultats.values()]
        ).delete()

        details_a_creer = []
        for iid, c in calculs.items():
            resultat = resultats[iid]
            for d in c['details']:
                details_a_creer.append(DetailResultatLycee(resultat=resultat, **d))
        if details_a_creer:
            DetailResultatLycee.objects.bulk_create(details_a_creer, batch_size=200)

        # Effectif = nombre de résultats de la classe pour ce trimestre
        effectif = ResultatTrimestreLycee.objects.filter(
            inscription__classe=classe, trimestre=trimestre
        ).count()
        ResultatTrimestreLycee.objects.filter(
            inscription__classe=classe, trimestre=trimestre
        ).update(effectif_classe=effectif)

    return resultats


def calculer_resultat_inscription(inscription, trimestre):
    """Résultat trimestriel d'UN élève (ResultatTrimestreLycee ou None si aucune note)."""
    resultats = _calculer_lycee(inscription.classe, [inscription], trimestre)
    return resultats.get(inscription.pk)


def calculer_moyennes_classe(classe, trimestre, annee=None):
    """
    Calcule les moyennes de toute une classe pour un trimestre.
    Retourne le nombre de résultats calculés.
    """
    inscriptions = InscriptionLycee.objects.filter(classe=classe)
    if annee is not None:
        inscriptions = inscriptions.filter(annee_scolaire=annee)
    return len(_calculer_lycee(classe, inscriptions, trimestre))


# =====================================================================
# 2. CLASSEMENT
# =====================================================================

def classer_classe(classe, trimestre, annee=None):
    """
    Classe les élèves d'une classe par moyenne décroissante (une écriture en lot).
    Les ex æquo partagent le même rang (1, 2, 2, 4).
    """
    qs = ResultatTrimestreLycee.objects.filter(
        inscription__classe=classe, trimestre=trimestre
    )
    if annee is not None:
        qs = qs.filter(inscription__annee_scolaire=annee)
    resultats = list(qs.select_related('inscription__eleve'))

    resultats.sort(key=lambda r: (
        -r.moyenne_generale,
        r.inscription.eleve.nom,
        r.inscription.eleve.prenom,
    ))
    attribuer_rangs(resultats)  # ex æquo : même rang (1, 2, 2, 4)

    if resultats:
        ResultatTrimestreLycee.objects.bulk_update(resultats, ['rang'], batch_size=200)

    return len(resultats)


# =====================================================================
# 3. STATISTIQUES
# =====================================================================

def stats_classe(classe, trimestre, resultat_eleve=None):
    """Calcule les statistiques d'une classe pour un trimestre."""
    qs = ResultatTrimestreLycee.objects.filter(
        inscription__classe=classe, trimestre=trimestre
    )

    moyenne_classe = qs.aggregate(Avg('moyenne_generale'))['moyenne_generale__avg'] or 0
    nb = qs.count()

    meilleur = qs.select_related('inscription__eleve').order_by('-moyenne_generale').first()

    stats = {
        'moyenne_classe': round(moyenne_classe, 2),
        'effectif': nb,
    }

    if resultat_eleve:
        stats['rang'] = resultat_eleve.rang
        stats['moyenne_eleve'] = resultat_eleve.moyenne_generale

    if meilleur:
        stats['moyenne_premier'] = float(meilleur.moyenne_generale)
        stats['nom_premier'] = (
            f"{meilleur.inscription.eleve.prenom} "
            f"{meilleur.inscription.eleve.nom}"
        )

    return stats


# =====================================================================
# 4. GÉNÉRATION PDF DU BULLETIN
# =====================================================================
def _get_police_arabe():
    """Vérifie si la police arabe est disponible."""
    try:
        from reportlab.pdfbase import pdfmetrics
        pdfmetrics.getFont('Amiri')
        return 'Amiri'
    except Exception:
        return 'Helvetica'


def generer_bulletin_lycee_pdf(eleve, inscription, resultat, stats, trimestre):
    """
    Génère le PDF du bulletin d'un élève du lycée.
    ✅ Calqué sur generer_bulletin_pdf_eleve (fondamental).
    ✅ Affiche le nom arabe UNIQUEMENT si l'école est franco-arabe.
    """
    from .models import EcoleInfo

    ecole = EcoleInfo.get_solo()
    classe = inscription.classe
    annee = inscription.annee_scolaire
    afficher_arabe = ecole.est_franco_arabe

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=3.2 * cm, bottomMargin=1.8 * cm,
    )

    story = []
    styles = getSampleStyleSheet()

    NOIR = colors.HexColor('#000000')
    GRIS_FONCE = colors.HexColor('#333333')
    GRIS = colors.HexColor('#666666')
    GRIS_CLAIR = colors.HexColor('#cccccc')
    BLANC = colors.HexColor('#ffffff')

    # ============================================================
    # STYLES DE BASE
    # ============================================================
    style_titre = ParagraphStyle(
        'Titre', parent=styles['Title'],
        fontSize=16, alignment=TA_CENTER, textColor=NOIR, spaceAfter=6
    )
    style_soustitre = ParagraphStyle(
        'SousTitre', parent=styles['Normal'],
        fontSize=11, alignment=TA_CENTER, textColor=NOIR, spaceAfter=10
    )
    style_section = ParagraphStyle(
        'Section', parent=styles['Heading2'],
        fontSize=11, textColor=NOIR, spaceBefore=10, spaceAfter=6
    )
    style_normal = ParagraphStyle(
        'Normal2', parent=styles['Normal'],
        fontSize=8, textColor=NOIR
    )
    style_normal_bold = ParagraphStyle(
        'Normal2Bold', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica-Bold', textColor=NOIR
    )
    style_label = ParagraphStyle(
        'Label', parent=styles['Normal'],
        fontSize=10, fontName='Helvetica-Bold', textColor=NOIR
    )
    style_valeur = ParagraphStyle(
        'Valeur', parent=styles['Normal'],
        fontSize=11, fontName='Helvetica-Bold',
        alignment=TA_RIGHT, textColor=NOIR
    )

    # ============================================================
    # TITRE
    # ============================================================
    story.append(Paragraph("BULLETIN DE NOTES", style_titre))
    story.append(Paragraph(
        f"{trimestre} — Année scolaire {annee.anneeScolaire}",
        style_soustitre
    ))

    # ============================================================
    # INFOS ÉLÈVE
    # ============================================================
    serie_affichee = classe.get_serie_display() if classe.serie else "Commune Générale"

    serie_affichee = classe.get_serie_display() if classe.serie else "Commune Générale"

    infos_eleve_data = [
        [
            Paragraph(f"<b>Matricule :</b> {eleve.matricule}", style_normal),
        ],
        [
            Paragraph(f"<b>Nom et Prénom :</b> {eleve.nom} {eleve.prenom}", style_normal),
            Paragraph(f"<b>Niveau :</b> {classe.get_niveau_display()}", style_normal),
        ],
        [
            Paragraph(f"<b>Classe :</b> {classe.nom}", style_normal),
            Paragraph(f"<b>Série :</b> {serie_affichee}", style_normal),
        ],
    ]
    infos_table = Table(infos_eleve_data, colWidths=[10 * cm, 6 * cm])
    infos_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(infos_table)
    story.append(Spacer(1, 10))

    # ============================================================
    # TABLEAU DES NOTES
    # ============================================================
    if resultat and resultat.details.exists():
        note_style = ParagraphStyle(
            'NoteStyle', parent=style_normal,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER, textColor=NOIR,
        )

        if afficher_arabe:
            # ====================================================
            # VERSION FRANCO-ARABE (8 colonnes)
            # ✅ EXACTEMENT COMME DANS pdf_generator.py
            # ====================================================
            style_arabe = _style_arabe(parent_style=style_normal, size=10)

            notes_data = [[
                Paragraph("<b>Matières</b>", style_normal_bold),
                Paragraph("<b>Coef</b>", style_normal_bold),
                Paragraph("<b>N.classe</b>", style_normal_bold),
                Paragraph("<b>N.cp×2</b>", style_normal_bold),
                Paragraph("<b>N.générales.</b>", style_normal_bold),
                Paragraph("<b>N.coef.</b>", style_normal_bold),
                Paragraph("<b>مواد</b>", style_arabe),                  # ✅ titre arabe DÉJÀ préparé
                Paragraph("<b>Appréciations</b>", style_normal_bold),
            ]]

            for detail in resultat.details.all():
                notes_data.append([
                    Paragraph(f"{detail.matiere.nom}", style_normal),
                    Paragraph(f"{detail.coefficient:g}", style_normal),
                    Paragraph(f"{detail.note_classe:.2f}", style_normal),
                    Paragraph(f"{detail.note_composition * 2:.2f}", style_normal),
                    Paragraph(f"{detail.moyenne_matiere:.2f}", note_style),
                    Paragraph(f"{detail.moyenne_coefficientee:.2f}", style_normal),
                    Paragraph(
                        _preparer_arabe(detail.matiere.nom_arabe) or '-',   # ✅ préparé
                        style_arabe
                    ),
                    Paragraph(f"{detail.appreciation or '-'}", style_normal),
                ])

            # ✅ MÊMES largeurs que le fondamental (adaptées au lycée)
            notes_table = Table(
                notes_data,
                colWidths=[3.3 * cm, 1.2 * cm, 1.6 * cm, 1.7 * cm,
                          1.5 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm]
            )
            notes_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), GRIS_CLAIR),
                ('TEXTCOLOR', (0, 0), (-1, 0), BLANC),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),           # Matières : gauche
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),          # Coef : droite
                ('ALIGN', (2, 0), (-2, -1), 'CENTER'),        # Notes : centré
                ('ALIGN', (-1, 0), (-1, -1), 'LEFT'),         # ✅ Appréciations : gauche
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 0), (-1, -1), 7.5),
                ('GRID', (0, 0), (-1, -1), 0.4, NOIR),
                ('BACKGROUND', (0, 1), (-1, -1), BLANC),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
            ]))

        else:
            # ====================================================
            # VERSION CLASSIQUE (7 colonnes, sans Arabe)
            # ====================================================
            notes_data = [[
                Paragraph("<b>Matières</b>", style_normal_bold),
                Paragraph("<b>Coef</b>", style_normal_bold),
                Paragraph("<b>N.classe</b>", style_normal_bold),
                Paragraph("<b>N.cp×2</b>", style_normal_bold),
                Paragraph("<b>N.générales</b>", style_normal_bold),
                Paragraph("<b>N.coeff</b>", style_normal_bold),
                Paragraph("<b>Appréciations.</b>", style_normal_bold),
            ]]

            for detail in resultat.details.all():
                notes_data.append([
                    Paragraph(f"{detail.matiere.nom}", style_normal),
                    Paragraph(f"{detail.coefficient:g}", style_normal),
                    Paragraph(f"{detail.note_classe:.2f}", style_normal),
                    Paragraph(f"{detail.note_composition * 2:.2f}", style_normal),
                    Paragraph(f"{detail.moyenne_matiere:.2f}", note_style),
                    Paragraph(f"{detail.moyenne_coefficientee:.2f}", style_normal),
                    Paragraph(f"{detail.appreciation or '-'}", style_normal),
                ])

            notes_table = Table(
                notes_data,
                colWidths=[4.5 * cm, 1.3 * cm, 1.8 * cm, 1.8 * cm,
                          2 * cm, 2 * cm, 2.1 * cm]
            )
            notes_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), GRIS_CLAIR),
                ('TEXTCOLOR', (0, 0), (-1, 0), BLANC),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (-1, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 0), (-1, -1), 7.5),
                ('GRID', (0, 0), (-1, -1), 0.4, NOIR),
                ('BACKGROUND', (0, 1), (-1, -1), BLANC),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
            ]))

        story.append(notes_table)
        story.append(Spacer(1, 10))

    # ============================================================
    # RÉSULTATS DU TRIMESTRE (identique au fondamental)
    # ============================================================
    if resultat:
        moyenne_classe_val = stats.get('moyenne_classe', 0) or 0
        effectif_val = stats.get('effectif', 0) or 0

        if resultat.rang == 1:
            rang_txt = "1er"
        else:
            rang_txt = f"{resultat.rang}ème" if resultat.rang else "—"

        moyenne_premier = stats.get('moyenne_premier', 0)
        nom_premier = stats.get('nom_premier', '')

        resultats_data = [
            [Paragraph("<b>Total :</b>", style_label),
             Paragraph(f"<b>{resultat.total_notes_coefficientees:.2f}</b>", style_valeur)],
            [Paragraph("<b>Somme des coefficients :</b>", style_label),
             Paragraph(f"<b>{resultat.total_coefficients:g}</b>", style_valeur)],
            [Paragraph("<b>Moyenne générale :</b>", style_label),
             Paragraph(f"<b>{resultat.moyenne_generale:.2f}</b>", style_valeur)],
            [Paragraph("<b>Rang :</b>", style_label),
             Paragraph(
                 f"<b>{rang_txt}</b> <font size=8 color='#666666'>"
                 f"sur {effectif_val} élève{'s' if effectif_val > 1 else ''}</font>",
                 style_valeur)],
            [Paragraph("<b>Moyenne du 1er de la classe :</b>", style_label),
             Paragraph(
                 f"<b>{moyenne_premier:.2f}</b>"
                 + (f" <font size=8 color='#666666'>({nom_premier})</font>"
                    if nom_premier else ""),
                 style_valeur)],
            [Paragraph("<b>Moyenne de la classe :</b>", style_label),
             Paragraph(f"<b>{moyenne_classe_val:.2f}</b>", style_valeur)],
        ]
        resultats_table = Table(resultats_data, colWidths=[8 * cm, 8 * cm])
        resultats_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), BLANC),
            ('BOX', (0, 0), (-1, -1), 0.5, NOIR),
            ('LINEBELOW', (0, 0), (-1, -2), 0.3, GRIS_CLAIR),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(resultats_table)
        story.append(Spacer(1, 12))

    # ============================================================
    # APPRÉCIATION GÉNÉRALE
    # ============================================================
    if resultat:
        story.append(Paragraph("Appréciation générale", style_section))

        if resultat.moyenne_generale >= 16:
            appreciation = "Excellent travail ! Félicitations pour vos résultats brillants."
        elif resultat.moyenne_generale >= 14:
            appreciation = "Très bon travail. Continuez sur cette lancée."
        elif resultat.moyenne_generale >= 12:
            appreciation = "Bon travail. Quelques efforts supplémentaires vous permettront de progresser."
        elif resultat.moyenne_generale >= 10:
            appreciation = "Travail satisfaisant. Vous pouvez faire mieux en vous appliquant davantage."
        else:
            appreciation = "Des efforts sont nécessaires. N'hésitez pas à demander de l'aide."

        story.append(Paragraph(appreciation, style_normal))
        story.append(Spacer(1, 20))

    # ============================================================
    # SIGNATURES
    # ============================================================
    signatures_data = [
        [Paragraph("<b>LE DIRECTEUR</b>", style_normal),
         Paragraph("<b>LES PARENTS</b>", style_normal)],
        [Paragraph("<br/><br/>_________________", style_normal),
         Paragraph("<br/><br/>_________________", style_normal)],
    ]
    signatures_table = Table(signatures_data, colWidths=[8 * cm, 8 * cm])
    signatures_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(signatures_table)

    # ============================================================
    # GÉNÉRATION
    # ============================================================
    entete_callback = _faire_callback_entete(ecole)
    doc.build(story, onFirstPage=entete_callback, onLaterPages=entete_callback)
    buffer.seek(0)
    return buffer


# =====================================================================
# 5. BULLETINS DE TOUTE UNE CLASSE (PDF fusionné)
# =====================================================================

def generer_bulletins_classe_lycee_pdf(classe, trimestre):
    """
    Génère un PDF contenant les bulletins de TOUS les élèves d'une classe.

    ✅ FIX: stats par classe utilisées pour chaque bulletin individuel.
    ✅ FIX: gestion d'erreur par élève (un élève en échec ne bloque pas les autres).
    ✅ FIX: log des erreurs pour débogage.

    Returns:
        Buffer (BytesIO) contenant le PDF fusionné, ou None si aucun résultat.
    """
    from PyPDF2 import PdfMerger
    import tempfile
    import os
    import logging

    logger = logging.getLogger(__name__)

    # ============================================================
    # 1. RÉCUPÉRATION DES RÉSULTATS
    # ============================================================
    resultats = list(
        ResultatTrimestreLycee.objects.filter(
            inscription__classe=classe,
            trimestre=trimestre,
        )
        .select_related('inscription__eleve')
        .prefetch_related('details__matiere')
        .order_by('-moyenne_generale')
    )

    if not resultats:
        logger.info(
            "Aucun résultat pour la classe %s au trimestre %s",
            classe.nom, trimestre
        )
        return None

    # ============================================================
    # 2. STATISTIQUES GLOBALES DE LA CLASSE
    #    (moyenne classe, moyenne du 1er, nom du 1er)
    # ============================================================
    stats = stats_classe(classe, trimestre)

    # ============================================================
    # 3. GÉNÉRATION DES BULLETINS
    # ============================================================
    merger = PdfMerger()
    temp_files = []
    nb_succes = 0
    nb_echecs = 0

    try:
        for resultat in resultats:
            inscription = resultat.inscription
            eleve = inscription.eleve

            try:
                buffer = generer_bulletin_lycee_pdf(
                    eleve=eleve,
                    inscription=inscription,
                    resultat=resultat,
                    stats=stats,
                    trimestre=trimestre,
                )

                temp_file = tempfile.NamedTemporaryFile(
                    delete=False, suffix='.pdf'
                )
                temp_file.write(buffer.getvalue())
                temp_file.close()
                temp_files.append(temp_file.name)
                merger.append(temp_file.name)
                nb_succes += 1

            except Exception as e:
                # ✅ FIX: un élève en échec ne bloque pas les autres
                nb_echecs += 1
                logger.error(
                    "Erreur génération bulletin pour %s %s (%s) : %s",
                    eleve.nom, eleve.prenom, eleve.matricule, e,
                    exc_info=True,
                )
                continue

        # ============================================================
        # 4. FUSION
        # ============================================================
        if nb_succes == 0:
            logger.error(
                "Aucun bulletin généré pour la classe %s au trimestre %s",
                classe.nom, trimestre,
            )
            return None

        output = io.BytesIO()
        merger.write(output)
        merger.close()

        # ============================================================
        # 5. NETTOYAGE DES FICHIERS TEMPORAIRES
        # ============================================================
        for f in temp_files:
            try:
                os.unlink(f)
            except OSError as e:
                # ✅ FIX: log au lieu de passer silencieusement
                logger.warning("Impossible de supprimer %s : %s", f, e)

        output.seek(0)

        if nb_echecs > 0:
            logger.warning(
                "Bulletins générés pour %s : %d succès, %d échec(s)",
                classe.nom, nb_succes, nb_echecs,
            )

        return output

    except Exception as e:
        # ✅ Nettoyage en cas d'erreur critique
        for f in temp_files:
            try:
                os.unlink(f)
            except OSError:
                pass

        logger.exception(
            "Erreur critique génération bulletins classe %s : %s",
            classe.nom, e,
        )
        # ✅ FIX: `raise` au lieu de `raise e` (préserve la stack trace)
        raise


# =====================================================================
# 6. GESTION DES PAIEMENTS DU LYCÉE (VERSION UNIQUE)
# =====================================================================

def calculer_echeances_lycee(ecole, classe, annee_scolaire):
    """
    Retourne la liste des échéances de scolarité pour le lycée.
    ✅ Miroir EXACT de calculer_echeances() du fondamental.
    """
    montant_annuel = Decimal(str(classe.frais_scolarite or 0))
    mode = ecole.mode_frais_scolarite

    echeances = []

    # MENSUEL : 9 versements
    if mode == 'mensuel':
        montants = _repartir(montant_annuel, 9)
        mois_scolaires = [
            (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre'),
            (1, 'Janvier'), (2, 'Février'), (3, 'Mars'),
            (4, 'Avril'), (5, 'Mai'), (6, 'Juin'),
        ]
        for i, (mois, nom) in enumerate(mois_scolaires, start=1):
            annee = (
                annee_scolaire.get_annee_debut() if mois >= 10
                else annee_scolaire.get_annee_fin()
            )
            echeances.append({
                'numero': i, 'libelle': nom, 'mois': mois, 'annee': annee,
                'montant': montants[i - 1], 'deja_paye': False,
            })

    # TRIMESTRIEL : 3 versements
    elif mode == 'trimestriel':
        montants = _repartir(montant_annuel, 3)
        trimestres = [
            (1, '1er Trimestre'), (2, '2ème Trimestre'), (3, '3ème Trimestre'),
        ]
        for i, (num, nom) in enumerate(trimestres, start=1):
            echeances.append({
                'numero': i, 'libelle': nom, 'mois': None,
                'annee': annee_scolaire.get_annee_debut(),
                'montant': montants[i - 1], 'deja_paye': False,
            })

    # TRANCHES : N versements
    elif mode == 'tranches':
        nb = ecole.nombre_tranches or 4
        montants = _repartir(montant_annuel, nb)
        for i in range(1, nb + 1):
            if i == 1:
                libelle = "1ère tranche"
            elif i == 2:
                libelle = "2ème tranche"
            elif i == 3:
                libelle = "3ème tranche"
            else:
                libelle = f"{i}ème tranche"
            echeances.append({
                'numero': i, 'libelle': libelle, 'mois': None,
                'annee': annee_scolaire.get_annee_debut(),
                'montant': montants[i - 1], 'deja_paye': False,
            })

    # ANNUEL : 1 versement
    elif mode == 'annuel':
        echeances.append({
            'numero': 1, 'libelle': "Année complète", 'mois': None,
            'annee': annee_scolaire.get_annee_debut(),
            'montant': montant_annuel, 'deja_paye': False,
        })

    # UNIQUE : 1 versement pour tout le cursus
    elif mode == 'unique':
        echeances.append({
            'numero': 1, 'libelle': "Scolarité complète (cursus)", 'mois': None,
            'annee': annee_scolaire.get_annee_debut(),
            'montant': montant_annuel, 'deja_paye': False,
        })

    return echeances


def _deja_paye_avant_lycee(inscription, est_inscription):
    """
    True si les frais « uniques » (inscription ou scolarité) ont été payés
    ENTIÈREMENT lors d'inscriptions antérieures (comparaison de MONTANT :
    un acompte ne suffit pas ; frais non configurés = tout paiement compte).
    """
    if not inscription or not inscription.eleve_id:
        return False
    annee_courante = inscription.annee_scolaire.anneeScolaire
    autres = InscriptionLycee.objects.filter(
        eleve=inscription.eleve,
        annee_scolaire__anneeScolaire__lt=annee_courante,
    ).exclude(pk=inscription.pk).select_related('classe')

    paye_total = Decimal('0')
    du_max = Decimal('0')
    for ins in autres:
        montants = ins.paiements.filter(est_inscription=est_inscription).values_list('montant', flat=True)
        paye_total += sum((Decimal(str(m)) for m in montants), Decimal('0'))
        du = ins.classe.frais_inscription if est_inscription else ins.classe.frais_scolarite
        du_max = max(du_max, Decimal(str(du or 0)))

    return paye_total > 0 and (du_max <= 0 or paye_total >= du_max)


def _frais_inscription_deja_paye_lycee(inscription):
    return _deja_paye_avant_lycee(inscription, True)


def _scolarite_unique_deja_payee_lycee(inscription):
    return _deja_paye_avant_lycee(inscription, False)


def calculer_montants_inscription_lycee(inscription):
    """
    Calcule les montants attendus/payés pour une inscription du lycée.
    ✅ Miroir EXACT de calculer_montants_inscription() du fondamental.
    ✅ Gère le cas spécial de l'élève ORIENTÉ (tout gratuit).
    """
    from .models import EcoleInfo

    if not inscription:
        return {}

    ecole = EcoleInfo.get_solo()
    classe = inscription.classe
    annee = inscription.annee_scolaire
    eleve = inscription.eleve

    # ================================================================
    # ✅ CAS SPÉCIAL : ÉLÈVE ORIENTÉ → tout gratuit
    # ================================================================
    if eleve.statut == 'oriente':
        return {
            'mode_frais_inscription': ecole.get_mode_frais_inscription_display(),
            'mode_frais_scolarite': ecole.get_mode_frais_scolarite_display(),
            'mode_frais_inscription_code': ecole.mode_frais_inscription,
            'mode_frais_scolarite_code': ecole.mode_frais_scolarite,
            'nombre_tranches': ecole.nombre_tranches,
            'frais_inscription_historique': False,
            'frais_inscription_attendu': Decimal('0'),
            'frais_inscription_paye': Decimal('0'),
            'frais_inscription_reste': Decimal('0'),
            'paiements_inscription_liste': [],
            'scolarite_attendue': Decimal('0'),
            'scolarite_payee': Decimal('0'),
            'scolarite_reste': Decimal('0'),
            'detail_echeances': [],
            'nb_echeances': 0,
            'nb_echeances_payees': 0,
            'total_attendu': Decimal('0'),
            'total_paye': Decimal('0'),
            'reste': Decimal('0'),
            'pourcentage_frais': 0,
            'pourcentage_scolarite': 0,
            'pourcentage_total': 0,
            'historique_paiements': [],
            'est_oriente': True,
            'statut_libelle': eleve.get_statut_display() if hasattr(eleve, 'get_statut_display') else "Orienté par l'État",
        }

    # ================================================================
    # 1. FRAIS D'INSCRIPTION
    # ================================================================
    frais_inscription_attendu = Decimal('0')
    frais_inscription_paye = Decimal('0')

    if ecole.mode_frais_inscription == 'annuel':
        frais_inscription_attendu = Decimal(str(classe.frais_inscription or 0))
    elif ecole.mode_frais_inscription == 'unique':
        deja_paye = _frais_inscription_deja_paye_lycee(inscription)
        if not deja_paye:
            frais_inscription_attendu = Decimal(str(classe.frais_inscription or 0))

    paiements_inscription_liste = list(
        inscription.paiements.filter(est_inscription=True).order_by('date_paiement', 'id_paiement')
    )
    for p in paiements_inscription_liste:
        frais_inscription_paye += Decimal(str(p.montant))

    # ================================================================
    # 2. SCOLARITÉ
    # ================================================================
    echeances = calculer_echeances_lycee(ecole, classe, annee)

    if ecole.mode_frais_scolarite == 'unique':
        if _scolarite_unique_deja_payee_lycee(inscription):
            for ech in echeances:
                ech['deja_paye'] = True
                ech['montant'] = Decimal('0')

    paiements_scolarite = list(
        inscription.paiements.filter(est_inscription=False).order_by('date_paiement', 'id_paiement')
    )

    # ================================================================
    # 3. ASSOCIER LES PAIEMENTS AUX ÉCHÉANCES (par montant)
    # ================================================================
    allocations = _allouer_paiements(echeances, paiements_scolarite)

    detail_echeances = []
    scolarite_attendue = Decimal('0')
    scolarite_payee = Decimal('0')
    nb_echeances_payees = 0

    for ech, alloc in zip(echeances, allocations):
        montant_attendu = ech['montant']
        scolarite_attendue += montant_attendu

        if ech['deja_paye']:
            montant_paye = montant_attendu
            paiements_lies = []
            nb_echeances_payees += 1
        else:
            montant_paye = alloc['paye']
            paiements_lies = alloc['paiements_lies']
            if montant_attendu > 0 and montant_paye >= montant_attendu:
                nb_echeances_payees += 1

        scolarite_payee += montant_paye

        reste_echeance = (
            max(Decimal('0'), montant_attendu - montant_paye)
            if not ech['deja_paye'] else Decimal('0')
        )

    # ================================================================
    # 4. TOTAUX
    # ================================================================
    total_attendu = frais_inscription_attendu + scolarite_attendue
    total_paye = frais_inscription_paye + scolarite_payee
    reste = max(Decimal('0'), total_attendu - total_paye)

    pourcentage_frais = (
        min(100, int(frais_inscription_paye / frais_inscription_attendu * 100))
        if frais_inscription_attendu > 0 else 0
    )
    pourcentage_scolarite = (
        min(100, int(scolarite_payee / scolarite_attendue * 100))
        if scolarite_attendue > 0 else 0
    )
    pourcentage_total = (
        min(100, int(total_paye / total_attendu * 100))
        if total_attendu > 0 else 0
    )

    historique_paiements = inscription.paiements.order_by('-date_paiement', '-id_paiement')

    return {
        'mode_frais_inscription': ecole.get_mode_frais_inscription_display(),
        'mode_frais_scolarite': ecole.get_mode_frais_scolarite_display(),
        'mode_frais_inscription_code': ecole.mode_frais_inscription,
        'mode_frais_scolarite_code': ecole.mode_frais_scolarite,
        'nombre_tranches': ecole.nombre_tranches,
        'frais_inscription_historique': inscription.frais_inscription_historique,
        'est_oriente': False,
        'statut_libelle': eleve.get_statut_display() if hasattr(eleve, 'get_statut_display') else 'Payant',

        'frais_inscription_attendu': frais_inscription_attendu,
        'frais_inscription_paye': frais_inscription_paye,
        'frais_inscription_reste': max(Decimal('0'), frais_inscription_attendu - frais_inscription_paye),
        'paiements_inscription_liste': paiements_inscription_liste,

        'scolarite_attendue': scolarite_attendue,
        'scolarite_payee': scolarite_payee,
        'scolarite_reste': max(Decimal('0'), scolarite_attendue - scolarite_payee),
        'detail_echeances': detail_echeances,
        'nb_echeances': len(detail_echeances),
        'nb_echeances_payees': nb_echeances_payees,

        'total_attendu': total_attendu,
        'total_paye': total_paye,
        'reste': reste,

        'pourcentage_frais': pourcentage_frais,
        'pourcentage_scolarite': pourcentage_scolarite,
        'pourcentage_total': pourcentage_total,

        'historique_paiements': historique_paiements,
    }


def calculer_montants_paiement_lycee(inscription):
    """
    Calcule les montants attendus/payés pour une inscription au lycée.
    (Fonction simplifiée, conservée pour compatibilité)
    """
    return calculer_montants_inscription_lycee(inscription)


# =====================================================================
# 7. GÉNÉRATION PDF EMPLOI DU TEMPS LYCÉE
# =====================================================================

def generer_emploi_temps_lycee_pdf(classe, annee_scolaire, ecole, plages, jours, creneaux_par_case):
    """
    Génère le PDF de l'emploi du temps d'une classe du lycée.
    """
    from datetime import date
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=0.5 * cm, bottomMargin=1 * cm,
    )

    story = []
    styles = getSampleStyleSheet()

    style_titre = ParagraphStyle(
        'Titre', parent=styles['Title'],
        fontSize=16, alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=6, spaceBefore=15,
    )
    style_sous_titre = ParagraphStyle(
        'SousTitre', parent=styles['Normal'],
        fontSize=11, alignment=TA_CENTER,
        textColor=colors.HexColor('#7f8c8d'),
        spaceAfter=15,
    )
    style_cellule = ParagraphStyle(
        'Cellule', parent=styles['Normal'],
        fontSize=9, alignment=TA_CENTER, leading=11,
    )
    style_case_remplie = ParagraphStyle(
        'CaseRemplie', parent=styles['Normal'],
        fontSize=9, alignment=TA_CENTER,
        leading=11, textColor=colors.HexColor('#155724'),
    )
    style_pied = ParagraphStyle(
        'Pied', parent=styles['Normal'],
        fontSize=8, alignment=TA_CENTER, textColor=colors.grey,
    )

    from .utils.pdf_generator import _construire_entete_3_zones
    story.append(_construire_entete_3_zones(ecole, styles))
    story.append(Spacer(1, 15))

    story.append(Paragraph("EMPLOI DU TEMPS — LYCÉE", style_titre))

    niveau = classe.get_niveau_display()
    serie = classe.get_serie_display() if classe.serie else "Commune Générale"
    story.append(Paragraph(
        f"Classe : <b>{classe.nom}</b> "
        f"({niveau} — {serie}) — "
        f"Année scolaire : <b>{annee_scolaire}</b>",
        style_sous_titre
    ))

    header = ['Heure']
    for jour_num, jour_nom in jours:
        header.append(jour_nom)

    data = [header]

    for plage in plages:
        heure_txt = f"{plage.heure_debut.strftime('%H:%M')}\n{plage.heure_fin.strftime('%H:%M')}"
        if plage.libelle:
            heure_txt += f"\n({plage.libelle})"

        ligne = [Paragraph(heure_txt, style_cellule)]

        for jour_num, jour_nom in jours:
            if plage.est_pause:
                ligne.append(Paragraph('<i>— Pause —</i>', style_cellule))
            else:
                creneau = creneaux_par_case.get((jour_num, plage.pk))
                if creneau and creneau.matiere:
                    texte = f"<b>{creneau.matiere.nom}</b>"
                    if creneau.salle:
                        texte += f"<br/><font size='7'>{creneau.salle}</font>"
                    ligne.append(Paragraph(texte, style_case_remplie))
                else:
                    ligne.append(Paragraph("", style_cellule))

        data.append(ligne)

    largeur_totale = doc.width
    largeur_heure = 2.5 * cm
    largeur_jour = (largeur_totale - largeur_heure) / len(jours)
    col_widths = [largeur_heure] + [largeur_jour] * len(jours)

    table = Table(data, colWidths=col_widths, repeatRows=1)

    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8e44ad')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#ecf0f1')),
        ('FONTSIZE', (0, 1), (0, -1), 8),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
    ]

    for i, plage in enumerate(plages, start=1):
        if plage.est_pause:
            table_styles.append(
                ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fff3cd'))
            )
        else:
            for j, (jour_num, jour_nom) in enumerate(jours, start=1):
                creneau = creneaux_par_case.get((jour_num, plage.pk))
                if creneau and creneau.matiere:
                    table_styles.append(
                        ('BACKGROUND', (j, i), (j, i), colors.HexColor('#d4edda'))
                    )

    table.setStyle(TableStyle(table_styles))
    story.append(table)

    story.append(Spacer(1, 15))
    story.append(Paragraph(
        f"Document généré le {date.today().strftime('%d/%m/%Y')}",
        style_pied
    ))

    story.append(Spacer(1, 25))
    sig_data = [
        [Paragraph("<b>Le Directeur</b>", style_cellule),
         Paragraph("<b>Le Censeur / Surveillant Général</b>", style_cellule)],
        [Paragraph("<br/><br/>_________________", style_cellule),
         Paragraph("<br/><br/>_________________", style_cellule)],
    ]
    sig_table = Table(sig_data, colWidths=[doc.width / 2, doc.width / 2])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer


def generer_carte_lycee_pdf(
    eleve,
    inscription,
    ecole,
    qr_code_image,
    couleur_hex="#1f43b9",
    nom_fond="bleu_vagues.jpg"
):
    """Génère la carte scolaire du Lycée avec le même design que le Fondamental."""
    import io
    import os
    import base64

    from django.conf import settings
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader

    buffer = io.BytesIO()

    width = 85.6 * mm
    height = 54 * mm

    c = canvas.Canvas(buffer, pagesize=(width, height))

    # =====================================================
    # COULEURS
    # =====================================================
    bleu_principal = colors.HexColor(couleur_hex)
    bleu_fonce = colors.HexColor("#123A7A")
    fond = colors.HexColor("#F8FAFD")

    # =====================================================
    # FOND
    # =====================================================
    c.setFillColor(fond)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    chemin_fond = os.path.join(settings.BASE_DIR, "ecole", "static", "img", "fonds", nom_fond)

    if os.path.exists(chemin_fond):
        try:
            c.drawImage(chemin_fond, 0, 0, width=width, height=height)
        except: pass

    # =====================================================
    # LOGO EN HAUT GAUCHE
    # =====================================================
    if ecole.logo and hasattr(ecole.logo, "path"):
        try:
            c.drawImage(ecole.logo.path, 4*mm, height - 12*mm, width=7*mm, height=7*mm, preserveAspectRatio=True, mask="auto")
        except: pass

    # =====================================================
    # ENTÊTE
    # =====================================================
    c.setFillColor(bleu_fonce)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(14*mm, height - 7*mm, (ecole.nom or "LYCEE")[:30].upper())

    c.setFont("Helvetica", 6)
    c.setFillColor(colors.black)
    # ✅ Adapté pour le Lycée
    c.drawCentredString(width/2, height - 10.5*mm, f"CARTE SCOLAIRE {inscription.annee_scolaire.anneeScolaire}")

    c.setStrokeColor(colors.lightgrey)
    c.line(14*mm, height - 12*mm, width - 5*mm, height - 12*mm)

    # =====================================================
    # PHOTO (avec cadre arrondi)
    # =====================================================
    photo_x = 5*mm
    photo_y = 18*mm
    photo_w = 20*mm
    photo_h = 21*mm
    rayon = 2*mm

    c.setStrokeColor(bleu_principal) 
    c.setLineWidth(1.5)
    c.roundRect(photo_x - 1, photo_y - 1, photo_w + 2, photo_h + 2, rayon, stroke=1, fill=0)

    if eleve.photo and hasattr(eleve.photo, "path"):
        try:
            c.saveState()
            p = c.beginPath()
            p.roundRect(photo_x, photo_y, photo_w, photo_h, rayon)
            c.clipPath(p, stroke=0, fill=0)
            c.drawImage(eleve.photo.path, photo_x, photo_y, width=photo_w, height=photo_h, preserveAspectRatio=True, mask="auto")
            c.restoreState()
        except: pass

    # Cachet sur la photo
    if ecole.cachet_ecole and hasattr(ecole.cachet_ecole, "path"):
        try:
            c.drawImage(ecole.cachet_ecole.path, photo_x + 13*mm, photo_y - 1*mm, width=6*mm, height=6*mm, preserveAspectRatio=True, mask="auto")
        except: pass

    # Matricule
    c.setFillColor(bleu_principal)
    c.roundRect(photo_x, photo_y - 5*mm, photo_w, 4.5*mm, 1*mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(photo_x + photo_w/2, photo_y - 3.2*mm, str(eleve.matricule))

    # =====================================================
    # INFORMATIONS ÉLÈVE (Adaptées aux champs du Lycée)
    # =====================================================
    info_x = 30*mm
    y = height - 17*mm

    def ligne(libelle, valeur):
        nonlocal y
        c.setFillColor(bleu_fonce)
        c.setFont("Helvetica-Bold", 6)
        c.drawString(info_x, y, libelle)

        c.setFillColor(colors.black)
        c.setFont("Helvetica", 6)
        c.drawString(info_x + 16*mm, y, str(valeur))

        y -= 3.6*mm

    ligne("Nom :", eleve.nom.upper())
    ligne("Prenom :", eleve.prenom)
    ligne("Classe :", inscription.classe.nom)
    ligne("Sexe :", eleve.get_sexe_display() or "-")
    ligne("Né(e) le :", eleve.date_naissance.strftime("%d/%m/%Y"))
    ligne("Lieu :", eleve.lieu_naissance or "-")
    ligne("Père :", eleve.pere or '-')
    ligne("Mère :", eleve.mere or '-')

    # =====================================================
    # GRAND LOGO À DROITE
    # =====================================================
    if ecole.logo and hasattr(ecole.logo, "path"):
        try:
            c.drawImage(ecole.logo.path, width - 20*mm, height - 30*mm, width=16*mm, height=16*mm, preserveAspectRatio=True, mask="auto")
        except: pass

    # =====================================================
    # QR CODE
    # =====================================================
    qr_x = width - 19*mm
    qr_y = 8*mm
    qr_size = 14*mm

    try:
        qr_base64 = qr_code_image.split(",")[1] if "," in qr_code_image else qr_code_image
        qr_data = base64.b64decode(qr_base64)
        qr_buffer = io.BytesIO(qr_data)
        qr_image = ImageReader(qr_buffer)

        c.setStrokeColor(bleu_principal) 
        c.setLineWidth(1)
        c.roundRect(qr_x - 1, qr_y - 1, qr_size + 2, qr_size + 2, 1*mm, stroke=1, fill=0)
        c.drawImage(qr_image, qr_x, qr_y, width=qr_size, height=qr_size)
    except: pass

    # =====================================================
    # SIGNATURE
    # =====================================================
    if ecole.signature_directeur and hasattr(ecole.signature_directeur, "path"):
        try:
            c.drawImage(ecole.signature_directeur.path, 9*mm, 7.5*mm, width=16*mm, height=5*mm, preserveAspectRatio=True, mask="auto")
        except: pass

    c.setFillColor(bleu_fonce)
    c.setFont("Helvetica-Oblique", 5)
    c.drawString(12*mm, 6*mm, "Le Directeur") 

    # =====================================================
    # CONTACT ECOLE
    # =====================================================
    c.setFillColor(bleu_fonce)
    c.rect(0, 0, width, 4*mm, fill=1, stroke=0)

    contact = ""
    if hasattr(ecole, "telephone") and ecole.telephone:
        contact += f"Tel: {ecole.telephone}"
    if hasattr(ecole, "email") and ecole.email:
        if contact: contact += " | "
        contact += ecole.email
    if hasattr(ecole, "adresse") and ecole.adresse:
        if contact: contact += " | "
        contact += ecole.adresse
    elif hasattr(ecole, "ville") and ecole.ville:
        if contact: contact += " | "
        contact += ecole.ville

    c.setFont("Helvetica", 4.8)
    c.setFillColor(colors.white)
    c.drawCentredString(width/2, 1.4*mm, contact[:90])

    c.save()
    buffer.seek(0)
    return buffer


def generer_planche_cartes_lycee_pdf(inscriptions, ecole, couleur_hex='#6f42c1', nom_fond='bleu_vagues.jpg'):
    """
    Génère une planche A4 contenant 8 cartes scolaires (2x4) pour le Lycée.
    """
    import io
    import os
    import base64
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from django.conf import settings
    from .utils.qr_code import generer_qr_code_base64

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    card_w = 85.6 * mm
    card_h = 54 * mm
    gap = 8 * mm 

    margin_x = (width - (card_w * 2) - gap) / 2
    margin_y = (height - (card_h * 4) - (gap * 3)) / 2

    chemin_fond = os.path.join(settings.BASE_DIR, "ecole", "static", "img", "fonds", nom_fond)

    bleu_principal = colors.HexColor(couleur_hex)
    bleu_fonce = colors.HexColor("#123A7A")
    fond = colors.HexColor("#F8FAFD")

    for index, inscription in enumerate(inscriptions):
        col = index % 2
        row = (index // 2) % 4
        
        if index > 0 and index % 8 == 0:
            c.showPage()
            row = 0
            col = 0

        x = margin_x + (col * (card_w + gap))
        y = height - margin_y - ((row + 1) * (card_h + gap)) + gap
        eleve = inscription.eleve
        
        # 1. FOND
        c.setFillColor(fond)
        c.rect(x, y, card_w, card_h, fill=1, stroke=0)
        if os.path.exists(chemin_fond):
            try:
                c.drawImage(chemin_fond, x, y, width=card_w, height=card_h, preserveAspectRatio=False, mask='auto')
            except: pass

        # 2. LOGO
        if ecole.logo and hasattr(ecole.logo, "path"):
            try:
                c.drawImage(ecole.logo.path, x + 4*mm, y + card_h - 12*mm, width=7*mm, height=7*mm, preserveAspectRatio=True, mask="auto")
            except: pass

        # 3. ENTÊTE
        c.setFillColor(bleu_fonce)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x + 14*mm, y + card_h - 7*mm, (ecole.nom or "LYCEE")[:30].upper())

        c.setFont("Helvetica", 6)
        c.setFillColor(colors.black)
        c.drawCentredString(x + card_w/2, y + card_h - 10.5*mm, f"CARTE SCOLAIRE {inscription.annee_scolaire.anneeScolaire}")

        c.setStrokeColor(colors.lightgrey)
        c.line(x + 14*mm, y + card_h - 12*mm, x + card_w - 5*mm, y + card_h - 12*mm)

        # 4. PHOTO
        photo_x = x + 5*mm
        photo_y = y + 18*mm
        photo_w = 20*mm
        photo_h = 21*mm
        rayon = 2*mm

        c.setStrokeColor(bleu_principal) 
        c.setLineWidth(1.5)
        c.roundRect(photo_x - 1, photo_y - 1, photo_w + 2, photo_h + 2, rayon, stroke=1, fill=0)

        if eleve.photo and hasattr(eleve.photo, "path"):
            try:
                c.saveState()
                p = c.beginPath()
                p.roundRect(photo_x, photo_y, photo_w, photo_h, rayon)
                c.clipPath(p, stroke=0, fill=0)
                c.drawImage(eleve.photo.path, photo_x, photo_y, width=photo_w, height=photo_h, preserveAspectRatio=True, mask="auto")
                c.restoreState()
            except: pass

        # Cachet
        if ecole.cachet_ecole and hasattr(ecole.cachet_ecole, "path"):
            try:
                c.drawImage(ecole.cachet_ecole.path, photo_x + 13*mm, photo_y - 1*mm, width=6*mm, height=6*mm, preserveAspectRatio=True, mask="auto")
            except: pass

        # Matricule
        c.setFillColor(bleu_principal)
        c.roundRect(photo_x, photo_y - 5*mm, photo_w, 4.5*mm, 1*mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(photo_x + photo_w/2, photo_y - 3.2*mm, str(eleve.matricule))

        # 5. INFOS
        info_x = x + 30*mm
        info_y = y + card_h - 17*mm

        def ligne(libelle, valeur):
            nonlocal info_y
            c.setFillColor(bleu_fonce)
            c.setFont("Helvetica-Bold", 6)
            c.drawString(info_x, info_y, libelle)

            c.setFillColor(colors.black)
            c.setFont("Helvetica", 6)
            c.drawString(info_x + 16*mm, info_y, str(valeur))

            info_y -= 3.6*mm

        ligne("Nom :", eleve.nom.upper())
        ligne("Prenom :", eleve.prenom)
        ligne("Classe :", inscription.classe.nom)
        ligne("Sexe :", eleve.get_sexe_display() or "-")
        ligne("Né(e) le :", eleve.date_naissance.strftime("%d/%m/%Y"))
        ligne("Lieu :", eleve.lieu_naissance or "-")
        ligne("Père :", eleve.pere or '-')
        ligne("Mère :", eleve.mere or '-')

        # 6. GRAND LOGO
        if ecole.logo and hasattr(ecole.logo, "path"):
            try:
                c.drawImage(ecole.logo.path, x + card_w - 20*mm, y + card_h - 30*mm, width=16*mm, height=16*mm, preserveAspectRatio=True, mask="auto")
            except: pass

        # 7. QR CODE
        texte_qr = f"{eleve.prenom} {eleve.nom.upper()} - {eleve.matricule}"
        qr_code_image = generer_qr_code_base64(texte_qr)
        
        qr_x = x + card_w - 19*mm
        qr_y = y + 8*mm
        qr_size = 14*mm

        try:
            qr_base64 = qr_code_image.split(",")[1] if "," in qr_code_image else qr_code_image
            qr_data = base64.b64decode(qr_base64)
            qr_buffer = io.BytesIO(qr_data)
            qr_image = ImageReader(qr_buffer)

            c.setStrokeColor(bleu_principal) 
            c.setLineWidth(1)
            c.roundRect(qr_x - 1, qr_y - 1, qr_size + 2, qr_size + 2, 1*mm, stroke=1, fill=0)
            c.drawImage(qr_image, qr_x, qr_y, width=qr_size, height=qr_size)
        except: pass

        # 8. SIGNATURE
        if ecole.signature_directeur and hasattr(ecole.signature_directeur, "path"):
            try:
                c.drawImage(ecole.signature_directeur.path, x + 9*mm, y + 7.5*mm, width=16*mm, height=5*mm, preserveAspectRatio=True, mask="auto")
            except: pass

        c.setFillColor(bleu_fonce)
        c.setFont("Helvetica-Oblique", 5)
        c.drawString(x + 12*mm, y + 6*mm, "Le Directeur") 

        # 9. CONTACT
        c.setFillColor(bleu_fonce)
        c.rect(x, y, card_w, 4*mm, fill=1, stroke=0)

        contact = ""
        if hasattr(ecole, "telephone") and ecole.telephone:
            contact += f"Tel: {ecole.telephone}"
        if hasattr(ecole, "email") and ecole.email:
            if contact: contact += " | "
            contact += ecole.email
        if hasattr(ecole, "adresse") and ecole.adresse:
            if contact: contact += " | "
            contact += ecole.adresse
        elif hasattr(ecole, "ville") and ecole.ville:
            if contact: contact += " | "
            contact += ecole.ville

        c.setFont("Helvetica", 4.8)
        c.setFillColor(colors.white)
        c.drawCentredString(x + card_w/2, y + 1.4*mm, contact[:90])

    c.save()
    buffer.seek(0)
    return buffer