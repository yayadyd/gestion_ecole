"""Vues : cycle2."""
from ._deps import *
from ._helpers import *


@login_required
@permission_required('ecole.view_note', raise_exception=True)
def cycle2_saisie_notes(request):
    """Saisie des notes trimestrielles - 2e cycle."""
    annee_id = request.GET.get('annee')
    classe_id = request.GET.get('classe')
    matiere_id = request.GET.get('matiere')
    trimestre = request.GET.get('trimestre')

    inscriptions = matiere = annee_scolaire = classe_nom = evaluation = None
    stats = {'total': 0, 'saisies': 0, 'non_saisies': 0, 'moyenne': None, 'note_min': None, 'note_max': None}

    classes = Classe.objects.filter(cycle='2e').order_by('nomClasse')

    if classe_id:
        try:
            classe_selectionnee = Classe.objects.get(idClasse=classe_id, cycle='2e')
            # ✅ FIX: Filtrer les matières par classe ET par année (si année fournie)
            matieres_classe = MatiereClasse.objects.filter(
                classe=classe_selectionnee
            )
            if annee_id:
                matieres_classe = matieres_classe.filter(annee_scolaire_id=annee_id)
                
            matieres_classe = matieres_classe.select_related('matiere').order_by('ordre_affichage', 'matiere__nomMatiere')
            matieres = [mc.matiere for mc in matieres_classe]
        except Classe.DoesNotExist:
            matieres = []
    else:
        matieres = []

    if all([annee_id, classe_id, matiere_id, trimestre]):
        annee_scolaire = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_id)
        classe = get_object_or_404(Classe, idClasse=classe_id, cycle='2e')
        matiere = get_object_or_404(Matiere, idMatiere=matiere_id, cycle='2e')
        classe_nom = classe.nomClasse

        evaluation, _ = Evaluation.objects.get_or_create(nomEvaluation=trimestre)
        inscriptions = Inscription.objects.filter(
            classe=classe, anneeScolaire=annee_scolaire
        ).select_related('eleve').order_by('eleve__nomEleve', 'eleve__prenomEleve')

        stats['total'] = inscriptions.count()
        notes_liste = []
        for ins in inscriptions:
            note = Note.objects.filter(
                eleve=ins.eleve, matiere=matiere,
                anneeScolaire=annee_scolaire, evaluation=evaluation
            ).first()
            ins.note_eleve = note.note if note else None
            ins.note_classe = note.noteClasse if note else None
            ins.note_id = note.idNote if note else None
            if note:
                stats['saisies'] += 1
                notes_liste.append(float(note.note))
            else:
                stats['non_saisies'] += 1

        if notes_liste:
            stats['moyenne'] = round(sum(notes_liste) / len(notes_liste), 2)
            stats['note_min'] = round(min(notes_liste), 2)
            stats['note_max'] = round(max(notes_liste), 2)

    context = {
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'classes': classes,
        'matieres': matieres,
        'trimestres': dict(Evaluation.TRIMESTRE),
        'inscriptions': inscriptions,
        'matiere': matiere,
        'annee_scolaire': annee_scolaire,
        'trimestre': trimestre,
        'annee_id': annee_id,
        'classe_id': classe_id,
        'matiere_id': matiere_id,
        'classe_nom': classe_nom,
        'total_eleves': stats['total'],
        'notes_saisies': stats['saisies'],
        'notes_non_saisies': stats['non_saisies'],
        'moyenne_classe': stats['moyenne'],
        'note_min': stats['note_min'],
        'note_max': stats['note_max'],
        'cycle': Cycle.SECOND,
    }
    return render(request, 'ecole/cycle2/notes/saisie.html', context)


@login_required
@permission_required('ecole.add_note', raise_exception=True)
@require_POST
def cycle2_enregistrer_notes(request):
    """Enregistre les notes trimestrielles - 2e cycle."""
    cycle = Cycle.SECOND
    annee = get_object_or_404(AnneeScolaire, idAnneeScolaire=request.POST['annee_id'])
    matiere = get_object_or_404(Matiere, idMatiere=request.POST['matiere_id'], cycle=cycle.value)
    classe = get_object_or_404(Classe, idClasse=request.POST['classe_id'], cycle=cycle.value) \
        if request.POST.get('classe_id') else None
    evaluation, _ = Evaluation.objects.get_or_create(nomEvaluation=request.POST['trimestre'])

    eleves_valides = set()
    if classe:
        eleves_valides = set(
            Inscription.objects.filter(classe=classe, anneeScolaire=annee)
            .values_list('eleve_id', flat=True)
        )

    compteurs = {'inserees': 0, 'maj': 0, 'supprimees': 0, 'invalides': 0}

    for key, value in request.POST.items():
        if not (key.startswith('note_') and key.endswith('_note')):
            continue
        eleve_id_str = key[len('note_'):-len('_note')]
        if not eleve_id_str.isdigit():
            continue
        eleve_id = int(eleve_id_str)
        if classe and eleve_id not in eleves_valides:
            continue

        note_value = value.replace(',', '.').strip()
        note_classe_raw = request.POST.get(
            f'note_{eleve_id}_classe', ''
        ).replace(',', '.').strip()
        eleve = Eleve.objects.get(id=eleve_id)

        if not note_value:
            deleted, _ = Note.objects.filter(
                eleve=eleve, matiere=matiere, evaluation=evaluation, anneeScolaire=annee
            ).delete()
            if deleted:
                compteurs['supprimees'] += 1
            continue

        try:
            note_float = float(note_value)
        except ValueError:
            compteurs['invalides'] += 1
            continue
        if not (0 <= note_float <= 20):
            compteurs['invalides'] += 1
            continue

        note_existante = Note.objects.filter(
            eleve=eleve, matiere=matiere, evaluation=evaluation, anneeScolaire=annee
        ).first()

        if note_classe_raw:
            try:
                note_classe = float(note_classe_raw)
            except ValueError:
                compteurs['invalides'] += 1
                continue
            if not (0 <= note_classe <= 20):
                compteurs['invalides'] += 1
                continue
        else:
            note_classe = note_existante.noteClasse if note_existante else 0

        _, created = Note.objects.update_or_create(
            eleve=eleve, matiere=matiere, evaluation=evaluation, anneeScolaire=annee,
            defaults={'note': note_float, 'noteClasse': note_classe},
        )
        compteurs['inserees' if created else 'maj'] += 1

    _flash_compteurs(request, compteurs)
    url = reverse('fondamental:cycle2_saisie_notes')
    params = {
        'annee': request.POST['annee_id'], 'classe': request.POST['classe_id'],
        'matiere': request.POST['matiere_id'], 'trimestre': request.POST['trimestre'],
    }
    return redirect(f"{url}?{urlencode({k: v for k, v in params.items() if v})}")


@login_required
def cycle2_calculer_moyennes(request, annee_scolaire, trimestre):
    """Calcule les moyennes trimestrielles - 2e cycle."""
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    # Calcul classe par classe, en lot (quelques requêtes par classe).
    nb = 0
    for classe in Classe.objects.filter(cycle=Cycle.SECOND.value).order_by('nomClasse'):
        nb += calculer_moyennes_classe_bulk(classe, trimestre, annee)
    messages.success(request, f"{nb} résultat(s) calculé(s) pour {trimestre}")

    url = reverse('fondamental:cycle2_bulletins_classe', kwargs={
        'annee_scolaire': annee_scolaire, 'trimestre': trimestre,
    })
    return redirect(url)


@login_required
def cycle2_classer_eleves(request, annee_scolaire, trimestre):
    """Classe les élèves par classe - 2e cycle."""
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)

    classes = Classe.objects.filter(cycle=Cycle.SECOND.value).order_by('nomClasse')

    total_classe = 0
    for classe in classes:
        inscriptions = Inscription.objects.filter(
            anneeScolaire=annee,
            classe=classe,
        )

        if not inscriptions.exists():
            continue

        resultats_classes = classer_inscriptions(inscriptions, trimestre)
        nb = len(resultats_classes) if resultats_classes else 0
        total_classe += 1

        messages.info(
            request,
            f"{classe.nomClasse} : {nb} élève(s) classé(s)"
        )

    messages.success(
        request,
        f"Classement mis à jour pour {total_classe} classe(s) - {trimestre}"
    )
    return redirect(
        'fondamental:cycle2_bulletins_classe',
        annee_scolaire=annee_scolaire,
        trimestre=trimestre
    )


@login_required
def cycle2_bulletins_index(request):
    """Accueil des bulletins - 2e cycle."""
    annees_scolaires = AnneeScolaire.objects.all().order_by('-anneeScolaire')
    annee_selectionnee = request.GET.get('annee')
    annee_encours = None
    if annee_selectionnee:
        annee_encours = AnneeScolaire.objects.filter(anneeScolaire=annee_selectionnee).first()
    else:
        annee_encours = annees_scolaires.first()

    annee_encours_str = annee_encours.anneeScolaire if annee_encours else "2025-2026"
    classes = classes_du_cycle(Cycle.SECOND.value)
    trimestres = dict(Evaluation.TRIMESTRE)

    derniers_resultats = []
    if annee_encours:
        derniers_resultats = ResultatTrimestre.objects.filter(
            anneeScolaire=annee_encours
        ).select_related(
            'inscription__eleve', 'inscription__classe'
        ).order_by('-date_calcul')[:10]

    stats_par_annee = []
    for annee in annees_scolaires[:5]:
        nb_inscriptions = Inscription.objects.filter(anneeScolaire=annee).count()
        nb_resultats = ResultatTrimestre.objects.filter(anneeScolaire=annee).count()
        stats_par_annee.append({
            'annee': annee,
            'nb_inscriptions': nb_inscriptions,
            'nb_resultats': nb_resultats,
        })

    context = {
        'annee_encours': annee_encours_str,
        'annee_selectionnee': annee_selectionnee,
        'annees_scolaires': annees_scolaires,
        'classes': classes,
        'trimestres': trimestres,
        'derniers_resultats': derniers_resultats,
        'stats_par_annee': stats_par_annee,
        'title': 'Bulletins de notes - 2e Cycle',
        'cycle': Cycle.SECOND,
    }
    return render(request, 'ecole/cycle2/bulletins/index.html', context)


@login_required
def bulletins_choix(request):
    """Page de sélection du cycle pour les bulletins."""
    return render(request, 'ecole/bulletins/choix.html')


@login_required
def notes_choix(request):
    """Page de sélection du cycle pour la saisie/consultation des notes."""
    return render(request, 'ecole/note/choix.html')


@login_required
def cycle2_bulletins_classe(request, annee_scolaire, trimestre, classe_id=None):
    """Bulletins d'une classe (ou de toutes) - 2e cycle."""
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    classes = classes_du_cycle(Cycle.SECOND.value)

    resultats = ResultatTrimestre.objects.filter(
        anneeScolaire=annee, trimestre=trimestre
    ).select_related(
        'inscription__eleve', 'inscription__classe'
    ).prefetch_related('details__matiere')

    classe_filtree = None
    if classe_id:
        classe_filtree = get_object_or_404(Classe, idClasse=classe_id)
        resultats = resultats.filter(inscription__classe=classe_filtree)

    resultats_par_classe = {}
    for resultat in resultats:
        classe = resultat.inscription.classe
        resultats_par_classe.setdefault(classe, []).append(resultat)

    matieres_par_classe = {}
    for classe, resultats_classe in resultats_par_classe.items():
        resultats_classe.sort(key=lambda x: x.moyenne_generale, reverse=True)
        matieres, _ = _construire_matieres_et_details(resultats_classe, attr='details')
        matieres_par_classe[classe] = matieres

    stats_par_classe = {c: _stats_resultats(r) for c, r in resultats_par_classe.items()}

    context = {
        'resultats_par_classe': resultats_par_classe,
        'matieres_par_classe': matieres_par_classe,
        'stats_par_classe': stats_par_classe,
        'annee_scolaire': annee_scolaire,
        'trimestre': trimestre,
        'trimestres': dict(Evaluation.TRIMESTRE),
        'classes': classes,
        'annee': annee,
        'classe_filtree': classe_filtree,
        'cycle': Cycle.SECOND,
    }
    return render(request, 'ecole/cycle2/bulletins/classe.html', context)


@login_required
def cycle2_bulletin_eleve(request, eleve_id, annee_scolaire, trimestre):
    """Bulletin individuel - 2e cycle."""
    eleve = get_object_or_404(Eleve, id=eleve_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    inscription = get_object_or_404(Inscription, eleve=eleve, anneeScolaire=annee)

    resultat = ResultatTrimestre.objects.filter(
        inscription=inscription, trimestre=trimestre, anneeScolaire=annee
    ).prefetch_related('details__matiere').first()

    total_moy_coef = 0
    total_coef = 0
    if resultat:
        for detail in resultat.details.all():
            total_moy_coef += float(detail.moyenne_coefficientee)
            total_coef += float(detail.coef)

    moyenne_generale = (
        _moyenne_bulletin(resultat, total_moy_coef, total_coef)
    )

    rang_affiche = "-"
    if resultat and resultat.rang:
        if resultat.rang == 1:
            if eleve.sexe == 'M':
                rang_affiche = "1er"
            elif eleve.sexe == 'F':
                rang_affiche = "1ère"
            else:
                rang_affiche = "1er"
        else:
            rang_affiche = f"{resultat.rang}ème"

    effectif_classe = ResultatTrimestre.objects.filter(
        inscription__classe=inscription.classe,
        trimestre=trimestre,
        anneeScolaire=annee,
    ).count()

    meilleur = ResultatTrimestre.objects.filter(
        inscription__classe=inscription.classe,
        trimestre=trimestre,
        anneeScolaire=annee,
    ).select_related('inscription__eleve').order_by('-moyenne_generale').first()

    if meilleur:
        moyenne_premier = float(meilleur.moyenne_generale)
        nom_premier_eleve = (
            f"{meilleur.inscription.eleve.prenomEleve} "
            f"{meilleur.inscription.eleve.nomEleve}"
        )
    else:
        moyenne_premier = 0
        nom_premier_eleve = ""

    class_stats = _stats_classe(
        ResultatTrimestre, inscription.classe,
        {'trimestre': trimestre, 'anneeScolaire': annee}, resultat
    )
    class_stats['rang'] = resultat.rang if resultat else 0
    class_stats['effectif'] = effectif_classe

    context = {
        'eleve': eleve,
        'inscription': inscription,
        'resultat': resultat,
        'annee_scolaire': annee_scolaire,
        'trimestre': trimestre,
        'trimestres': dict(Evaluation.TRIMESTRE),
        'class_stats': class_stats,
        'annee': annee,
        'annees_scolaires': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'est_1er_cycle': False,
        'cycle': Cycle.SECOND,
        'ecole': EcoleInfo.get_solo(),

        'total_moyennes_coefficientees': round(total_moy_coef, 2),
        'total_coefficients': total_coef,
        'moyenne_generale': moyenne_generale,
        'rang_affiche': rang_affiche,
        'effectif_classe': effectif_classe,
        'moyenne_premier': moyenne_premier,
        'nom_premier_eleve': nom_premier_eleve,
    }
    return render(request, 'ecole/cycle2/bulletins/eleve.html', context)


@login_required
def cycle2_bulletin_eleve_pdf(request, eleve_id, annee_scolaire, trimestre):
    """Export PDF du bulletin individuel d'un élève - 2e cycle."""
    eleve = get_object_or_404(Eleve, id=eleve_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    inscription = get_object_or_404(Inscription, eleve=eleve, anneeScolaire=annee)

    resultat = get_object_or_404(
        ResultatTrimestre.objects.prefetch_related('details__matiere'),
        inscription=inscription, trimestre=trimestre, anneeScolaire=annee
    )

    total_moy_coef = 0
    total_coef = 0
    for detail in resultat.details.all():
        total_moy_coef += float(detail.moyenne_coefficientee)
        total_coef += float(detail.coef)

    moyenne_generale = (
        _moyenne_bulletin(resultat, total_moy_coef, total_coef)
    )

    rang_affiche = "-"
    if resultat.rang:
        if resultat.rang == 1:
            rang_affiche = "1er" if eleve.sexe != 'F' else "1ère"
        else:
            rang_affiche = f"{resultat.rang}ème"

    effectif_classe = ResultatTrimestre.objects.filter(
        inscription__classe=inscription.classe,
        trimestre=trimestre,
        anneeScolaire=annee,
    ).count()

    meilleur = ResultatTrimestre.objects.filter(
        inscription__classe=inscription.classe,
        trimestre=trimestre,
        anneeScolaire=annee,
    ).select_related('inscription__eleve').order_by('-moyenne_generale').first()

    if meilleur:
        moyenne_premier = float(meilleur.moyenne_generale)
        nom_premier_eleve = (
            f"{meilleur.inscription.eleve.prenomEleve} "
            f"{meilleur.inscription.eleve.nomEleve}"
        )
    else:
        moyenne_premier = 0
        nom_premier_eleve = ""

    class_stats = _stats_classe(
        ResultatTrimestre, inscription.classe,
        {'trimestre': trimestre, 'anneeScolaire': annee}, resultat
    )
    class_stats['rang'] = resultat.rang or 0
    class_stats['effectif'] = effectif_classe

    buffer = generer_bulletin_pdf_eleve(
        eleve=eleve,
        inscription=inscription,
        resultat=resultat,
        class_stats=class_stats,
        annee_scolaire=annee_scolaire,
        trimestre=trimestre,

        total_moyennes_coefficientees=total_moy_coef,
        total_coefficients=total_coef,
        moyenne_generale=moyenne_generale,
        rang_affiche=rang_affiche,
        effectif_classe=effectif_classe,
        moyenne_premier=moyenne_premier,
        nom_premier_eleve=nom_premier_eleve,
    )

    trimestre_clean = trimestre.replace(' ', '_')
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="bulletin_{eleve.matricule}_{trimestre_clean}_{annee_scolaire}.pdf"'
    )
    return response


@login_required
def cycle2_bulletins_eleve_annee(request, eleve_id):
    """Sélection d'année pour les bulletins d'un élève - 2e cycle."""
    eleve = get_object_or_404(Eleve, id=eleve_id)
    annees_scolaires = AnneeScolaire.objects.all().order_by('-anneeScolaire')
    inscriptions = Inscription.objects.filter(eleve=eleve).select_related('classe', 'anneeScolaire')

    resultats_par_annee = {}
    for inscription in inscriptions:
        annee_scolaire = inscription.anneeScolaire
        if annee_scolaire:
            annee_key = annee_scolaire.anneeScolaire
            resultats = ResultatTrimestre.objects.filter(
                inscription=inscription
            ).prefetch_related('details__matiere')
            if resultats.exists():
                resultats_par_annee[annee_key] = resultats

    annee_courante = annees_scolaires.first().anneeScolaire if annees_scolaires else None

    context = {
        'eleve': eleve,
        'annees_scolaires': annees_scolaires,
        'resultats_par_annee': resultats_par_annee,
        'inscriptions': inscriptions,
        'annee_courante': annee_courante,
        'trimestres': dict(Evaluation.TRIMESTRE),
        'cycle': Cycle.SECOND,
    }
    return render(request, 'ecole/cycle2/bulletins/eleve_annee.html', context)


@login_required
def cycle2_exporter_bulletins_pdf(request, annee_scolaire, trimestre):
    """Export PDF de tous les bulletins d'un trimestre - 2e cycle."""
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    resultats = ResultatTrimestre.objects.filter(
        anneeScolaire=annee, trimestre=trimestre
    ).select_related(
        'inscription__eleve', 'inscription__classe'
    ).prefetch_related('details__matiere').order_by('-moyenne_generale')

    if not resultats:
        messages.warning(request, "Aucun résultat disponible pour ce trimestre.")
        return redirect('fondamental:cycle2_bulletins_classe',
                        annee_scolaire=annee_scolaire, trimestre=trimestre)

    resultats = list(resultats)

    stats_par_classe = {}
    premier_par_classe = {}

    for resultat in resultats:
        classe_id = resultat.inscription.classe_id
        if classe_id not in stats_par_classe:
            resultats_classe = [r for r in resultats if r.inscription.classe_id == classe_id]
            moyennes = [r.moyenne_generale for r in resultats_classe]
            stats_par_classe[classe_id] = {
                'moyenne_classe': round(sum(moyennes) / len(moyennes), 2) if moyennes else 0,
                'effectif': len(resultats_classe),
            }
            premier = resultats_classe[0]
            premier_par_classe[classe_id] = {
                'moyenne': float(premier.moyenne_generale),
                'nom': (
                    f"{premier.inscription.eleve.prenomEleve} "
                    f"{premier.inscription.eleve.nomEleve}"
                ),
            }

    try:
        from PyPDF2 import PdfMerger
        import tempfile

        merger = PdfMerger()
        temp_files = []

        for resultat in resultats:
            eleve = resultat.inscription.eleve
            inscription = resultat.inscription
            classe_id = inscription.classe_id

            total_moy_coef = 0
            total_coef = 0
            for detail in resultat.details.all():
                total_moy_coef += float(detail.moyenne_coefficientee)
                total_coef += float(detail.coef)

            moyenne_generale = (
                _moyenne_bulletin(resultat, total_moy_coef, total_coef)
            )

            rang_affiche = "-"
            if resultat.rang:
                if resultat.rang == 1:
                    rang_affiche = "1er" if eleve.sexe != 'F' else "1ère"
                else:
                    rang_affiche = f"{resultat.rang}ème"

            stats = stats_par_classe[classe_id]
            premier_info = premier_par_classe[classe_id]

            class_stats = {
                'moyenne_classe': stats['moyenne_classe'],
                'effectif': stats['effectif'],
                'rang': resultat.rang or 0,
            }

            pdf_buffer = generer_bulletin_pdf_eleve(
                eleve=eleve,
                inscription=inscription,
                resultat=resultat,
                class_stats=class_stats,
                annee_scolaire=annee_scolaire,
                trimestre=trimestre,

                total_moyennes_coefficientees=total_moy_coef,
                total_coefficients=total_coef,
                moyenne_generale=moyenne_generale,
                rang_affiche=rang_affiche,
                effectif_classe=stats['effectif'],
                moyenne_premier=premier_info['moyenne'],
                nom_premier_eleve=premier_info['nom'],
            )

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file.write(pdf_buffer.getvalue())
            temp_file.close()
            temp_files.append(temp_file.name)
            merger.append(temp_file.name)

        output = io.BytesIO()
        merger.write(output)
        merger.close()

        for f in temp_files:
            try:
                os.unlink(f)
            except Exception:
                pass

        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="bulletins_{annee_scolaire}_{trimestre}.pdf"'
        )
        return response

    except ImportError:
        messages.error(request, "PyPDF2 n'est pas installée.")
        return redirect('fondamental:cycle2_bulletins_classe',
                        annee_scolaire=annee_scolaire, trimestre=trimestre)
    except Exception as e:
        messages.error(request, f"Erreur lors de la génération du PDF: {str(e)}")
        return redirect('fondamental:cycle2_bulletins_classe',
                        annee_scolaire=annee_scolaire, trimestre=trimestre)


