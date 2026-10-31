"""Vues : cycle1."""
from ._deps import *
from ._helpers import *


@login_required
@permission_required('ecole.view_note', raise_exception=True)
def cycle1_saisie_notes(request):
    """Saisie des notes mensuelles - 1er cycle."""
    annee_id = request.GET.get('annee')
    classe_id = request.GET.get('classe')
    matiere_id = request.GET.get('matiere')
    mois = request.GET.get('mois')

    inscriptions = matiere = annee_scolaire = classe_nom = None
    stats = {'total': 0, 'saisies': 0, 'non_saisies': 0, 'moyenne': None, 'note_min': None, 'note_max': None}

    classes = Classe.objects.filter(cycle='1er').order_by('nomClasse')

    if classe_id:
        try:
            classe_selectionnee = Classe.objects.get(idClasse=classe_id, cycle='1er')
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

    if all([annee_id, classe_id, matiere_id, mois]):
        annee_scolaire = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_id)
        classe = get_object_or_404(Classe, idClasse=classe_id, cycle='1er')
        matiere = get_object_or_404(Matiere, idMatiere=matiere_id, cycle='1er')
        classe_nom = classe.nomClasse

        composition, _ = CompositionMensuelle.objects.get_or_create(
            mois=int(mois), anneeScolaire=annee_scolaire
        )

        inscriptions = Inscription.objects.filter(
            classe=classe, anneeScolaire=annee_scolaire
        ).select_related('eleve').order_by('eleve__nomEleve', 'eleve__prenomEleve')

        stats['total'] = inscriptions.count()
        notes_liste = []
        for ins in inscriptions:
            note_obj = NoteMensuelle.objects.filter(
                eleve=ins.eleve, matiere=matiere, composition=composition
            ).first()
            ins.note_eleve = note_obj.note if note_obj else None
            ins.note_id = note_obj.idNoteMensuelle if note_obj else None
            if note_obj:
                stats['saisies'] += 1
                notes_liste.append(float(note_obj.note))
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
        'mois_choices': Cycle.PREMIER.unites_evaluation,
        'inscriptions': inscriptions,
        'matiere': matiere,
        'annee_scolaire': annee_scolaire,
        'mois': mois,
        'mois_int': int(mois) if mois else None,
        'nom_mois': dict(Paiement.MOIS_SCOLAIRES).get(int(mois)) if mois else None,
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
        'cycle': Cycle.PREMIER,
    }
    return render(request, 'ecole/cycle1/notes/saisie.html', context)


@login_required
@permission_required('ecole.add_note', raise_exception=True)
@require_POST
def cycle1_enregistrer_notes(request):
    """Enregistre les notes mensuelles d'une classe - 1er cycle."""
    cycle = Cycle.PREMIER
    annee = get_object_or_404(AnneeScolaire, idAnneeScolaire=request.POST['annee_id'])
    classe = get_object_or_404(Classe, idClasse=request.POST['classe_id'], cycle=cycle.value)
    matiere = get_object_or_404(Matiere, idMatiere=request.POST['matiere_id'], cycle=cycle.value)
    mois = request.POST['mois']

    composition, _ = CompositionMensuelle.objects.get_or_create(
        mois=int(mois), anneeScolaire=annee
    )

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
        if eleve_id not in eleves_valides:
            continue

        note_value = value.replace(',', '.').strip()
        eleve = Eleve.objects.get(id=eleve_id)

        if not note_value:
            deleted, _ = NoteMensuelle.objects.filter(
                eleve=eleve, matiere=matiere, composition=composition
            ).delete()
            if deleted:
                compteurs['supprimees'] += 1
            continue

        try:
            note_float = float(note_value)
        except ValueError:
            compteurs['invalides'] += 1
            continue
        if not (0 <= note_float <= 10):
            compteurs['invalides'] += 1
            continue

        _, created = NoteMensuelle.objects.update_or_create(
            eleve=eleve, matiere=matiere, composition=composition,
            defaults={'note': note_float},
        )
        compteurs['inserees' if created else 'maj'] += 1

    _flash_compteurs(request, compteurs, note_max=10)
    url = reverse('fondamental:cycle1_saisie_notes')
    params = {
        'annee': request.POST['annee_id'], 'classe': request.POST['classe_id'],
        'matiere': request.POST['matiere_id'], 'mois': mois,
    }
    return redirect(f"{url}?{urlencode({k: v for k, v in params.items() if v})}")


@login_required
def cycle1_calculer_moyennes(request, classe_id, annee_scolaire, mois):
    """Calcule les moyennes mensuelles d'une classe - 1er cycle."""
    classe = get_object_or_404(Classe, idClasse=classe_id, cycle=Cycle.PREMIER.value)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    composition, _ = CompositionMensuelle.objects.get_or_create(
        mois=int(mois), anneeScolaire=annee
    )

    inscriptions = Inscription.objects.filter(
        classe=classe, anneeScolaire=annee
    ).select_related('eleve')
    nb = calculer_moyennes_classe_bulk(classe, composition, annee, inscriptions)

    messages.success(request, f"{nb} résultat(s) calculé(s) pour {composition}")
    return redirect('fondamental:cycle1_bulletin_classe', classe_id=classe_id,
                    annee_scolaire=annee_scolaire, mois=mois)


@login_required
def cycle1_classer_eleves(request, classe_id, annee_scolaire, mois):
    """Classe les élèves pour une composition mensuelle - 1er cycle."""
    classe = get_object_or_404(Classe, idClasse=classe_id, cycle=Cycle.PREMIER.value)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    composition = get_object_or_404(CompositionMensuelle, mois=int(mois), anneeScolaire=annee)

    inscriptions = Inscription.objects.filter(classe=classe, anneeScolaire=annee)
    classer_inscriptions(inscriptions, composition)

    messages.success(request, "Classement mis à jour avec succès!")
    return redirect('fondamental:cycle1_bulletin_classe', classe_id=classe_id,
                    annee_scolaire=annee_scolaire, mois=mois)


@login_required
def cycle1_bulletins_index(request):
    """Accueil des bulletins mensuels - 1er cycle."""
    annees = AnneeScolaire.objects.all().order_by('-anneeScolaire')
    annee_param = request.GET.get('annee')
    annee_encours = (
        AnneeScolaire.objects.filter(anneeScolaire=annee_param).first()
        if annee_param else annees.first()
    )

    derniers_resultats = []
    if annee_encours:
        derniers_resultats = ResultatMensuel.objects.filter(
            composition__anneeScolaire=annee_encours
        ).select_related(
            'inscription__eleve', 'inscription__classe', 'composition'
        ).order_by('-date_calcul')[:10]

    context = {
        'annee_encours': annee_encours.anneeScolaire if annee_encours else None,
        'annees_scolaires': annees,
        'classes': classes_du_cycle(Cycle.PREMIER.value),
        'mois_choices': Cycle.PREMIER.unites_evaluation,
        'derniers_resultats': derniers_resultats,
        'cycle': Cycle.PREMIER,
    }
    return render(request, 'ecole/cycle1/bulletins/index.html', context)


@login_required
def cycle1_bulletin_classe(request, classe_id, annee_scolaire, mois):
    """Bulletins d'une classe - 1er cycle."""
    classe = get_object_or_404(Classe, idClasse=classe_id, cycle=Cycle.PREMIER.value)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)

    composition = CompositionMensuelle.objects.filter(
        mois=int(mois), anneeScolaire=annee
    ).first()

    resultats = []
    matieres = []
    stats = None

    if composition:
        resultats = list(ResultatMensuel.objects.filter(
            composition=composition, inscription__classe=classe
        ).select_related('inscription__eleve').prefetch_related('details__matiere'))
        resultats.sort(key=lambda r: r.moyenne_generale, reverse=True)

        matieres, _ = _construire_matieres_et_details(resultats, attr='details')
        stats = _stats_resultats(resultats)

    context = {
        'classe': classe,
        'annee_scolaire': annee_scolaire,
        'mois': int(mois),
        'nom_mois': dict(Paiement.MOIS_SCOLAIRES).get(int(mois)),
        'resultats': resultats,
        'matieres': matieres,
        'stats': stats,
        'composition_existe': composition is not None,
        'mois_choices': Cycle.PREMIER.unites_evaluation,
        'cycle': Cycle.PREMIER,
    }
    return render(request, 'ecole/cycle1/bulletins/classe.html', context)


@login_required
def cycle1_bulletins_eleve_annee(request, eleve_id):
    """Historique des bulletins mensuels d'un élève - 1er cycle."""
    eleve = get_object_or_404(Eleve, id=eleve_id)
    annees_scolaires = AnneeScolaire.objects.all().order_by('-anneeScolaire')
    inscriptions = Inscription.objects.filter(
        eleve=eleve, classe__cycle=Cycle.PREMIER.value
    ).select_related('classe', 'anneeScolaire')

    resultats_par_annee = {}
    for inscription in inscriptions:
        annee_scolaire = inscription.anneeScolaire
        if not annee_scolaire:
            continue
        resultats = ResultatMensuel.objects.filter(
            inscription=inscription
        ).select_related('composition').order_by('composition__mois')

        if resultats.exists():
            resultats_par_annee[annee_scolaire.anneeScolaire] = {
                'inscription': inscription,
                'resultats': resultats,
            }

    annee_courante = annees_scolaires.first().anneeScolaire if annees_scolaires else None

    context = {
        'eleve': eleve,
        'annees_scolaires': annees_scolaires,
        'inscriptions': inscriptions,
        'resultats_par_annee': resultats_par_annee,
        'annee_courante': annee_courante,
        'mois_choices': Cycle.PREMIER.unites_evaluation,
        'cycle': Cycle.PREMIER,
    }
    return render(request, 'ecole/cycle1/bulletins/eleve_annee.html', context)


@login_required
def cycle1_bulletin_eleve(request, eleve_id, annee_scolaire, mois):
    """Bulletin individuel - 1er cycle."""
    eleve = get_object_or_404(Eleve, id=eleve_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    inscription = get_object_or_404(Inscription, eleve=eleve, anneeScolaire=annee)
    composition = get_object_or_404(CompositionMensuelle, mois=int(mois), anneeScolaire=annee)

    resultat = ResultatMensuel.objects.filter(
        inscription=inscription, composition=composition
    ).prefetch_related('details__matiere').first()

    total_notes = 0
    nb_matieres_notees = 0
    if resultat:
        for detail in resultat.details.all():
            if detail.note is not None:
                total_notes += float(detail.note)
                nb_matieres_notees += 1

    moyenne_notes = (
        round(total_notes / nb_matieres_notees, 2)
        if nb_matieres_notees > 0 else 0
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

    effectif_classe = ResultatMensuel.objects.filter(
        inscription__classe=inscription.classe,
        composition=composition,
    ).count()

    class_stats = _stats_classe(
        ResultatMensuel, inscription.classe, {'composition': composition}, resultat
    )

    context = {
        'eleve': eleve,
        'inscription': inscription,
        'resultat': resultat,
        'annee_scolaire': annee_scolaire,
        'mois': int(mois),
        'nom_mois': dict(Paiement.MOIS_SCOLAIRES).get(int(mois)),
        'mois_choices': Cycle.PREMIER.unites_evaluation,
        'class_stats': class_stats,
        'cycle': Cycle.PREMIER,
        'ecole': EcoleInfo.get_solo(),

        'total_notes': total_notes,
        'moyenne_notes': moyenne_notes,
        'nb_matieres_notees': nb_matieres_notees,
        'rang_affiche': rang_affiche,
        'effectif_classe': effectif_classe,
    }
    return render(request, 'ecole/cycle1/bulletins/eleve.html', context)


@login_required
def cycle1_bulletin_eleve_pdf(request, eleve_id, annee_scolaire, mois):
    """PDF du bulletin mensuel - 1er cycle."""
    eleve = get_object_or_404(Eleve, id=eleve_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    inscription = get_object_or_404(Inscription, eleve=eleve, anneeScolaire=annee)
    composition = get_object_or_404(
        CompositionMensuelle, mois=int(mois), anneeScolaire=annee
    )
    ecole = EcoleInfo.get_solo()

    resultat = get_object_or_404(
        ResultatMensuel.objects.prefetch_related('details__matiere'),
        inscription=inscription, composition=composition
    )

    total_notes = 0
    nb_matieres_notees = 0
    for detail in resultat.details.all():
        if detail.note is not None:
            total_notes += float(detail.note)
            nb_matieres_notees += 1

    moyenne_notes = (
        round(total_notes / nb_matieres_notees, 2)
        if nb_matieres_notees > 0 else 0
    )

    rang_affiche = "-"
    if resultat.rang:
        if resultat.rang == 1:
            if eleve.sexe == 'M':
                rang_affiche = "1er"
            elif eleve.sexe == 'F':
                rang_affiche = "1ère"
            else:
                rang_affiche = "1er"
        else:
            rang_affiche = f"{resultat.rang}ème"

    effectif_classe = ResultatMensuel.objects.filter(
        inscription__classe=inscription.classe,
        composition=composition,
    ).count()

    class_stats = _stats_classe(
        ResultatMensuel, inscription.classe,
        {'composition': composition}, resultat
    )
    class_stats['rang'] = resultat.rang or 0
    class_stats['effectif'] = effectif_classe

    meilleur_resultat = ResultatMensuel.objects.filter(
        inscription__classe=inscription.classe,
        composition=composition,
    ).select_related('inscription__eleve').order_by('-moyenne_generale').first()

    if meilleur_resultat:
        moyenne_premier = float(meilleur_resultat.moyenne_generale)
        nom_premier_eleve = (
            f"{meilleur_resultat.inscription.eleve.prenomEleve} "
            f"{meilleur_resultat.inscription.eleve.nomEleve}"
        )
    else:
        moyenne_premier = 0
        nom_premier_eleve = ""

    buffer = generer_bulletin_mensuel_pdf_eleve(
        eleve=eleve,
        inscription=inscription,
        resultat=resultat,
        class_stats=class_stats,
        ecole=ecole,
        annee_scolaire=annee_scolaire,
        composition=composition,
        total_notes=total_notes,
        moyenne_notes=moyenne_notes,
        nb_matieres_notees=nb_matieres_notees,
        rang_affiche=rang_affiche,
        effectif_classe=effectif_classe,
        moyenne_premier=moyenne_premier,
        nom_premier_eleve=nom_premier_eleve,
    )

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="bulletin_{eleve.matricule}_'
        f'{composition.get_mois_display()}_{annee_scolaire}.pdf"'
    )
    return response


@login_required
@permission_required('ecole.view_note', raise_exception=True)
def cycle1_notes_list(request):
    """Liste des notes mensuelles - 1er cycle."""
    from ..models import NoteMensuelle

    search = request.GET.get('search', '').strip()
    classe_id = request.GET.get('classe', '')
    matiere_id = request.GET.get('matiere', '')
    annee_id = request.GET.get('annee', '')
    mois = request.GET.get('mois', '')

    notes = NoteMensuelle.objects.select_related(
        'eleve', 'matiere', 'composition', 'composition__anneeScolaire'
    ).all()

    if search:
        notes = notes.filter(
            Q(eleve__nomEleve__icontains=search) |
            Q(eleve__prenomEleve__icontains=search) |
            Q(eleve__matricule__icontains=search)
        )
    if classe_id:
        notes = notes.filter(eleve__inscription__classe__idClasse=classe_id)
    if matiere_id:
        notes = notes.filter(matiere__idMatiere=matiere_id)
    if annee_id:
        notes = notes.filter(composition__anneeScolaire__idAnneeScolaire=annee_id)
    if mois:
        notes = notes.filter(composition__mois=int(mois))

    notes = notes.order_by(
        '-composition__anneeScolaire__anneeScolaire',
        'eleve__nomEleve',
        'eleve__prenomEleve',
        'matiere__nomMatiere',
    )

    paginator = Paginator(notes, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    eleve_ids = [n.eleve_id for n in page_obj]
    annee_ids = [n.composition.anneeScolaire_id for n in page_obj]

    inscriptions_map = {}
    if eleve_ids and annee_ids:
        inscriptions = Inscription.objects.filter(
            eleve_id__in=eleve_ids,
            anneeScolaire_id__in=annee_ids,
        ).select_related('classe')
        for ins in inscriptions:
            inscriptions_map[(ins.eleve_id, ins.anneeScolaire_id)] = ins

    for note in page_obj:
        key = (note.eleve_id, note.composition.anneeScolaire_id)
        note.inscription_courante = inscriptions_map.get(key)

    matieres_affichees = []
    classe_sans_matieres = False

    if classe_id:
        try:
            classe_selectionnee = Classe.objects.get(idClasse=classe_id)
            matieres_affichees = _matieres_classe_annee(classe_selectionnee, annee_id)

            if not matieres_affichees:
                classe_sans_matieres = True

        except Classe.DoesNotExist:
            pass
    else:
        matieres_affichees = list(Matiere.objects.filter(cycle='1er').order_by('nomMatiere'))

    context = {
        'notes': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),

        'classes': Classe.objects.filter(cycle='1er').order_by('nomClasse'),
        'matieres': matieres_affichees,
        'classe_sans_matieres': classe_sans_matieres,
        'annees_scolaires': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'mois_choices': Paiement.MOIS_SCOLAIRES_ORDONNES,

        'search': search,
        'classe_filter': classe_id,
        'matiere_filter': matiere_id,
        'annee_filter': annee_id,
        'mois_filter': mois,

        'cycle': Cycle.PREMIER,
    }
    return render(request, 'ecole/cycle1/notes/list.html', context)


@login_required
def cycle1_exporter_bulletins_pdf(request, classe_id, annee_scolaire, mois):
    """Export PDF de tous les bulletins d'une classe - 1er cycle."""
    classe = get_object_or_404(Classe, idClasse=classe_id, cycle=Cycle.PREMIER.value)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    composition = get_object_or_404(
        CompositionMensuelle, mois=int(mois), anneeScolaire=annee
    )
    ecole = EcoleInfo.get_solo()

    resultats = ResultatMensuel.objects.filter(
        composition=composition,
        inscription__classe=classe
    ).select_related(
        'inscription__eleve'
    ).prefetch_related('details__matiere').order_by('-moyenne_generale')

    if not resultats.exists():
        messages.warning(
            request,
            "Aucun résultat disponible pour cette classe et ce mois. "
            "Commencez par calculer les moyennes."
        )
        return redirect(
            'fondamental:cycle1_bulletin_classe',
            classe_id=classe_id,
            annee_scolaire=annee_scolaire,
            mois=mois
        )

    resultats = list(resultats)
    effectif_classe = len(resultats)

    moyennes = [float(r.moyenne_generale) for r in resultats]
    moyenne_classe = round(sum(moyennes) / len(moyennes), 2) if moyennes else 0

    if resultats:
        premier_resultat = resultats[0]
        premier_eleve = premier_resultat.inscription.eleve
        moyenne_premier = float(premier_resultat.moyenne_generale)
    else:
        premier_eleve = None
        moyenne_premier = 0

    try:
        from PyPDF2 import PdfMerger
        import tempfile

        merger = PdfMerger()
        temp_files = []

        for resultat in resultats:
            eleve = resultat.inscription.eleve
            inscription = resultat.inscription

            total_notes = 0
            nb_matieres_notees = 0
            for detail in resultat.details.all():
                if detail.note is not None:
                    total_notes += float(detail.note)
                    nb_matieres_notees += 1

            moyenne_notes = (
                round(total_notes / nb_matieres_notees, 2)
                if nb_matieres_notees > 0 else 0
            )

            rang_affiche = "-"
            if resultat.rang:
                if resultat.rang == 1:
                    if eleve.sexe == 'M':
                        rang_affiche = "1er"
                    elif eleve.sexe == 'F':
                        rang_affiche = "1ère"
                    else:
                        rang_affiche = "1er"
                else:
                    rang_affiche = f"{resultat.rang}ème"

            class_stats = {
                'moyenne_classe': moyenne_classe,
                'effectif': effectif_classe,
                'rang': resultat.rang or 0,
            }

            pdf_buffer = generer_bulletin_mensuel_pdf_eleve(
                eleve=eleve,
                inscription=inscription,
                resultat=resultat,
                class_stats=class_stats,
                ecole=ecole,
                annee_scolaire=annee_scolaire,
                composition=composition,
                total_notes=total_notes,
                moyenne_notes=moyenne_notes,
                nb_matieres_notees=nb_matieres_notees,
                rang_affiche=rang_affiche,
                effectif_classe=effectif_classe,

                moyenne_premier=moyenne_premier,
                nom_premier_eleve=(
                    f"{premier_eleve.prenomEleve} {premier_eleve.nomEleve}"
                    if premier_eleve else ""
                ),
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

        nom_mois = dict(Paiement.MOIS_SCOLAIRES).get(int(mois), f"mois_{mois}")
        filename = f"bulletins_{classe.nomClasse}_{nom_mois}_{annee_scolaire}.pdf"

        response = HttpResponse(output.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except ImportError:
        messages.error(request, "PyPDF2 n'est pas installée.")
        return redirect(
            'fondamental:cycle1_bulletin_classe',
            classe_id=classe_id,
            annee_scolaire=annee_scolaire,
            mois=mois
        )
    except Exception as e:
        messages.error(request, f"Erreur PDF : {str(e)}")
        return redirect(
            'fondamental:cycle1_bulletin_classe',
            classe_id=classe_id,
            annee_scolaire=annee_scolaire,
            mois=mois
        )


