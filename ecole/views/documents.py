"""Vues : documents."""
from ._deps import *
from ._helpers import *


@login_required
def dossier_scolaire_eleve(request, eleve_id):
    eleve = get_object_or_404(Eleve, id=eleve_id)
    inscriptions = Inscription.objects.filter(eleve=eleve).select_related(
        'classe', 'anneeScolaire'
    ).order_by('-anneeScolaire__anneeScolaire')
    context = {'eleve': eleve, 'inscriptions': inscriptions}
    return render(request, 'ecole/dossier/index.html', context)


@login_required
def certificat_frequentation(request, eleve_id, annee_scolaire):
    eleve = get_object_or_404(Eleve, id=eleve_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    inscription = get_object_or_404(Inscription, eleve=eleve, anneeScolaire=annee)
    ecole = EcoleInfo.get_solo()
    context = {
        'eleve': eleve, 'inscription': inscription,
        'annee_scolaire': annee_scolaire, 'ecole': ecole, 'date_jour': date.today(),
    }
    return render(request, 'ecole/certificats/frequentation.html', context)


@login_required
def certificat_frequentation_pdf(request, eleve_id, annee_scolaire):
    eleve = get_object_or_404(Eleve, id=eleve_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    inscription = get_object_or_404(Inscription, eleve=eleve, anneeScolaire=annee)
    ecole = EcoleInfo.get_solo()
    buffer = generer_certificat_frequentation_pdf(
        eleve, inscription, ecole, annee_scolaire, date.today()
    )
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="certificat_frequentation_{eleve.matricule}.pdf"'
    )
    return response


@login_required
def proposition_passage_index(request):
    """Page de sélection : onglets cycle + liste des classes."""
    cycle_param = request.GET.get('cycle')
    annee_param = request.GET.get('annee')

    annees_scolaires = AnneeScolaire.objects.all().order_by('-anneeScolaire')

    if annee_param:
        annee_selectionnee = AnneeScolaire.objects.filter(anneeScolaire=annee_param).first()
    else:
        annee_selectionnee = annees_scolaires.first()

    annee_encours = annee_selectionnee.anneeScolaire if annee_selectionnee else None

    classes_1er = Classe.objects.filter(cycle='1er').order_by('nomClasse')
    classes_2e = Classe.objects.filter(cycle='2e').order_by('nomClasse')

    def enrichir_classes(classes_qs):
        resultats = []
        for classe in classes_qs:
            nb = 0
            if annee_selectionnee:
                nb = Inscription.objects.filter(
                    classe=classe, anneeScolaire=annee_selectionnee
                ).count()
            resultats.append({
                'classe': classe,
                'nb_eleves': nb,
            })
        return resultats

    context = {
        'annees_scolaires': annees_scolaires,
        'annee_selectionnee': annee_selectionnee,
        'annee_encours': annee_encours,
        'cycle_filtre': cycle_param,
        'classes_1er': enrichir_classes(classes_1er),
        'classes_2e': enrichir_classes(classes_2e),
    }
    return render(request, 'ecole/proposition_passage/index.html', context)


@login_required
def proposition_passage(request, classe_id, annee_scolaire):
    classe = get_object_or_404(Classe, idClasse=classe_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    ecole = EcoleInfo.get_solo()

    lignes = _construire_lignes_proposition(classe, annee)

    total_garcons = sum(1 for l in lignes if l['eleve'].sexe == 'M')
    total_filles = sum(1 for l in lignes if l['eleve'].sexe == 'F')
    passants_garcons = sum(1 for l in lignes if l['prop_cons'] == 'Passant' and l['eleve'].sexe == 'M')
    passants_filles = sum(1 for l in lignes if l['prop_cons'] == 'Passant' and l['eleve'].sexe == 'F')
    redoublants_garcons = sum(1 for l in lignes if l['prop_cons'] == 'Redoublant' and l['eleve'].sexe == 'M')
    redoublants_filles = sum(1 for l in lignes if l['prop_cons'] == 'Redoublant' and l['eleve'].sexe == 'F')

    context = {
        'classe': classe, 'annee_scolaire': annee_scolaire, 'ecole': ecole,
        'lignes': lignes, 'total_eleves': len(lignes),
        'total_garcons': total_garcons, 'total_filles': total_filles,
        'passants_garcons': passants_garcons, 'passants_filles': passants_filles,
        'passants_total': passants_garcons + passants_filles,
        'redoublants_garcons': redoublants_garcons,
        'redoublants_filles': redoublants_filles,
        'redoublants_total': redoublants_garcons + redoublants_filles,
        'est_1er_cycle': classe.cycle == '1er',
        'libelle_cycle': "1er CYCLE" if classe.cycle == '1er' else "2 CYCLE",
    }
    return render(request, 'ecole/proposition_passage/liste.html', context)


@login_required
def proposition_passage_pdf(request, classe_id, annee_scolaire):
    classe = get_object_or_404(Classe, idClasse=classe_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    ecole = EcoleInfo.get_solo()

    lignes = _construire_lignes_proposition(classe, annee)

    total_garcons = sum(1 for l in lignes if l['eleve'].sexe == 'M')
    total_filles = sum(1 for l in lignes if l['eleve'].sexe == 'F')
    passants_garcons = sum(1 for l in lignes if l['prop_cons'] == 'Passant' and l['eleve'].sexe == 'M')
    passants_filles = sum(1 for l in lignes if l['prop_cons'] == 'Passant' and l['eleve'].sexe == 'F')
    redoublants_garcons = sum(1 for l in lignes if l['prop_cons'] == 'Redoublant' and l['eleve'].sexe == 'M')
    redoublants_filles = sum(1 for l in lignes if l['prop_cons'] == 'Redoublant' and l['eleve'].sexe == 'F')

    stats = {
        'total_garcons': total_garcons,
        'total_filles': total_filles,
        'total_eleves': len(lignes),
        'passants_garcons': passants_garcons,
        'passants_filles': passants_filles,
        'passants_total': passants_garcons + passants_filles,
        'redoublants_garcons': redoublants_garcons,
        'redoublants_filles': redoublants_filles,
        'redoublants_total': redoublants_garcons + redoublants_filles,
    }

    buffer = generer_proposition_passage_pdf(
        classe, annee_scolaire, ecole, lignes, stats
    )
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="proposition_passage_{classe.nomClasse}_{annee_scolaire}.pdf"'
    )
    return response


@login_required
def certificat_transfert_form(request, eleve_id, annee_scolaire):
    eleve = get_object_or_404(Eleve, id=eleve_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    inscription = get_object_or_404(Inscription, eleve=eleve, anneeScolaire=annee)

    moyenne = _moyenne_annuelle_inscription(inscription)
    travail_auto = f"{moyenne:.2f}".replace('.', ',') if moyenne is not None else ''

    if request.method == 'POST':
        form = CertificatTransfertForm(request.POST)
        if form.is_valid():
            certificat = form.save(commit=False)
            certificat.inscription = inscription
            certificat.travail = travail_auto
            certificat.save()
            messages.success(request, "Certificat de transfert généré avec succès!")
            return redirect('fondamental:certificat_transfert_preview', certificat_id=certificat.id)
    else:
        form = CertificatTransfertForm()

    context = {
        'eleve': eleve, 'inscription': inscription,
        'annee_scolaire': annee_scolaire,
        'form': form, 'moyenne_generale': travail_auto,
    }
    return render(request, 'ecole/certificats/transfert_form.html', context)


@login_required
def certificat_transfert_preview(request, certificat_id):
    certificat = get_object_or_404(CertificatTransfert, id=certificat_id)
    inscription = certificat.inscription
    eleve = inscription.eleve
    ecole = EcoleInfo.get_solo()

    annee_debut = eleve.annee_recrutement[:4] if eleve.annee_recrutement else ''
    annee_fin = inscription.anneeScolaire.get_annee_fin()
    classes_doublees = _classes_doublees_affichage(eleve)

    context = {
        'eleve': eleve, 'inscription': inscription, 'certificat': certificat,
        'ecole': ecole, 'annee_debut': annee_debut, 'annee_fin': annee_fin,
        'classes_doublees': classes_doublees,
    }
    return render(request, 'ecole/certificats/transfert.html', context)


@login_required
def certificat_transfert_pdf(request, certificat_id):
    certificat = get_object_or_404(CertificatTransfert, id=certificat_id)
    inscription = certificat.inscription
    eleve = inscription.eleve
    ecole = EcoleInfo.get_solo()

    annee_debut = eleve.annee_recrutement[:4] if eleve.annee_recrutement else ''
    annee_fin = inscription.anneeScolaire.get_annee_fin()
    classes_doublees = _classes_doublees_affichage(eleve)

    buffer = generer_certificat_transfert_pdf(
        eleve, inscription, certificat, ecole, annee_debut, annee_fin, classes_doublees
    )
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="certificat_transfert_{eleve.matricule}.pdf"'
    )
    return response


@login_required
def fiche_suivi_second_cycle_preview(request, eleve_id):
    eleve = get_object_or_404(Eleve, id=eleve_id)
    ecole = EcoleInfo.get_solo()
    data_par_classe, matieres = _construire_fiche_suivi_data(eleve)
    moyennes_par_position = _construire_moyennes_par_tentative_chronologique(eleve)
    historique_ecoles = _construire_historique_ecoles(eleve, ecole, data_par_classe)

    moyennes_tendances = _calculer_moyennes_tendances(moyennes_par_position, matieres)

    context = {
        'eleve': eleve,
        'ecole': ecole,
        'data_par_classe': data_par_classe,
        'matieres': matieres,
        'moyennes_par_position': moyennes_par_position,
        'moyennes_tendances': moyennes_tendances,
        'historique_ecoles': historique_ecoles,
    }
    return render(request, 'ecole/certificats/fiche_suivi.html', context)


@login_required
def fiche_suivi_second_cycle_pdf(request, eleve_id):
    eleve = get_object_or_404(Eleve, id=eleve_id)
    ecole = EcoleInfo.get_solo()
    data_par_classe, matieres = _construire_fiche_suivi_data(eleve)
    moyennes_par_position = _construire_moyennes_par_tentative_chronologique(eleve)
    historique_ecoles = _construire_historique_ecoles(eleve, ecole, data_par_classe)

    moyennes_tendances = _calculer_moyennes_tendances(
        moyennes_par_position, matieres
    )

    buffer = generer_fiche_suivi_second_cycle_pdf(
        eleve, ecole, data_par_classe, matieres,
        moyennes_par_position, historique_ecoles,
        moyennes_tendances=moyennes_tendances,
    )
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="fiche_suivi_{eleve.matricule}.pdf"'
    )
    return response


@login_required
def certificat_transfert_dossier_complet_pdf(request, certificat_id):
    certificat = get_object_or_404(CertificatTransfert, id=certificat_id)
    inscription = certificat.inscription
    eleve = inscription.eleve
    ecole = EcoleInfo.get_solo()

    annee_debut = eleve.annee_recrutement[:4] if eleve.annee_recrutement else ''
    annee_fin = inscription.anneeScolaire.get_annee_fin()
    classes_doublees = _classes_doublees_affichage(eleve)

    buffer_certificat = generer_certificat_transfert_pdf(
        eleve, inscription, certificat, ecole, annee_debut, annee_fin, classes_doublees
    )

    data_par_classe, matieres = _construire_fiche_suivi_data(eleve)
    moyennes_par_position = _construire_moyennes_par_tentative_chronologique(eleve)
    historique_ecoles = _construire_historique_ecoles(eleve, ecole, data_par_classe)

    buffer_fiche = generer_fiche_suivi_second_cycle_pdf(
        eleve, ecole, data_par_classe, matieres, moyennes_par_position, historique_ecoles,
        moyennes_tendances=_calculer_moyennes_tendances(moyennes_par_position, matieres),
    )

    from PyPDF2 import PdfMerger
    merger = PdfMerger()
    merger.append(buffer_certificat)
    merger.append(buffer_fiche)

    output = io.BytesIO()
    merger.write(output)
    merger.close()
    output.seek(0)

    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="dossier_transfert_{eleve.matricule}.pdf"'
    )
    return response


@login_required
def dossiers_scolaires_index(request):
    """Page listant tous les élèves avec accès direct à leur dossier scolaire."""
    cycle = request.GET.get('cycle', '')
    classe_id = request.GET.get('classe', '')
    annee_id = request.GET.get('annee', '')
    search = request.GET.get('search', '').strip()

    inscriptions = Inscription.objects.select_related(
        'eleve', 'classe', 'anneeScolaire'
    )

    if cycle:
        inscriptions = inscriptions.filter(classe__cycle=cycle)
    if classe_id:
        inscriptions = inscriptions.filter(classe__idClasse=classe_id)
    if annee_id:
        inscriptions = inscriptions.filter(anneeScolaire__idAnneeScolaire=annee_id)
    if search:
        inscriptions = inscriptions.filter(
            Q(eleve__nomEleve__icontains=search) |
            Q(eleve__prenomEleve__icontains=search) |
            Q(eleve__matricule__icontains=search)
        )

    inscriptions = inscriptions.order_by('eleve__nomEleve', 'eleve__prenomEleve')

    classes_qs = Classe.objects.all().order_by('nomClasse')
    if cycle:
        classes_qs = classes_qs.filter(cycle=cycle)

    context = {
        'inscriptions': inscriptions,
        'classes': classes_qs,
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'cycle_filtre': cycle,
        'classe_id': classe_id,
        'annee_id': annee_id,
        'search': search,
        'total': inscriptions.count(),
    }
    return render(request, 'ecole/dossier/index_liste.html', context)


