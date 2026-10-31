# ecole/utils/pdf_generator.py
import io
import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, LongTable, TableStyle, Paragraph, Spacer,
    PageBreak, Table,
)
from reportlab.platypus import Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.conf import settings
from ..cycles import Cycle, arrondir_moyenne


# =====================================================================
# ✅ ENREGISTREMENT DES POLICES ARABES (Amiri)
# =====================================================================

def _get_fonts_dir():
    """Retourne le dossier des polices (dev ou PyInstaller)."""
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base = settings.BASE_DIR
    return os.path.join(base, 'ecole', 'static', 'fonts')


_ARABIC_FONT_REGISTERED = False
_ARABIC_FONT_PATH = None


def _enregistrer_police_arabe():
    """Enregistre la police Amiri auprès de ReportLab (une seule fois)."""
    global _ARABIC_FONT_REGISTERED, _ARABIC_FONT_PATH

    if _ARABIC_FONT_REGISTERED:
        return True

    try:
        fonts_dir = _get_fonts_dir()
        font_path = os.path.join(fonts_dir, 'Amiri.ttf')

        if not os.path.exists(font_path):
            print(f"⚠️  Police Amiri introuvable : {font_path}")
            return False

        pdfmetrics.registerFont(TTFont('Amiri', font_path))
        pdfmetrics.registerFontFamily(
            'Amiri',
            normal='Amiri',
            bold='Amiri',
            italic='Amiri',
            boldItalic='Amiri',
        )

        _ARABIC_FONT_REGISTERED = True
        _ARABIC_FONT_PATH = font_path
        print(f"✅ Police Amiri enregistrée : {font_path}")
        return True

    except Exception as e:
        print(f"❌ Erreur enregistrement Amiri : {e}")
        return False


# ✅ APPEL AU CHARGEMENT DU MODULE
_enregistrer_police_arabe()

def _style_arabe(parent_style=None, size=None, alignment=None):
    """Retourne un ParagraphStyle configuré pour l'arabe."""
    # ✅ Taille par défaut augmentée
    base_size = size or (parent_style.fontSize + 4 if parent_style else 14)

    # ✅ Alignement par défaut à droite
    if alignment == 'center':
        align = TA_CENTER
    elif alignment == 'left':
        align = TA_LEFT
    else:
        align = TA_RIGHT

    font_name = 'Amiri' if _ARABIC_FONT_REGISTERED else 'Helvetica'

    return ParagraphStyle(
        'ArabicStyle',
        parent=parent_style,
        fontName=font_name,
        fontSize=base_size,
        leading=base_size * 1.2,   
        alignment=align,
        wordWrap='RTL',          
        splitLongWords=0,  
    )


def _preparer_arabe(texte):
    """Prépare un texte arabe pour ReportLab."""
    if not texte:
        return ''

    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        reshaped = arabic_reshaper.reshape(texte)
        return get_display(reshaped)
    except ImportError:
        return texte[::-1]


# =====================================================================
# HELPERS
# =====================================================================

def _calculer_largeurs_colonnes(data, largeur_disponible):
    """Calcule automatiquement la largeur de chaque colonne."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    nb_colonnes = len(data[0])
    largeurs_min = []
    poids = []

    for col_idx in range(nb_colonnes):
        longueur_max = 0
        for row in data:
            if col_idx < len(row):
                cell = row[col_idx]
                if hasattr(cell, 'text'):
                    texte = cell.text
                else:
                    texte = str(cell)
                for mot in texte.split():
                    longueur = stringWidth(mot, 'Helvetica', 5.5)
                    if longueur > longueur_max:
                        longueur_max = longueur
        largeurs_min.append(longueur_max + 4)

    POIDS_MIN = 18
    for i, lmin in enumerate(largeurs_min):
        poids.append(max(lmin, POIDS_MIN))

    total_poids = sum(poids)
    if total_poids == 0:
        return [largeur_disponible / nb_colonnes] * nb_colonnes

    return [(p / total_poids) * largeur_disponible for p in poids]


def _construire_entete_3_zones(ecole, styles):
    """Construit l'en-tête en 3 zones (gauche, centre=logo, droite)."""
    style_gauche = ParagraphStyle(
        'Gauche', parent=styles['Normal'],
        fontSize=8, alignment=TA_LEFT,
        textColor=colors.HexColor('#2c3e50'), leading=10,
    )
    style_droite = ParagraphStyle(
        'Droite', parent=styles['Normal'],
        fontSize=8, alignment=TA_RIGHT,
        textColor=colors.HexColor('#2c3e50'), leading=10,
    )

    gauche_html = ""
    if ecole and ecole.circonscription:
        gauche_html += f"{ecole.circonscription}<br/>"
    if ecole and ecole.nom:
        gauche_html += f"<b>{ecole.nom}</b><br/>"
    if ecole and ecole.telephone:
        gauche_html += f"Tel : {ecole.telephone}"
    gauche_cell = Paragraph(gauche_html or "", style_gauche)

    logo_cell = Paragraph("", styles['Normal'])
    if ecole and ecole.logo:
        try:
            logo_path = ecole.logo.path
            if os.path.exists(logo_path):
                logo_img = RLImage(logo_path, width=2*cm, height=2*cm)
                logo_img.hAlign = 'CENTER'
                logo_cell = logo_img
        except (ValueError, AttributeError):
            pass

    droite_html = ""
    if ecole and ecole.republique:
        droite_html += f"<b>{ecole.republique}</b><br/>"
    if ecole and ecole.devise:
        droite_html += f"{ecole.devise}"
    droite_cell = Paragraph(droite_html or "", style_droite)

    header_table = Table(
        [[gauche_cell, logo_cell, droite_cell]],
        colWidths=[8 * cm, 4 * cm, 8 * cm]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LINEBELOW', (0, 0), (-1, -1), 1.5, colors.HexColor('#3498db')),
    ]))

    return header_table


def _dessiner_entete_ecole(canvas, doc, ecole):
    """Callback dessiné à chaque page par ReportLab."""
    canvas.saveState()

    largeur, hauteur = A4
    marge = 1.5 * cm
    haut = hauteur - 0.8 * cm
    centre_x = largeur / 2
    hauteur_entete = 2.8 * cm

    y_gauche = haut
    canvas.setFillColor(colors.HexColor('#2c3e50'))
    canvas.setFont("Helvetica", 8)
    if ecole and ecole.circonscription:
        canvas.drawString(marge, y_gauche, ecole.circonscription[:45])
    y_gauche -= 0.4 * cm

    canvas.setFont("Helvetica-Bold", 8)
    if ecole and ecole.nom:
        canvas.drawString(marge, y_gauche, ecole.nom[:45])
    y_gauche -= 0.4 * cm

    canvas.setFont("Helvetica", 7)
    if ecole and ecole.telephone:
        canvas.drawString(marge, y_gauche, f"Tel: {ecole.telephone}")

    logo_path = None
    if ecole and ecole.logo:
        try:
            logo_path = ecole.logo.path
            if not os.path.exists(logo_path):
                logo_path = None
        except (ValueError, AttributeError):
            logo_path = None

    if logo_path:
        try:
            logo_size = 2.2 * cm
            logo_x = centre_x - (logo_size / 2)
            logo_y = haut - logo_size + 0.4 * cm
            canvas.drawImage(
                logo_path, logo_x, logo_y,
                width=logo_size, height=logo_size,
                preserveAspectRatio=True, mask='auto'
            )
        except Exception:
            pass

    y_droite = haut
    canvas.setFillColor(colors.HexColor('#2c3e50'))
    canvas.setFont("Helvetica-Bold", 9)
    if ecole and ecole.republique:
        canvas.drawRightString(largeur - marge, y_droite, ecole.republique[:40])
    y_droite -= 0.5 * cm

    canvas.setFont("Helvetica", 8)
    if ecole and ecole.devise:
        canvas.drawRightString(largeur - marge, y_droite, ecole.devise[:40])

    y_ligne = hauteur - hauteur_entete
    canvas.setStrokeColor(colors.HexColor('#3498db'))
    canvas.setLineWidth(1)
    canvas.line(marge, y_ligne, largeur - marge, y_ligne)

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawCentredString(centre_x, 1 * cm, f"Page {doc.page}")

    canvas.restoreState()


def _faire_callback_entete(ecole):
    """Retourne une fonction callback pour ReportLab qui capture `ecole`."""
    def callback(canvas, doc):
        _dessiner_entete_ecole(canvas, doc, ecole)
    return callback


# =====================================================================
# BULLETIN TRIMESTRIEL (2e cycle)
# =====================================================================
def generer_bulletin_pdf_eleve(
    eleve, inscription, resultat, class_stats, annee_scolaire, trimestre,
    total_moyennes_coefficientees=0, total_coefficients=0,
    moyenne_generale=0, rang_affiche="-", effectif_classe=0,
    moyenne_premier=0, nom_premier_eleve="",
):
    """
    Génère le PDF du bulletin trimestriel d'un élève (2e cycle).
    Version NOIR ET BLANC, fond blanc.
    ✅ La colonne Arabe s'affiche uniquement si l'école est Franco-arabe.
    """
    from ecole.models import EcoleInfo

    ecole = EcoleInfo.get_solo()

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

    # ✅ Déterminer si on affiche l'arabe
    afficher_arabe = ecole.est_franco_arabe if ecole else True

    # ============================================================
    # STYLES
    # ============================================================
    style_titre = ParagraphStyle(
        'Titre', parent=styles['Title'],
        fontSize=16, alignment=TA_CENTER, textColor=NOIR, spaceAfter=6
    )
    style_soustitre = ParagraphStyle(
        'SousTitre', parent=styles['Normal'],
        fontSize=11, alignment=TA_CENTER, textColor=GRIS, spaceAfter=10
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
        f"{trimestre} — Année scolaire {annee_scolaire}",
        style_soustitre
    ))

    # ============================================================
    # INFOS ÉLÈVE
    # ============================================================
    infos_eleve_data = [
        [
            Paragraph(f"<b>Prénoms et noms :</b> {eleve.prenomEleve} {eleve.nomEleve.upper()}", style_normal),
            Paragraph(f"<b>Matricule :</b> {eleve.matricule}", style_normal),
        ],
        [
            Paragraph(f"<b>Classe :</b> {inscription.classe.nomClasse}", style_normal),
            Paragraph(f"<b>Sexe :</b> {eleve.get_sexe_display() or '-'}", style_normal),
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
    # TABLEAU DES NOTES (avec ou sans colonne Arabe)
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
            # ====================================================
            style_arabe = _style_arabe(parent_style=style_normal, size=10)

            notes_data = [[
                Paragraph("<b>Matières</b>", style_normal_bold),
                Paragraph("<b>Coef</b>", style_normal_bold),
                Paragraph("<b>N.classe</b>", style_normal_bold),
                Paragraph("<b>N.cp×2</b>", style_normal_bold),
                Paragraph("<b>N.générales.</b>", style_normal_bold),
                Paragraph("<b>N.coef.</b>", style_normal_bold),
                Paragraph("<b>مواد</b>", style_arabe),
                Paragraph("<b>Appréciations</b>", style_normal_bold),
            ]]

            for detail in resultat.details.all():
                notes_data.append([
                    Paragraph(f"{detail.matiere.nomMatiere}", style_normal),
                    Paragraph(f"{detail.coef:g}", style_normal),
                    Paragraph(f"{detail.note_classe:.2f}", style_normal),
                    Paragraph(f"{detail.note_compo:.2f}", style_normal),
                    Paragraph(f"{detail.moyenne_generale:.2f}", note_style),
                    Paragraph(f"{detail.moyenne_coefficientee:.2f}", style_normal),
                    Paragraph(
                        _preparer_arabe(detail.matiere.nomArabe) or '-',
                        style_arabe
                    ),
                    Paragraph(f"{detail.appreciation or '-'}", style_normal),
                ])

            notes_table = Table(
                notes_data,
                colWidths=[3.3 * cm, 1.2 * cm, 1.6 * cm, 1.7 * cm,
                          1.5 * cm, 1.5 * cm, 2.5 * cm, 2.5 * cm]
            )
            notes_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), GRIS_CLAIR),
                ('TEXTCOLOR', (0, 0), (-1, 0), BLANC),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('ALIGN', (2, 0), (-2, -1), 'CENTER'),
                ('ALIGN', (-1, 0), (-1, -1), 'LEFT'),
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
                    Paragraph(f"{detail.matiere.nomMatiere}", style_normal),
                    Paragraph(f"{detail.coef:g}", style_normal),
                    Paragraph(f"{detail.note_classe:.2f}", style_normal),
                    Paragraph(f"{detail.note_compo:.2f}", style_normal),
                    Paragraph(f"{detail.moyenne_generale:.2f}", note_style),
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
    # RÉSULTATS DU TRIMESTRE
    # ============================================================
    if resultat:
        moyenne_classe_val = class_stats.get('moyenne_classe', 0) or 0
        effectif_val = class_stats.get('effectif', 0) or 0

        if rang_affiche == "1er":
            rang_txt = "1er (garçon)"
        elif rang_affiche == "1ère":
            rang_txt = "1ère (fille)"
        elif rang_affiche != "-":
            rang_txt = rang_affiche
        else:
            rang_txt = "—"

        resultats_data = [
            [Paragraph("<b>Total :</b>", style_label),
             Paragraph(f"<b>{total_moyennes_coefficientees:.2f}</b>", style_valeur)],
            [Paragraph("<b>Somme des coefficients :</b>", style_label),
             Paragraph(f"<b>{total_coefficients:g}</b>", style_valeur)],
            [Paragraph("<b>Moyenne générale :</b>", style_label),
             Paragraph(f"<b>{moyenne_generale:.2f}</b>", style_valeur)],
            [Paragraph("<b>Rang :</b>", style_label),
             Paragraph(
                 f"<b>{rang_txt}</b> <font size=8 color='#666666'>"
                 f"sur {effectif_classe} élève{'s' if effectif_classe > 1 else ''}</font>",
                 style_valeur)],
            [Paragraph("<b>Moyenne du 1er de la classe :</b>", style_label),
             Paragraph(
                 f"<b>{moyenne_premier:.2f}</b>"
                 + (f" <font size=8 color='#666666'>({nom_premier_eleve})</font>"
                    if nom_premier_eleve else ""),
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

        if moyenne_generale >= 16:
            appreciation = "Excellent travail ! Félicitations pour vos résultats brillants."
        elif moyenne_generale >= 14:
            appreciation = "Très bon travail. Continuez sur cette lancée."
        elif moyenne_generale >= 12:
            appreciation = "Bon travail. Quelques efforts supplémentaires vous permettront de progresser."
        elif moyenne_generale >= 10:
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
# CERTIFICAT DE FRÉQUENTATION
# =====================================================================

def generer_certificat_frequentation_pdf(eleve, inscription, ecole, annee_scolaire, date_jour):
    """Génère le PDF du certificat de fréquentation scolaire."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2*cm, bottomMargin=2*cm, leftMargin=2*cm, rightMargin=2*cm
    )

    styles = getSampleStyleSheet()

    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'],
                                   fontSize=10, fontName='Helvetica-Bold', leading=12)
    title_style = ParagraphStyle('TitleStyle', parent=styles['Normal'],
                                  fontSize=14, fontName='Helvetica-Bold',
                                  alignment=TA_CENTER, spaceAfter=15, spaceBefore=5)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'],
                                 fontSize=12, fontName='Helvetica', leading=20,
                                 alignment=TA_JUSTIFY, spaceAfter=10)
    note_style = ParagraphStyle('NoteStyle', parent=body_style, fontSize=10, leading=15)
    right_style = ParagraphStyle('RightStyle', parent=styles['Normal'],
                                  fontSize=11, fontName='Helvetica', alignment=TA_RIGHT,
                                  leading=15)
    signature_style = ParagraphStyle('SignatureStyle', parent=styles['Normal'],
                                      fontSize=12, fontName='Helvetica-Bold',
                                      alignment=TA_RIGHT, leading=15)

    elements = []

    gauche = f"""
        {ecole.ministere or ''}<br/>
        {ecole.circonscription or ''}<br/>
        ******************************<br/>
        <font size=9>TEL : {ecole.telephone or ''}</font>
    """
    droite = f"""
        {ecole.republique or ''}<br/>
        {ecole.devise or ''}<br/>
        ******************************
    """

    header_table = Table(
        [[Paragraph(gauche, header_style), Paragraph(droite, header_style)]],
        colWidths=[9*cm, 9*cm]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 1*cm))

    elements.append(Paragraph("<u>CERTIFICAT DE FREQUENTATION SCOLAIRE</u>", title_style))
    elements.append(Spacer(1, 0.6*cm))

    classe_nom = inscription.classe.nomClasse
    nom_complet = f"{eleve.prenomEleve} {eleve.nomEleve.upper()}"
    date_naiss = eleve.dateNaiss.strftime('%d/%m/%Y')
    lieu_naiss = eleve.lieuNaiss or ''
    pere = eleve.pere or 'Non renseigné'
    mere = eleve.mere or 'Non renseigné'

    corps = f"""
    Je soussigné, Directeur de la : <b>{ecole.nom}</b>.<br/>
    Certifie que le(la) nommé(e) : <b>{nom_complet}</b><br/>
    Né(e) le : <b>{date_naiss}</b> à <b>{lieu_naiss}</b><br/>
    Fils(fille) de : <b>{pere}</b><br/>
    Et de : <b>{mere}</b><br/>
    Est élève dans mon établissement où il(elle) est inscrit(e) en classe de « <b>{classe_nom}</b> »<br/>
    Pour l'année scolaire « <b>{annee_scolaire}</b> » sous le N° MLE : <b>{eleve.matricule}</b><br/>
    Fait pour servir et valoir ce que de droit.
    """
    elements.append(Paragraph(corps, body_style))
    elements.append(Spacer(1, 0.5*cm))

    elements.append(Paragraph(
        "<i>NB : à ne délivrer que pour la constitution de dossiers administratifs.</i>",
        note_style
    ))
    elements.append(Spacer(1, 1.2*cm))

    lieu = ecole.ville or ''
    date_str = date_jour.strftime('%d/%m/%Y')
    elements.append(Paragraph(f"Fait à {lieu}, le {date_str}", right_style))
    elements.append(Spacer(1, 0.8*cm))
    elements.append(Paragraph("<u>Le Directeur</u>", signature_style))
    elements.append(Spacer(1, 1.2*cm))
    elements.append(Paragraph("<i>Cachet et signature</i>", right_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# =====================================================================
# PROPOSITION DE PASSAGE
# =====================================================================

def generer_proposition_passage_pdf(classe, annee_scolaire, ecole, lignes, stats=None):
    """Génère le PDF du tableau de proposition de passage."""
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        topMargin=0.5*cm, bottomMargin=0.5*cm,
        leftMargin=0.5*cm, rightMargin=0.5*cm
    )
    styles = getSampleStyleSheet()
    elements = []

    NOIR = colors.HexColor('#000000')
    GRIS_CLAIR = colors.HexColor('#f0f0f0')

    cycle_style = ParagraphStyle(
        'CycleStyle', parent=styles['Normal'],
        fontSize=10, fontName='Helvetica-Bold',
        alignment=TA_CENTER, textColor=NOIR
    )

    est_1er_cycle = classe.cycle == '1er'

    style_entete_gauche = ParagraphStyle(
        'EnteteGauche', parent=styles['Normal'],
        fontSize=8, alignment=TA_LEFT, textColor=NOIR, leading=10,
    )
    style_entete_centre = ParagraphStyle(
        'EnteteCentre', parent=styles['Normal'],
        fontSize=11, fontName='Helvetica-Bold',
        alignment=TA_CENTER, textColor=NOIR, leading=14,
    )
    style_entete_droite = ParagraphStyle(
        'EnteteDroite', parent=styles['Normal'],
        fontSize=8, alignment=TA_RIGHT, textColor=NOIR, leading=10,
    )

    gauche_html = ""
    if ecole.republique:
        gauche_html += f"{ecole.republique}<br/>"
    if ecole.ministere:
        gauche_html += f"{ecole.ministere}<br/>"
    if ecole.academie:
        gauche_html += f"Académie : {ecole.academie}<br/>"
    if ecole.circonscription:
        gauche_html += f"CAP : {ecole.circonscription}<br/>"
    gauche_cell = Paragraph(gauche_html or "", style_entete_gauche)

    centre_html = (
        "  TABLEAU DE DONNEES ET DE PROPOSITION<br/>"
        " DE PASSAGE, DE REDOUBLEMENT ET D'EXCLUSION<br/>"
        "<b>Moyenne annuelle par ordre de merite</b>"
    )
    centre_cell = Paragraph(centre_html, style_entete_centre)

    droite_html = ""
    if ecole.republique:
        droite_html += f"<b>{ecole.republique}</b><br/>"
    if ecole.devise:
        droite_html += f"{ecole.devise}"
    droite_cell = Paragraph(droite_html or "", style_entete_droite)

    entete_table = Table(
        [[gauche_cell, centre_cell, droite_cell]],
        colWidths=[doc.width * 0.33, doc.width * 0.34, doc.width * 0.33]
    )
    entete_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(entete_table)
    elements.append(Spacer(1, 0.2*cm))

    elements.append(Paragraph(
        "<hr style='border-top: 1.5px solid black;'/>",
        styles['Normal']
    ))
    elements.append(Spacer(1, 0.2*cm))

    info_droite = ParagraphStyle(
        'InfoDroite', parent=styles['Normal'],
        fontSize=10, alignment=TA_RIGHT, textColor=NOIR, leading=13,
    )
    info_gauche = ParagraphStyle(
        'InfoGauche', parent=styles['Normal'],
        fontSize=10, alignment=TA_LEFT, textColor=NOIR, leading=13,
    )

    ligne_info = Table(
        [[
            Paragraph(f" {ecole.nom}<br/><b> </b> {ecole.telephone}", info_gauche),
            Paragraph(
                f"<b>CLASSE DE :</b> {classe.nomClasse}<br/>"
                f"Année Scolaire : {annee_scolaire}",
                info_droite
            ),
        ]],
        colWidths=[doc.width * 0.5, doc.width * 0.5]
    )
    ligne_info.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(ligne_info)
    elements.append(Spacer(1, 0.3*cm))

    libelle_cycle = "PREMIER CYCLE" if est_1er_cycle else "DEUXIEME CYCLE"
    elements.append(Paragraph(f"<u>{libelle_cycle}</u>", cycle_style))
    elements.append(Spacer(1, 0.3*cm))

    headers = [
        "N°", "Prénoms", "Nom", "Sexe",
        "Jour", "Mois", "Année", "Lieu Nais.",
        "N° délivr.", "Date délivr.", "Père", "Mère",
        "Scol\n1°c",
    ]
    if not est_1er_cycle:
        headers.append("Scol\n2°c")
        headers.append("Scol\nTot")

    headers += ["1er\nRed", "2è\nRed", "3è\nRed", "Année\nRecrut", "Ecole\nRecrut"]
    if not est_1er_cycle:
        headers.append("Ecole\nfin 1c")
        headers.append("Année\n7a")

    headers += ["Ecole\nAn der.", "Moy-\nAnn", "Prop-\nCons", "Déc\nD/CAP"]

    data = [headers]

    style_cellule_2lignes = ParagraphStyle(
        'Cellule2Lignes', parent=styles['Normal'],
        fontSize=5, leading=6.5, textColor=NOIR,
        alignment=TA_CENTER, wordWrap='CJK',
    )
    style_cellule_gauche = ParagraphStyle(
        'CelluleGauche', parent=styles['Normal'],
        fontSize=5, leading=6.5, textColor=NOIR,
        alignment=TA_LEFT, wordWrap='CJK',
    )

    for ligne in lignes:
        e = ligne['eleve']

        if e.sexe == 'M':
            sexe_affiche = 'M'
        elif e.sexe == 'F':
            sexe_affiche = 'F'
        else:
            sexe_affiche = ''

        row = [
            str(ligne['rang']),
            Paragraph(e.prenomEleve or '', style_cellule_gauche),
            Paragraph(e.nomEleve or '', style_cellule_gauche),
            sexe_affiche,
            str(e.dateNaiss.day),
            str(e.dateNaiss.month),
            str(e.dateNaiss.year),
            Paragraph(e.lieuNaiss or '', style_cellule_gauche),
            Paragraph(e.numero_acte_naissance or '', style_cellule_gauche),
            e.date_delivrance_acte.strftime('%d/%m/%Y') if e.date_delivrance_acte else '',
            Paragraph(e.pere or '', style_cellule_gauche),
            Paragraph(e.mere or '', style_cellule_gauche),
            str(e.scolarite_1er_cycle),
        ]
        if not est_1er_cycle:
            row.append(str(e.scolarite_2e_cycle))
            row.append(str(e.scolarite_totale))

        row += [
            e.redoublement_1 or '',
            e.redoublement_2 or '',
            e.redoublement_3 or '',
            Paragraph(e.annee_recrutement or '', style_cellule_2lignes),
            Paragraph(e.ecole_recrutement or '', style_cellule_gauche),
        ]
        if not est_1er_cycle:
            row.append(Paragraph(e.ecole_fin_1er_cycle or '', style_cellule_gauche))
            row.append(e.annee_entree_7eme or '')

        row += [
            Paragraph(e.ecole_an_dernier or '', style_cellule_gauche),
            f"{ligne['moyenne_annuelle']:.2f}" if ligne['moyenne_annuelle'] is not None else '',
            '',
            '',
        ]
        data.append(row)

    col_widths = _calculer_largeurs_colonnes(data, doc.width)

    table = LongTable(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 5.5),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 5.5),
        ('GRID', (0, 0), (-1, -1), 0.4, NOIR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_CLAIR]),
        ('LEFTPADDING', (0, 0), (-1, -1), 1.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1.5),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    elements.append(table)

    elements.append(PageBreak())
    elements.append(Spacer(1, 0.5*cm))

    if stats is None:
        stats = {}

    recap_data = [
        ["FLUX / Evènements", "Garçons", "Filles", "TOTAL Elèves"],
        ["PASSANTS",
         str(stats.get('passants_garcons', '')),
         str(stats.get('passants_filles', '')),
         str(stats.get('passants_total', ''))],
        ["REDOUBLANTS",
         str(stats.get('redoublants_garcons', '')),
         str(stats.get('redoublants_filles', '')),
         str(stats.get('redoublants_total', ''))],
        ["EXCLUS", "", "", ""],
        ["TOTAL Elèves",
         str(stats.get('total_garcons', '')),
         str(stats.get('total_filles', '')),
         str(stats.get('total_eleves', ''))],
    ]
    recap_table = Table(
        recap_data,
        colWidths=[5*cm, 3*cm, 3*cm, 3*cm],
        hAlign='CENTER'
    )
    recap_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, NOIR),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_CLAIR),
        ('BACKGROUND', (0, -1), (-1, -1), GRIS_CLAIR),
    ]))

    elements.append(Paragraph(
        "<b><u>TABLEAU RECAPITALATIF</u></b>",
        ParagraphStyle('RecapTitle', parent=styles['Normal'],
                       alignment=TA_CENTER, fontSize=11, textColor=NOIR)
    ))
    elements.append(Spacer(1, 0.3*cm))
    elements.append(recap_table)
    elements.append(Spacer(1, 0.5*cm))

    nb_style = ParagraphStyle(
        'NBStyle', parent=styles['Normal'],
        fontSize=8, leading=11, textColor=NOIR
    )
    nb_texte = """
    <b>NB :</b><br/>
    1- Sont exclus les élèves qui n'ont pas d'enregistrements complets c-a-d sans DOSSIER SCOLAIRE
    (sans renseignements complets) et ceux qui sont en limite de scolarité et d'âge.<br/>
    2- On rappelle qu'un élève n'a droit qu'à deux (2) redoublants sur des années d'études différentes dans son cycle d'études.<br/>
    3- L'élève ne peut doubler qu'une seule fois son année d'études au 2er Cycle, exceptée la 9ème Année d'études
    s'il n'a jamais doublé avant la 9ème Année.<br/>
    4- L'élève ne peut doubler que 3 années d'étude différentes entre le 1er cycle et le 2e cycle. Soit 2 redoublement
    au cycle 1 et 1 au cycle 2 ou inversement.<br/>
    5- Les données du tableau doivent être conformes à celles des dossiers scolaires en état civil et en scolarité.
    """
    elements.append(Paragraph(nb_texte, nb_style))
    elements.append(Spacer(1, 1*cm))

    right_style = ParagraphStyle(
        'RightPP', parent=styles['Normal'],
        fontSize=10, alignment=TA_RIGHT, textColor=NOIR
    )
    elements.append(Paragraph("Fait à Bamako, Le ...../....../20.....", right_style))
    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph("<b><u>Le (La) Directeur(trice)</u></b>", styles['Normal']))
    elements.append(Paragraph(
        f"Prénoms et Nom : {ecole.nom_directeur or ''}",
        styles['Normal']
    ))
    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph("<i>(Cachet et Signature)</i>", right_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# =====================================================================
# BULLETIN MENSUEL (1er cycle) — AVEC ARABE
# =====================================================================
def generer_bulletin_mensuel_pdf_eleve(
    eleve, inscription, resultat, class_stats, ecole,
    annee_scolaire, composition,
    total_notes=0, moyenne_notes=0, nb_matieres_notees=0,
    rang_affiche="-", effectif_classe=0,
    moyenne_premier=0, nom_premier_eleve="",
):
    """
    Génère le PDF du bulletin mensuel d'un élève (1er cycle).
    Note sur 10, sans coefficient.
    Version NOIR ET BLANC, fond blanc.
    ✅ La colonne Arabe s'affiche uniquement si l'école est Franco-arabe.
    """
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

    # ✅ Déterminer si on affiche l'arabe
    afficher_arabe = ecole.est_franco_arabe if ecole else True

    # ============================================================
    # STYLES
    # ============================================================
    style_titre = ParagraphStyle(
        'Titre', parent=styles['Title'],
        fontSize=16, alignment=TA_CENTER, textColor=NOIR, spaceAfter=6
    )
    style_soustitre = ParagraphStyle(
        'SousTitre', parent=styles['Normal'],
        fontSize=11, alignment=TA_CENTER, textColor=GRIS, spaceAfter=10
    )
    style_section = ParagraphStyle(
        'Section', parent=styles['Heading2'],
        fontSize=11, textColor=NOIR, spaceBefore=10, spaceAfter=6
    )
    style_normal = ParagraphStyle(
        'Normal2', parent=styles['Normal'],
        fontSize=9, textColor=NOIR
    )
    style_normal_bold = ParagraphStyle(
        'Normal2Bold', parent=styles['Normal'],
        fontSize=9, fontName='Helvetica-Bold', textColor=NOIR
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
    story.append(Paragraph("BULLETIN MENSUEL", style_titre))
    nom_mois = composition.get_mois_display() if composition else ''
    story.append(Paragraph(
        f"Composition de {nom_mois} — Année scolaire {annee_scolaire}",
        style_soustitre
    ))

    # ============================================================
    # INFOS ÉLÈVE
    # ============================================================
    infos_eleve_data = [
        [
            Paragraph(f"<b>Prénoms et noms :</b> {eleve.prenomEleve} {eleve.nomEleve.upper()}", style_normal),
            Paragraph(f"<b>Matricule :</b> {eleve.matricule}", style_normal),
        ],
        [
            Paragraph(f"<b>Classe :</b> {inscription.classe.nomClasse}", style_normal),
            Paragraph(f"<b>Sexe :</b> {eleve.get_sexe_display() or '-'}", style_normal),
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
    # TABLEAU DES NOTES (avec ou sans colonne Arabe)
    # ============================================================
    if resultat and resultat.details.exists():
        note_style = ParagraphStyle(
            'NoteStyle', parent=style_normal,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER, textColor=NOIR,
        )

        if afficher_arabe:
            # ====================================================
            # VERSION FRANCO-ARABE (avec colonne Arabe)
            # ====================================================
            style_arabe = _style_arabe(parent_style=style_normal, size=11)

            notes_data = [[
                Paragraph("<b>Matières</b>", style_normal_bold),
                Paragraph("<b>Notes</b>", style_normal_bold),
                Paragraph("<b>مواد</b>", style_arabe),
                Paragraph("<b>Appréciations</b>", style_normal_bold),
            ]]

            for detail in resultat.details.all():
                notes_data.append([
                    Paragraph(f"{detail.matiere.nomMatiere}", style_normal),
                    Paragraph(f"{detail.note:.2f}", note_style),
                    Paragraph(
                        _preparer_arabe(detail.matiere.nomArabe) or '-',
                        style_arabe
                    ),
                    Paragraph(f"{detail.appreciation or '-'}", style_normal),
                ])

            notes_table = Table(
                notes_data,
                colWidths=[5.5 * cm, 2.5 * cm, 3 * cm, 5 * cm]
            )
            notes_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), GRIS_CLAIR),
                ('TEXTCOLOR', (0, 0), (-1, 0), BLANC),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                ('ALIGN', (3, 0), (3, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.4, NOIR),
                ('BACKGROUND', (0, 1), (-1, -1), BLANC),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
            ]))

        else:
            # ====================================================
            # VERSION CLASSIQUE (sans colonne Arabe)
            # ====================================================
            notes_data = [[
                Paragraph("<b>Matières</b>", style_normal_bold),
                Paragraph("<b>Notes</b>", style_normal_bold),
                Paragraph("<b>Appréciations</b>", style_normal_bold),
            ]]

            for detail in resultat.details.all():
                notes_data.append([
                    Paragraph(f"{detail.matiere.nomMatiere}", style_normal),
                    Paragraph(f"{detail.note:.2f}", note_style),
                    Paragraph(f"{detail.appreciation or '-'}", style_normal),
                ])

            notes_table = Table(
                notes_data,
                colWidths=[7 * cm, 3 * cm, 6 * cm]
            )
            notes_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), GRIS_CLAIR),
                ('TEXTCOLOR', (0, 0), (-1, 0), BLANC),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.4, NOIR),
                ('BACKGROUND', (0, 1), (-1, -1), BLANC),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
            ]))

        story.append(notes_table)
        story.append(Spacer(1, 8))

    # ============================================================
    # RÉSULTATS DU MOIS
    # ============================================================
    if resultat:
        if rang_affiche == "1er":
            rang_txt = "1er"
        elif rang_affiche == "1ère":
            rang_txt = "1ère"
        elif rang_affiche != "-":
            rang_txt = rang_affiche
        else:
            rang_txt = "—"

        moyenne_classe_val = class_stats.get('moyenne_classe', 0) or 0
        effectif_val = class_stats.get('effectif', 0) or 0

        resultats_data = [
            [Paragraph("<b>Total (somme des notes) :</b>", style_label),
             Paragraph(f"<b>{total_notes:.2f}</b> <font size=8 color='#666666'></font>", style_valeur)],
            [Paragraph("<b>Moyenne :</b>", style_label),
             Paragraph(f"<b>{moyenne_notes:.2f}</b>", style_valeur)],
            [Paragraph("<b>Rang :</b>", style_label),
             Paragraph(
                 f"<b>{rang_txt}</b> <font size=8 color='#666666'>"
                 f"sur {effectif_classe} élève{'s' if effectif_classe > 1 else ''}</font>",
                 style_valeur)],
            [Paragraph("<b>Moyenne du 1er de la classe :</b>", style_label),
             Paragraph(
                 f"<b>{moyenne_premier:.2f}</b>"
                 + (f" <font size=8 color='#666666'>({nom_premier_eleve})</font>"
                    if nom_premier_eleve else ""),
                 style_valeur)],
            [Paragraph("<b>Moyenne de la classe :</b>", style_label),
             Paragraph(f"<b>{moyenne_classe_val:.2f}</b>", style_valeur)],
            
        ]
        resultats_table = Table(resultats_data, colWidths=[7 * cm, 9 * cm])
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

        # ✅ Échelle unique (cycles.py) : les seuils ne sont plus recopiés ici.
        from ..cycles import Cycle
        _phrases = {
            "Très Bien": "Très Bien. Excellent travail ! Félicitations.",
            "Bien": "Bien. Très bon travail. Continuez ainsi.",
            "Assez Bien": "Assez Bien. Bon travail. Continuez vos efforts.",
            "Passable": "Passable. Résultats justes. Encore un petit effort.",
            "Insuffisant": "Insuffisant. Travail à améliorer.",
            "Faible": "Faible. Des efforts sont nécessaires.",
        }
        appreciation = _phrases[Cycle.PREMIER.appreciation(moyenne_notes)]

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
# CERTIFICAT DE TRANSFERT
# =====================================================================

def generer_certificat_transfert_pdf(eleve, inscription, certificat, ecole,
                                     annee_debut, annee_fin, classes_doublees):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=1.5*cm, rightMargin=1.5*cm)
    styles = getSampleStyleSheet()

    header_style = ParagraphStyle('HeaderCT', parent=styles['Normal'], fontSize=10, leading=14)
    title_ecole_style = ParagraphStyle('TitleEcoleCT', parent=styles['Normal'], fontSize=15,
                                        fontName='Helvetica-Bold', alignment=TA_CENTER,
                                        spaceBefore=15, spaceAfter=5)
    title_style = ParagraphStyle('TitleCT', parent=styles['Normal'], fontSize=14,
                                  fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=20)
    body_style = ParagraphStyle('BodyCT', parent=styles['Normal'], fontSize=11,
                                 leading=20, alignment=TA_JUSTIFY)
    note_style = ParagraphStyle('NoteCT', parent=body_style, fontSize=9, leading=13)
    right_style = ParagraphStyle('RightCT', parent=styles['Normal'], fontSize=10, alignment=TA_RIGHT)

    cell_style = ParagraphStyle('CellCT', parent=styles['Normal'], fontSize=8,
                                 leading=10, alignment=TA_CENTER)
    cell_header_style = ParagraphStyle('CellHeaderCT', parent=cell_style, fontName='Helvetica-Bold')

    elements = []

    gauche = f"""
        {ecole.ministere or ''}<br/>
        ******************************<br/>
        {ecole.academie or ''}<br/>
        ******************************<br/>
        {ecole.circonscription or ''}
    """
    droite = f"""
        {ecole.republique or ''}<br/>
        {ecole.devise or ''}
    """
    header_table = Table([[Paragraph(gauche, header_style), Paragraph(droite, header_style)]],
                          colWidths=[10*cm, 8*cm])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(header_table)

    elements.append(Paragraph(ecole.nom, title_ecole_style))
    elements.append(Paragraph("Certificat de Transfert", title_style))

    classe_display = inscription.classe.get_nomClasse_display()
    pere = eleve.pere or 'Non renseigné'
    mere = eleve.mere or 'Non renseigné'

    corps = f"""
    Le Directeur de la {ecole.nom} soussigné certifie que l'élève : <u>{eleve.prenomEleve} {eleve.nomEleve.upper()}</u><br/><br/>
    Né(e) le : <u>{eleve.dateNaiss.strftime('%d/%m/%Y')}</u> à <u>{eleve.lieuNaiss}</u><br/><br/>
    Fils(Fille) de : <u>{pere}</u> et de : <u>{mere}</u><br/><br/>
    A fréquenté ledit établissement de <u>{annee_debut}</u> au <u>{annee_fin}</u><br/><br/>
    Sous le numéro matricule / Mle : <u>{eleve.matricule}</u> où il(elle) était en classe de : <u>{classe_display}</u>
    """
    elements.append(Paragraph(corps, body_style))
    elements.append(Spacer(1, 0.7*cm))

    col_widths = [2.0*cm, 2.0*cm, 2.3*cm, 2.2*cm, 3.3*cm, 3.2*cm, 3.0*cm]

    header_row = [
        Paragraph("Travail", cell_header_style),
        Paragraph("Conduite", cell_header_style),
        Paragraph("Nombre d'années de scolarité", cell_header_style),
        Paragraph("Classes doublées", cell_header_style),
        Paragraph("Décisions des conseils de maîtres", cell_header_style),
        Paragraph("Motifs du transfert", cell_header_style),
        Paragraph("École de destination", cell_header_style),
    ]

    data_row = [
        Paragraph(str(certificat.travail or '—'), cell_style),
        Paragraph(str(certificat.conduite or '—'), cell_style),
        Paragraph(f"{eleve.scolarite_totale} ans", cell_style),
        Paragraph(classes_doublees or 'Néant', cell_style),
        Paragraph(certificat.decision_conseil_maitres or '—', cell_style),
        Paragraph(certificat.motif_transfert or '—', cell_style),
        Paragraph(certificat.ecole_destination or '—', cell_style),
    ]

    info_table = Table([header_row, data_row], colWidths=col_widths, repeatRows=1)
    info_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.8*cm))

    elements.append(Paragraph(
        "Avis du Directeur du CAP (s'agissant d'un élève du second cycle) :",
        body_style
    ))
    elements.append(Spacer(1, 1.2*cm))

    elements.append(Paragraph(
        f"Fait à {ecole.ville or ''}, le {certificat.date_delivrance.strftime('%d/%m/%Y')}",
        right_style
    ))
    elements.append(Paragraph("Le Directeur de l'école", right_style))
    elements.append(Spacer(1, 2*cm))

    elements.append(Paragraph(
        "<b>NB :</b> <i>Le présent certificat sert uniquement pour l'admission provisoire de l'élève. "
        "L'inscription définitive n'intervient qu'après la réception du dossier scolaire.</i>",
        note_style
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# =====================================================================
# FICHE DE SUIVI SECOND CYCLE
# =====================================================================

def _cell(text, style):
    """Retourne un Paragraph (permet le retour à la ligne automatique)."""
    return Paragraph(str(text) if text is not None else "", style)


def generer_fiche_suivi_second_cycle_pdf(
    eleve, ecole, data_par_classe, matieres,
    moyennes_par_position, historique_ecoles,
    moyennes_tendances=None,
):
    """Fiche de suivi second cycle - Paysage A4."""
    buffer = io.BytesIO()

    def ordinal_fois(i):
        # ✅ « 1ère fois », « 2ème fois », « 3ème fois » (et non « 2ère fois »)
        return "1ère" if i == 1 else f"{i}ème"

    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        topMargin=0.8*cm, bottomMargin=0.8*cm,
        leftMargin=0.8*cm, rightMargin=0.8*cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'FSTitle', parent=styles['Normal'], fontSize=11,
        fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=2
    )
    small_style = ParagraphStyle(
        'FSSmall', parent=styles['Normal'], fontSize=8, leading=10
    )
    small_bold = ParagraphStyle(
        'FSSmallBold', parent=styles['Normal'], fontSize=8,
        leading=10, fontName='Helvetica-Bold'
    )
    identif_style = ParagraphStyle(
        'FSIdentif', parent=styles['Normal'], fontSize=9,
        leading=13, alignment=TA_CENTER
    )
    remarques_style = ParagraphStyle(
        'FSRemarques', parent=styles['Normal'], fontSize=8, leading=10
    )
    right_style = ParagraphStyle(
        'FSRight', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT
    )
    cell_style = ParagraphStyle(
        'Cell', parent=styles['Normal'], fontSize=7.5, leading=9,
        alignment=TA_CENTER
    )
    cell_bold = ParagraphStyle(
        'CellBold', parent=styles['Normal'], fontSize=7.5, leading=9,
        fontName='Helvetica-Bold', alignment=TA_LEFT
    )
    cell_bold_center = ParagraphStyle(
        'CellBoldCenter', parent=styles['Normal'], fontSize=7.5,
        leading=9, fontName='Helvetica-Bold', alignment=TA_CENTER
    )
    header_style = ParagraphStyle(
        'Header', parent=styles['Normal'], fontSize=7.5, leading=9,
        fontName='Helvetica-Bold', alignment=TA_CENTER
    )
    sign_style = ParagraphStyle(
        'Sign', parent=styles['Normal'], fontSize=7.5, leading=9,
        fontName='Helvetica-Bold', alignment=TA_LEFT
    )

    elements = []

    elements.append(Paragraph("MINISTERE DE L'EDUCATION NATIONALE", small_bold))
    elements.append(Paragraph("CELLULE DE PLANIFICATION ET DE STATISTIQUE", small_bold))
    elements.append(Paragraph("Commission d'Orientation DEF", small_bold))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(Paragraph(
        "FICHE DE SUIVI SECOND CYCLE DE L'ENSEIGNEMENT FONDAMENTAL",
        title_style
    ))
    elements.append(Paragraph("(Mettre un seul chiffre par case)", small_style))
    elements.append(Spacer(1, 0.3*cm))

    a_headers = ["N°", "NOM DE L'ECOLE", "COURS", "ANNEE", "CAP", "AE"]
    table_a_data = [[_cell(h, header_style) for h in a_headers]]

    nb_lignes_a = max(len(historique_ecoles), 5)
    for i in range(1, nb_lignes_a + 1):
        if i <= len(historique_ecoles):
            ligne = historique_ecoles[i - 1]
            table_a_data.append([
                _cell(str(i), cell_style),
                _cell(ligne['ecole'], cell_style),
                _cell(ligne['cours'], cell_style),
                _cell(ligne['annee'], cell_style),
                _cell(ligne['cap'], cell_style),
                _cell(ligne['ae'], cell_style),
            ])
        else:
            table_a_data.append([_cell(str(i), cell_style)] + [_cell("", cell_style)] * 5)

    table_a = Table(table_a_data)
    table_a.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8e8e8')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(table_a)
    elements.append(Spacer(1, 0.3*cm))

    elements.append(Paragraph(
        f"<b>Numéro Matricule :</b> {eleve.matricule} &nbsp;&nbsp;&nbsp; "
        f"<b>Prénoms :</b> {eleve.prenomEleve} &nbsp;&nbsp; "
        f"<b>NOM :</b> {eleve.nomEleve.upper()} &nbsp;&nbsp; "
        f"<b>Sexe :</b> {eleve.get_sexe_display() if eleve.sexe else ''}",
        identif_style))
    elements.append(Paragraph(
        f"<b>Né(e) le :</b> {eleve.dateNaiss.strftime('%d/%m/%Y') if eleve.dateNaiss else ''} "
        f"à {eleve.lieuNaiss or ''} &nbsp;&nbsp;&nbsp; "
        f"<b>Fils/Fille de :</b> {eleve.pere or ''} <b>et de :</b> {eleve.mere or ''}",
        identif_style))
    elements.append(Spacer(1, 0.4*cm))

    def construire_grille(nom_classes_page):
        headers_row1 = [_cell("Matières", header_style)]
        headers_row2 = [_cell("", header_style)]
        spans_classes = []
        col_cursor = 1

        for nom_classe in nom_classes_page:
            for i, tentative in enumerate(data_par_classe[nom_classe], 1):
                annee = tentative.get('annee', '') or ''
                suffixe = f" - {annee}" if annee else ""
                headers_row1.append(_cell(
                    f"{nom_classe} ({ordinal_fois(i)} fois){suffixe}", header_style))  # ✅
                headers_row1.extend([_cell("", header_style)] * 2)
                headers_row2.extend([
                    _cell("1er Tr", header_style),
                    _cell("2ème Tr", header_style),
                    _cell("3ème Tr", header_style),
                ])
                spans_classes.append((col_cursor, 3))
                col_cursor += 3

        rows = [headers_row1, headers_row2]

        for matiere in matieres:
            if matiere.tendance == 'litteraire':
                nom_affiche = f"{matiere.nomMatiere} (L)"
            elif matiere.tendance == 'scientifique':
                nom_affiche = f"{matiere.nomMatiere} (S)"
            else:
                nom_affiche = matiere.nomMatiere

            row = [_cell(nom_affiche, cell_bold)]

            for nom_classe in nom_classes_page:
                for tentative in data_par_classe[nom_classe]:
                    valeurs = tentative['grille'].get(
                        matiere.idMatiere, [None, None, None]
                    )
                    for val in valeurs:
                        row.append(_cell(
                            f"{val:.2f}" if val is not None else "",
                            cell_style
                        ))
            rows.append(row)

        nb_col = len(rows[0])
        rows.append([
            _cell("Date, Signature et Cachet du Directeur d'école →", sign_style)
        ] + [_cell("", cell_style)] * (nb_col - 1))
        idx_sign = len(rows) - 1

        return rows, nb_col, idx_sign, spans_classes

    def style_grille(idx_signature, nb_colonnes, spans_classes):
        style = [
            ('GRID', (0, 0), (-1, idx_signature - 1), 0.5, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 2), (-1, idx_signature - 1),
             [colors.white, colors.HexColor('#f9f9f9')]),
            ('BACKGROUND', (0, 0), (-1, 1), colors.HexColor('#e8e8e8')),
            ('SPAN', (0, idx_signature), (nb_colonnes - 1, idx_signature)),
            ('ALIGN', (0, idx_signature), (0, idx_signature), 'LEFT'),
            ('LINEABOVE', (0, idx_signature), (-1, idx_signature),
             0.5, colors.black),
            ('TOPPADDING', (0, idx_signature), (-1, idx_signature), 6),
            ('BOTTOMPADDING', (0, idx_signature), (-1, idx_signature), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]
        for start_col, span in spans_classes:
            style.append(('SPAN', (start_col, 0), (start_col + span - 1, 0)))
            style.append(('ALIGN', (start_col, 0),
                          (start_col + span - 1, 0), 'CENTER'))
        return style

    if matieres:
        data_p1, nb_col_p1, idx_sign_p1, spans_p1 = construire_grille(['7ème A', '8ème A'])
        table_p1 = Table(data_p1, repeatRows=2)
        table_p1.setStyle(TableStyle(style_grille(idx_sign_p1, nb_col_p1, spans_p1)))
        elements.append(table_p1)
    else:
        elements.append(Paragraph(
            "Aucune matière avec tendance disponible pour cet élève.",
            small_style
        ))

    elements.append(PageBreak())

    elements.append(Paragraph(
        f"Fiche de suivi (suite) - {eleve.prenomEleve} {eleve.nomEleve.upper()} "
        f"- Mle {eleve.matricule}", small_style
    ))
    elements.append(Spacer(1, 0.3*cm))

    if matieres:
        headers_row1 = [_cell("Matières", header_style)]
        headers_row2 = [_cell("", header_style)]
        spans_tentatives = []
        col_cursor = 1

        tentatives_9eme = []
        for i, tentative in enumerate(data_par_classe.get('9ème A', []), 1):
            annee = tentative.get('annee', '') or ''
            suffixe = f" - {annee}" if annee else ""
            headers_row1.append(_cell(
                f"9ème A ({ordinal_fois(i)} fois){suffixe}", header_style))  # ✅
            headers_row1.extend([_cell("", header_style)] * 2)
            headers_row2.extend([
                _cell("1er Tr", header_style),
                _cell("2ème Tr", header_style),
                _cell("3ème Tr", header_style),
            ])
            spans_tentatives.append((col_cursor, 3))
            col_cursor += 3
            tentatives_9eme.append(tentative)

        rows = [headers_row1, headers_row2]

        for matiere in matieres:
            if matiere.tendance == 'litteraire':
                nom_affiche = f"{matiere.nomMatiere} (L)"
            elif matiere.tendance == 'scientifique':
                nom_affiche = f"{matiere.nomMatiere} (S)"
            else:
                nom_affiche = matiere.nomMatiere

            row = [_cell(nom_affiche, cell_bold)]

            for tentative in tentatives_9eme:
                valeurs = tentative['grille'].get(
                    matiere.idMatiere, [None, None, None]
                )
                for val in valeurs:
                    row.append(_cell(
                        f"{val:.2f}" if val is not None else "",
                        cell_style
                    ))
            rows.append(row)

        row_tend = [_cell("TENDANCES", cell_bold_center)]
        for _ in tentatives_9eme:
            row_tend.extend([_cell("", cell_style)] * 3)
        rows.append(row_tend)
        idx_tendances = len(rows) - 1

        row_litt = [_cell("Littéraire", cell_bold)]
        for i, _ in enumerate(tentatives_9eme):
            item = (moyennes_tendances[i]
                    if moyennes_tendances and i < len(moyennes_tendances)
                    else {})
            val = item.get('litteraire')
            row_litt.append(_cell(
                f"{val:.2f}" if val is not None else "—",
                cell_bold_center
            ))
            row_litt.extend([_cell("", cell_style)] * 2)
        rows.append(row_litt)
        idx_litt = len(rows) - 1

        row_sci = [_cell("Scientifique", cell_bold)]
        for i, _ in enumerate(tentatives_9eme):
            item = (moyennes_tendances[i]
                    if moyennes_tendances and i < len(moyennes_tendances)
                    else {})
            val = item.get('scientifique')
            row_sci.append(_cell(
                f"{val:.2f}" if val is not None else "—",
                cell_bold_center
            ))
            row_sci.extend([_cell("", cell_style)] * 2)
        rows.append(row_sci)
        idx_sci = len(rows) - 1

        nb_col = len(rows[0])
        rows.append([
            _cell("Date, Signature et Cachet du Directeur d'école →", sign_style)
        ] + [_cell("", cell_style)] * (nb_col - 1))
        idx_sign = len(rows) - 1

        table = Table(rows, repeatRows=2)
        table_style = [
            ('GRID', (0, 0), (-1, idx_sign - 1), 0.5, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 1), colors.HexColor('#e8e8e8')),
            ('ROWBACKGROUNDS', (0, 2), (-1, idx_tendances - 1),
             [colors.white, colors.HexColor('#f9f9f9')]),
            ('SPAN', (0, idx_sign), (nb_col - 1, idx_sign)),
            ('ALIGN', (0, idx_sign), (0, idx_sign), 'LEFT'),
            ('LINEABOVE', (0, idx_sign), (-1, idx_sign), 0.5, colors.black),
            ('TOPPADDING', (0, idx_sign), (-1, idx_sign), 6),
            ('BOTTOMPADDING', (0, idx_sign), (-1, idx_sign), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('BACKGROUND', (0, idx_tendances), (-1, idx_tendances),
             colors.HexColor('#d0d0d0')),
            ('BACKGROUND', (0, idx_litt), (-1, idx_litt),
             colors.HexColor('#fff8dc')),
            ('BACKGROUND', (0, idx_sci), (-1, idx_sci),
             colors.HexColor('#e6f3ff')),
        ]

        for start_col, span in spans_tentatives:
            table_style.append(
                ('SPAN', (start_col, 0), (start_col + span - 1, 0)))
            table_style.append(('ALIGN', (start_col, 0),
                                (start_col + span - 1, 0), 'CENTER'))

        for start_col, _ in spans_tentatives:
            table_style.append(
                ('SPAN', (start_col, idx_litt), (start_col + 2, idx_litt)))
            table_style.append(
                ('SPAN', (start_col, idx_sci), (start_col + 2, idx_sci)))

        table.setStyle(TableStyle(table_style))
        elements.append(table)

    elements.append(Spacer(1, 0.5*cm))

    if moyennes_tendances:
        moyennes_litt_valides = [
            m['litteraire'] for m in moyennes_tendances
            if m.get('litteraire') is not None
        ]
        moyennes_sci_valides = [
            m['scientifique'] for m in moyennes_tendances
            if m.get('scientifique') is not None
        ]

        # ✅ Arrondi scolaire (12,345 → 12,35) au lieu de round()
        moy_litt = (
            arrondir_moyenne(sum(moyennes_litt_valides) / len(moyennes_litt_valides))
            if moyennes_litt_valides else None
        )
        moy_sci = (
            arrondir_moyenne(sum(moyennes_sci_valides) / len(moyennes_sci_valides))
            if moyennes_sci_valides else None
        )

        tendance_eleve = "—"
        if moy_litt is not None and moy_sci is not None:
            if moy_litt > moy_sci:
                tendance_eleve = "Littéraire"
            elif moy_sci > moy_litt:
                tendance_eleve = "Scientifique"
            else:
                tendance_eleve = "Équilibré"
        elif moy_litt is not None:
            tendance_eleve = "Littéraire"
        elif moy_sci is not None:
            tendance_eleve = "Scientifique"

        bilan_data = [
            [_cell("BILAN FINAL", cell_bold_center),
             _cell("Littéraire", cell_bold_center),
             _cell("Scientifique", cell_bold_center),
             _cell("Tendance de l'élève", cell_bold_center)],
            [_cell("Moyenne des tentatives", cell_bold),
             _cell(f"{moy_litt:.2f}" if moy_litt is not None else "—", cell_bold_center),
             _cell(f"{moy_sci:.2f}" if moy_sci is not None else "—", cell_bold_center),
             _cell(tendance_eleve, cell_bold_center)],
        ]
        bilan_table = Table(
            bilan_data,
            colWidths=[6*cm, 4*cm, 4*cm, 5*cm],
            hAlign='CENTER'
        )
        bilan_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8e8e8')),
            ('BACKGROUND', (1, 1), (1, 1), colors.HexColor('#fff8dc')),
            ('BACKGROUND', (2, 1), (2, 1), colors.HexColor('#e6f3ff')),
            ('BACKGROUND', (3, 1), (3, 1), colors.HexColor('#d4edda')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        elements.append(Paragraph("<b><u>SYNTHÈSE DES TENDANCES</u></b>", title_style))
        elements.append(Spacer(1, 0.2*cm))
        elements.append(bilan_table)
        elements.append(Spacer(1, 0.5*cm))

    elements.append(Paragraph(
        "<b>REMARQUES IMPORTANTES (sur la Fiche de Suivi) :</b>",
        remarques_style
    ))
    elements.append(Paragraph(
        "1. En aucun cas, la fiche ne sera remise ni à ses parents ;<br/>"
        "2. En cas de changement d'établissement cette fiche sera transmise "
        "au Directeur du CAP qui reçoit l'élève ;<br/>"
        "3. Cette fiche ne doit comporter aucune surcharge ni rature sous "
        "peine de nullité ;<br/>"
        "4. La non production de cette fiche entraîne la non orientation "
        "de l'élève ;<br/>"
        "5. Lorsque l'élève est admis au DEF, envoyez la fiche à l'Académie "
        "d'Enseignement.",
        remarques_style
    ))
    elements.append(Spacer(1, 0.8*cm))

    elements.append(Paragraph(
        "Fait à ......................., le ............../............./20.....",
        right_style
    ))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(Paragraph(
        "Le Directeur d'école (pour les Admis au DEF)", right_style
    ))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(
        "<i>Prénom, NOM, Signature et Cachet</i>", right_style
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# =====================================================================
# EMPLOI DU TEMPS
# =====================================================================

def generer_emploi_temps_pdf(classe, annee_scolaire, ecole, plages, jours, creneaux_par_case):
    """Génère le PDF de l'emploi du temps d'une classe."""
    from datetime import date

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

    story.append(_construire_entete_3_zones(ecole, styles))
    story.append(Spacer(1, 15))

    story.append(Paragraph("EMPLOI DU TEMPS", style_titre))
    story.append(Paragraph(
        f"Classe : <b>{classe.nomClasse}</b> — Année scolaire : <b>{annee_scolaire}</b>",
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
                    texte = f"<b>{creneau.matiere.nomMatiere}</b>"
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
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


# =====================================================================
# LISTE DES ÉLÈVES
# =====================================================================

def generer_liste_eleves_pdf(eleves, ecole, filtres=None):
    """Génère le PDF de la liste des élèves (Mode Portrait)."""
    from datetime import date

    if filtres is None:
        filtres = {}

    buffer = io.BytesIO()

    # ✅ 1. Passage en mode portrait
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=0.5 * cm, bottomMargin=0.3 * cm,
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
    # ✅ 2. Taille de police légèrement réduite pour le portrait
    style_cellule = ParagraphStyle(
        'Cellule', parent=styles['Normal'],
        fontSize=8, alignment=TA_CENTER, leading=10,
    )
    style_cellule_gauche = ParagraphStyle(
        'CelluleGauche', parent=styles['Normal'],
        fontSize=8, alignment=TA_LEFT, leading=10,
    )
    style_pied = ParagraphStyle(
        'Pied', parent=styles['Normal'],
        fontSize=8, alignment=TA_CENTER, textColor=colors.grey,
    )

    story.append(_construire_entete_3_zones(ecole, styles))
    story.append(Spacer(1, 15))

    story.append(Paragraph("LISTE DES ÉLÈVES", style_titre))

    sous_titre_parts = []
    if filtres.get('classe_nom'):
        sous_titre_parts.append(f"Classe : <b>{filtres['classe_nom']}</b>")
    if filtres.get('annee_nom'):
        sous_titre_parts.append(f"Année scolaire : <b>{filtres['annee_nom']}</b>")
    if filtres.get('cycle_filtre'):
        sous_titre_parts.append(f"Cycle : <b>{filtres['cycle_filtre']}</b>")
    if filtres.get('search'):
        sous_titre_parts.append(f"Recherche : <b>{filtres['search']}</b>")

    if sous_titre_parts:
        story.append(Paragraph(" — ".join(sous_titre_parts), style_sous_titre))
    else:
        story.append(Paragraph(
            f"Année scolaire : <b>{filtres.get('annee_nom', 'Toutes')}</b>",
            style_sous_titre
        ))

    header = ['N°', 'Matricule', 'Prénoms', 'Noms']
    data = [header]

    for i, eleve in enumerate(eleves, start=1):
        data.append([
            Paragraph(str(i), style_cellule),
            Paragraph(eleve.matricule or '-', style_cellule),
            Paragraph(eleve.prenomEleve or '-', style_cellule_gauche),
            Paragraph(eleve.nomEleve or '-', style_cellule_gauche),
        ])

    if len(data) == 1:
        data.append([
            Paragraph('-', style_cellule),
            Paragraph('-', style_cellule),
            Paragraph('Aucun élève trouvé', style_cellule_gauche),
            Paragraph('-', style_cellule),
        ])

    # ✅ 3. Ajustement des largeurs pour le format A4 Portrait
    # Largeur totale A4 portrait avec marges 1.5cm = 18 cm environ.
    largeur_totale = doc.width
    col_widths = [
        1.2 * cm,  # N°
        3.5 * cm,  # Matricule (légèrement réduit)
        (largeur_totale - 1.2 * cm - 3.5 * cm - 6 * cm), # Prénoms (le reste)
        6 * cm,  # Noms (légèrement réduit)
    ]

    table = Table(data, colWidths=col_widths, repeatRows=1)

    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, 0), 10), # En-tête un peu plus petite
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]

    table.setStyle(TableStyle(table_styles))
    story.append(table)

    story.append(Spacer(1, 15))

    total = len(eleves)
    story.append(Paragraph(
        f"<b>Total : {total} élève{'s' if total > 1 else ''}</b>",
        style_cellule
    ))

    """story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"Document généré le {date.today().strftime('%d/%m/%Y')}",
        style_pied
    ))"""

    doc.build(story)
    buffer.seek(0)
    return buffer

def generer_carte_scolaire_pdf(
    eleve,
    inscription,
    ecole,
    qr_code_image,
    couleur_hex="#1E5AA8",
    nom_fond="bleu_vagues.jpg"
):
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
    bleu_principal = colors.HexColor("#4C81D6")
    bleu_fonce = colors.HexColor("#123A7A")
    gris = colors.HexColor("#666666")
    fond = colors.HexColor("#F8FAFD")

    # =====================================================
    # FOND
    # =====================================================
    c.setFillColor(fond)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    chemin_fond = os.path.join(
        settings.BASE_DIR,
        "ecole",
        "static",
        "img",
        "fonds",
        nom_fond
    )

    if os.path.exists(chemin_fond):
        try:
            c.drawImage(chemin_fond, 0, 0, width=width, height=height)
        except:
            pass

    # =====================================================
    # LOGO EN HAUT GAUCHE
    # =====================================================
    if ecole.logo and hasattr(ecole.logo, "path"):
        try:
            c.drawImage(
                ecole.logo.path,
                4 * mm,
                height - 12 * mm,
                width=7 * mm,
                height=7 * mm,
                preserveAspectRatio=True,
                mask="auto"
            )
        except:
            pass

    # =====================================================
    # ENTÊTE
    # =====================================================
    c.setFillColor(bleu_fonce)
    c.setFont("Helvetica-Bold", 12)
    
    # Nom de l'école
    c.drawString(14 * mm, height - 7 * mm, (ecole.nom or "ECOLE")[:30].upper())

    # ✅ FIX : Centrage de "CARTE SCOLAIRE" et de l'année
    c.setFont("Helvetica", 6)
    c.setFillColor(colors.black)
    c.drawCentredString(
        width / 2,
        height - 10.5 * mm,
        f"CARTE SCOLAIRE {inscription.anneeScolaire.anneeScolaire}"
    )

    c.setStrokeColor(colors.lightgrey)
    c.line(14 * mm, height - 12 * mm, width - 5 * mm, height - 12 * mm)

    # =====================================================
    # PHOTO (avec cadre arrondi)
    # =====================================================
    photo_x = 5 * mm
    photo_y = 18 * mm
    photo_w = 20 * mm
    photo_h = 21 * mm
    rayon = 2 * mm

    # 1. DESSINER LE CADRE BLEU
    c.setStrokeColor(bleu_principal) 
    c.setLineWidth(1.5)
    c.roundRect(
        photo_x - 1, photo_y - 1,
        photo_w + 2, photo_h + 2,
        rayon, stroke=1, fill=0
    )

    # 2. DESSINER LA PHOTO À L'INTÉRIEUR DU CADRE (avec découpe)
    if eleve.photo and hasattr(eleve.photo, "path"):
        try:
            # Sauvegarde de l'état du canvas
            c.saveState()
            
            # Création du chemin de découpe (un rectangle aux coins arrondis)
            p = c.beginPath()
            p.roundRect(photo_x, photo_y, photo_w, photo_h, rayon)
            c.clipPath(p, stroke=0, fill=0)
            
            # Dessin de la photo (elle sera découpée par le chemin précédent)
            c.drawImage(
                eleve.photo.path,
                photo_x, photo_y,
                width=photo_w, height=photo_h,
                preserveAspectRatio=True, 
                mask="auto"
            )
            
            # Restauration de l'état du canvas
            c.restoreState()
        except Exception as e:
            print(f"Erreur photo: {e}")
            pass

    # =====================================================
    # CACHET SUR LA PHOTO
    # =====================================================
    if ecole.cachet_ecole and hasattr(ecole.cachet_ecole, "path"):
        try:
            c.drawImage(
                ecole.cachet_ecole.path,
                photo_x + 13 * mm,
                photo_y - 1 * mm,
                width=6 * mm, height=6 * mm,
                preserveAspectRatio=True, mask="auto"
            )
        except:
            pass

    # =====================================================
    # MATRICULE (sous la photo)
    # =====================================================
    c.setFillColor(bleu_principal)
    c.roundRect(
        photo_x,
        photo_y - 5 * mm,
        photo_w,
        4.5 * mm,
        1 * mm,
        fill=1, stroke=0
    )

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(
        photo_x + photo_w / 2,
        photo_y - 3.2 * mm,
        str(eleve.matricule)
    )

    # =====================================================
    # INFORMATIONS ÉLÈVE
    # =====================================================
    info_x = 30 * mm
    y = height - 17 * mm

    def ligne(libelle, valeur):
        nonlocal y
        c.setFillColor(bleu_fonce)
        c.setFont("Helvetica-Bold", 6)
        c.drawString(info_x, y, libelle)

        c.setFillColor(colors.black)
        c.setFont("Helvetica", 6)
        c.drawString(info_x + 16 * mm, y, str(valeur))

        y -= 3.6 * mm

    ligne("Nom :",eleve.nomEleve.upper())
    ligne("Prenom :",eleve.prenomEleve)
    ligne("Classe :", inscription.classe.nomClasse)
    ligne("Sexe :", eleve.get_sexe_display() or "-")
    ligne("Né(e) le :", eleve.dateNaiss.strftime("%d/%m/%Y"))
    ligne("Lieu :", eleve.lieuNaiss or "-")
    ligne("Père :", eleve.pere or '-')
    ligne("Mère :", eleve.mere or '-')

    # =====================================================
    # GRAND LOGO À DROITE (s'il y en a un)
    # =====================================================
    if ecole.logo and hasattr(ecole.logo, "path"):
        try:
            c.drawImage(
                ecole.logo.path,
                width - 20 * mm,
                height - 30 * mm,
                width=16 * mm, height=16 * mm,
                preserveAspectRatio=True, mask="auto"
            )
        except:
            pass

    # =====================================================
    # QR CODE
    # =====================================================
    qr_x = width - 19 * mm
    qr_y = 8 * mm
    qr_size = 14 * mm

    try:
        qr_base64 = qr_code_image.split(",")[1] if "," in qr_code_image else qr_code_image
        qr_data = base64.b64decode(qr_base64)
        qr_buffer = io.BytesIO(qr_data)
        qr_image = ImageReader(qr_buffer)

        # ✅ FIX : Cadre du QR Code en bleu principal (au lieu de noir)
        c.setStrokeColor(bleu_principal) 
        c.setLineWidth(1)
        c.roundRect(
            qr_x - 1, qr_y - 1,
            qr_size + 2, qr_size + 2,
            1 * mm, stroke=1, fill=0
        )

        c.drawImage(
            qr_image,
            qr_x, qr_y,
            width=qr_size, height=qr_size
        )
    except:
        pass

    # =====================================================
    # SIGNATURE
    # =====================================================
    if ecole.signature_directeur and hasattr(ecole.signature_directeur, "path"):
        try:
            c.drawImage(
                ecole.signature_directeur.path,
                9 * mm, 7.5 * mm,
                width=16 * mm, height=5 * mm,
                preserveAspectRatio=True, mask="auto"
            )
        except:
            pass

    c.setFillColor(bleu_fonce)
    c.setFont("Helvetica-Oblique", 5)
    
    # ✅ FIX : Décalage du texte "Le Directeur" vers la droite pour l'aligner avec la signature
    c.drawString(12 * mm, 6 * mm, "Le Directeur") 

    # =====================================================
    # CONTACT ECOLE (Pied de page)
    # =====================================================
    c.setFillColor(bleu_fonce)
    c.rect(0, 0, width, 4 * mm, fill=1, stroke=0)

    # ✅ FIX : Ajout de l'adresse dans la chaîne de contact
    contact = ""
    if hasattr(ecole, "telephone") and ecole.telephone:
        contact += f"Tel: {ecole.telephone}"
    if hasattr(ecole, "email") and ecole.email:
        if contact: contact += " | "
        contact += ecole.email
    # Ajout de l'adresse
    if hasattr(ecole, "adresse") and ecole.adresse:
        if contact: contact += " | "
        contact += ecole.adresse
    elif hasattr(ecole, "ville") and ecole.ville:
        if contact: contact += " | "
        contact += ecole.ville

    c.setFont("Helvetica", 4.8)
    c.setFillColor(colors.white)
    c.drawCentredString(width / 2, 1.4 * mm, contact[:90])

    # =====================================================
    # FINALISATION
    # =====================================================
    c.save()
    buffer.seek(0)
    return buffer


def generer_planche_cartes_classe_pdf(inscriptions, ecole, couleur_hex='#1E5AA8', nom_fond='bleu_vagues.jpg'):
    """
    Génère une planche A4 contenant 8 cartes scolaires (2x4).
    ✅ Utilise exactement le design de la carte individuelle.
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
    from .qr_code import generer_qr_code_base64

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Dimensions d'une carte
    card_w = 85.6 * mm
    card_h = 54 * mm
    gap = 8 * mm 

    # Marges pour centrer la grille (2x4)
    margin_x = (width - (card_w * 2) - gap) / 2
    margin_y = (height - (card_h * 4) - (gap * 3)) / 2

    # Chemin de l'image de fond
    chemin_fond = os.path.join(settings.BASE_DIR, "ecole", "static", "img", "fonds", nom_fond)

    bleu_principal = colors.HexColor(couleur_hex)
    bleu_fonce = colors.HexColor("#123A7A")
    gris = colors.HexColor("#666666")
    fond = colors.HexColor("#F8FAFD")

    for index, inscription in enumerate(inscriptions):
        col = index % 2
        row = (index // 2) % 4
        
        if index > 0 and index % 8 == 0:
            c.showPage()
            row = 0
            col = 0

        # Coordonnées du coin inférieur gauche de la carte
        x = margin_x + (col * (card_w + gap))
        y = height - margin_y - ((row + 1) * (card_h + gap)) + gap
        eleve = inscription.eleve
        
        # =====================================================
        # 1. FOND
        # =====================================================
        c.setFillColor(fond)
        c.rect(x, y, card_w, card_h, fill=1, stroke=0)

        if os.path.exists(chemin_fond):
            try:
                c.drawImage(chemin_fond, x, y, width=card_w, height=card_h, preserveAspectRatio=False, mask='auto')
            except: pass

        # =====================================================
        # 2. LOGO EN HAUT GAUCHE
        # =====================================================
        if ecole.logo and hasattr(ecole.logo, "path"):
            try:
                c.drawImage(ecole.logo.path, x + 4*mm, y + card_h - 12*mm, width=7*mm, height=7*mm, preserveAspectRatio=True, mask="auto")
            except: pass

        # =====================================================
        # 3. ENTÊTE
        # =====================================================
        c.setFillColor(bleu_fonce)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x + 14*mm, y + card_h - 7*mm, (ecole.nom or "ECOLE")[:30].upper())

        c.setFont("Helvetica", 6)
        c.setFillColor(colors.black)
        c.drawCentredString(x + card_w/2, y + card_h - 10.5*mm, f"CARTE SCOLAIRE {inscription.anneeScolaire.anneeScolaire}")

        c.setStrokeColor(colors.lightgrey)
        c.line(x + 14*mm, y + card_h - 12*mm, x + card_w - 5*mm, y + card_h - 12*mm)

        # =====================================================
        # 4. PHOTO (avec cadre arrondi)
        # =====================================================
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

        # Cachet sur la photo
        if ecole.cachet_ecole and hasattr(ecole.cachet_ecole, "path"):
            try:
                c.drawImage(ecole.cachet_ecole.path, photo_x + 13*mm, photo_y - 1*mm, width=6*mm, height=6*mm, preserveAspectRatio=True, mask="auto")
            except: pass

        # Matricule (sous la photo)
        c.setFillColor(bleu_principal)
        c.roundRect(photo_x, photo_y - 5*mm, photo_w, 4.5*mm, 1*mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(photo_x + photo_w/2, photo_y - 3.2*mm, str(eleve.matricule))

        # =====================================================
        # 5. INFORMATIONS ÉLÈVE
        # =====================================================
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

        ligne("Nom :", eleve.nomEleve.upper())
        ligne("Prenom :", eleve.prenomEleve)
        ligne("Classe :", inscription.classe.nomClasse)
        ligne("Sexe :", eleve.get_sexe_display() or "-")
        ligne("Né(e) le :", eleve.dateNaiss.strftime("%d/%m/%Y"))
        ligne("Lieu :", eleve.lieuNaiss or "-")
        ligne("Père :", eleve.pere or '-')
        ligne("Mère :", eleve.mere or '-')

        # =====================================================
        # 6. GRAND LOGO À DROITE
        # =====================================================
        if ecole.logo and hasattr(ecole.logo, "path"):
            try:
                c.drawImage(ecole.logo.path, x + card_w - 20*mm, y + card_h - 30*mm, width=16*mm, height=16*mm, preserveAspectRatio=True, mask="auto")
            except: pass

        # =====================================================
        # 7. QR CODE
        # =====================================================
        texte_qr = f"{eleve.prenomEleve} {eleve.nomEleve.upper()} - {eleve.matricule}"
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

        # =====================================================
        # 8. SIGNATURE
        # =====================================================
        if ecole.signature_directeur and hasattr(ecole.signature_directeur, "path"):
            try:
                c.drawImage(ecole.signature_directeur.path, x + 9*mm, y + 7.5*mm, width=16*mm, height=5*mm, preserveAspectRatio=True, mask="auto")
            except: pass

        c.setFillColor(bleu_fonce)
        c.setFont("Helvetica-Oblique", 5)
        c.drawString(x + 12*mm, y + 6*mm, "Le Directeur") 

        # =====================================================
        # 9. CONTACT ECOLE (Pied de page)
        # =====================================================
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