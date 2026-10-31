"""Vues : cartes."""
from ._deps import *
from ._helpers import *


@login_required
def carte_scolaire_preview(request, inscription_id):
    """Affiche la prévisualisation HTML de la carte scolaire."""
    inscription = get_object_or_404(Inscription, idInscription=inscription_id)
    eleve = inscription.eleve
    ecole = EcoleInfo.get_solo()

    texte_qr = f"{eleve.prenomEleve} {eleve.nomEleve.upper()} - {eleve.matricule}"
    qr_code_image = generer_qr_code_base64(texte_qr)

    # ✅ Récupérer la couleur et le fond depuis l'URL
    couleur_principale = couleur_valide(request.GET.get('couleur'), '#2980b9') 
    fond_choisi = fond_valide(request.GET.get('fond'), 'bleu_vagues.jpg') # Valeur par défaut

    # ✅ Liste des fonds disponibles
    fonds_disponibles = [
        {'code': 'fond_blanc', 'nom': 'Fond blanc'},
        {'code': 'carte_scolaire1.jpg', 'nom': 'Fond 1'},
        {'code': 'carte_scolaire2.jpg', 'nom': 'Fond 2'},
        {'code': 'carte_scolaire3.jpg', 'nom': 'Fond 3'},
        {'code': 'carte_scolaire4.jpg', 'nom': 'Fond 4'},
    ]

    couleurs_disponibles = [
        {'code': '#2980b9', 'nom': 'Bleu'},
        {'code': '#6f42c1', 'nom': 'Violet'},
        {'code': '#28a745', 'nom': 'Vert'},
        {'code': '#dc3545', 'nom': 'Rouge'},
    ]

    context = {
        'eleve': eleve,
        'inscription': inscription,
        'ecole': ecole,
        'qr_code_image': qr_code_image,
        'couleur_principale': couleur_principale,
        'couleurs_disponibles': couleurs_disponibles,
        'fond_choisi': fond_choisi,              # ✅ Nouveau
        'fonds_disponibles': fonds_disponibles,  # ✅ Nouveau
    }
    return render(request, 'ecole/carte_scolaire/preview.html', context)


@login_required
def carte_scolaire_pdf(request, inscription_id):
    """Génère le PDF de la carte scolaire via ReportLab."""
    inscription = get_object_or_404(Inscription, idInscription=inscription_id)
    eleve = inscription.eleve
    ecole = EcoleInfo.get_solo()

    texte_qr = f"{eleve.prenomEleve} {eleve.nomEleve.upper()} - {eleve.matricule}"
    qr_code_image = generer_qr_code_base64(texte_qr)

    # ✅ Récupérer la couleur ET le fond depuis l'URL
    couleur = couleur_valide(request.GET.get('couleur'), '#2980b9')
    fond = fond_valide(request.GET.get('fond'), 'bleu_vagues.jpg')

    # ✅ Passer le fond à la fonction
    buffer = generer_carte_scolaire_pdf(eleve, inscription, ecole, qr_code_image, couleur, fond)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="carte_scolaire_{eleve.matricule}.pdf"'
    return response


@login_required
def carte_scolaire_classe_pdf(request, classe_id, annee_id):
    """Génère la planche PDF de toute la classe."""
    classe = get_object_or_404(Classe, idClasse=classe_id)
    annee = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_id)
    ecole = EcoleInfo.get_solo()

    inscriptions = Inscription.objects.filter(
        classe=classe, anneeScolaire=annee
    ).select_related('eleve').order_by('eleve__nomEleve')

    if not inscriptions.exists():
        messages.warning(request, "Aucun élève inscrit dans cette classe.")
        return redirect('fondamental:classe_list')

    # ✅ 1. Récupérer la couleur et le fond depuis l'URL
    couleur = couleur_valide(request.GET.get('couleur'), '#2980b9')
    fond = fond_valide(request.GET.get('fond'), 'bleu_vagues.jpg')

    # ✅ 2. Générer la planche
    buffer = generer_planche_cartes_classe_pdf(inscriptions, ecole, couleur, fond)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="cartes_{classe.nomClasse}.pdf"'
    return response


