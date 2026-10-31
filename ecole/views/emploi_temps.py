"""Vues : emploi_temps."""
from ._deps import *
from ._helpers import *


@login_required
def plage_horaire_list(request):
    """Liste des plages horaires de l'école, séparées par cycle."""
    cycle_filtre = request.GET.get('cycle', '')

    plages_1er = PlageHoraire.objects.filter(
        cycle='1er'
    ).order_by('ordre', 'heure_debut')

    plages_2e = PlageHoraire.objects.filter(
        cycle='2e'
    ).order_by('ordre', 'heure_debut')

    if cycle_filtre == '1er':
        plages = plages_1er
    elif cycle_filtre == '2e':
        plages = plages_2e
    else:
        plages = PlageHoraire.objects.all().order_by('cycle', 'ordre', 'heure_debut')

    context = {
        'plages': plages,
        'plages_1er': plages_1er,
        'plages_2e': plages_2e,
        'cycle_filtre': cycle_filtre,
        'total': plages.count(),
        'nb_1er': plages_1er.count(),
        'nb_2e': plages_2e.count(),
        'nb_pauses_1er': plages_1er.filter(est_pause=True).count(),
        'nb_pauses_2e': plages_2e.filter(est_pause=True).count(),
        'nb_pauses': plages.filter(est_pause=True).count(),
        'nb_cours': plages.filter(est_pause=False).count(),
    }
    return render(request, 'ecole/emploi_temps/plage/list.html', context)


class PlageHoraireCreateView(LoginRequiredMixin, CreateView):
    model = PlageHoraire
    form_class = PlageHoraireForm
    template_name = 'ecole/emploi_temps/plage/form.html'
    success_url = reverse_lazy('fondamental:plage_horaire_list')

    def get_initial(self):
        initial = super().get_initial()
        cycle = self.request.GET.get('cycle')
        if cycle in ('1er', '2e'):
            initial['cycle'] = cycle
        return initial

    def form_valid(self, form):
        messages.success(self.request, "Plage horaire créée avec succès !")
        return super().form_valid(form)

    def form_invalid(self, form):
        
        return super().form_invalid(form)


class PlageHoraireUpdateView(LoginRequiredMixin, UpdateView):
    model = PlageHoraire
    form_class = PlageHoraireForm
    template_name = 'ecole/emploi_temps/plage/form.html'
    success_url = reverse_lazy('fondamental:plage_horaire_list')

    def form_valid(self, form):
        messages.success(self.request, "Plage horaire mise à jour avec succès !")
        return super().form_valid(form)

    def form_invalid(self, form):
        
        return super().form_invalid(form)


class PlageHoraireDeleteView(LoginRequiredMixin, DeleteView):
    model = PlageHoraire
    template_name = 'ecole/emploi_temps/plage/confirm_delete.html'
    success_url = reverse_lazy('fondamental:plage_horaire_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Plage horaire supprimée avec succès !")
        return super().delete(request, *args, **kwargs)


@login_required
def emploi_temps_index(request):
    """Page d'accueil : liste des classes avec accès à leur emploi du temps."""
    annee_param = request.GET.get('annee')
    cycle = request.GET.get('cycle', '')

    annees_scolaires = AnneeScolaire.objects.all().order_by('-anneeScolaire')

    annee_selectionnee = None
    if annee_param:
        if annee_param.isdigit():
            annee_selectionnee = AnneeScolaire.objects.filter(
                idAnneeScolaire=annee_param
            ).first()
        if not annee_selectionnee:
            annee_selectionnee = AnneeScolaire.objects.filter(
                anneeScolaire=annee_param
            ).first()

    if not annee_selectionnee:
        annee_selectionnee = annees_scolaires.first()

    classes_1er = Classe.objects.filter(cycle='1er').order_by('nomClasse')
    classes_2e = Classe.objects.filter(cycle='2e').order_by('nomClasse')

    emplois_existants = {}
    if annee_selectionnee:
        for et in EmploiTemps.objects.filter(anneeScolaire=annee_selectionnee):
            emplois_existants[et.classe_id] = et

    def enrichir(classes_qs):
        result = []
        for c in classes_qs:
            result.append({
                'classe': c,
                'emploi_temps': emplois_existants.get(c.idClasse),
            })
        return result

    context = {
        'annees_scolaires': annees_scolaires,
        'annee_selectionnee': annee_selectionnee,
        'annee_encours': annee_selectionnee.anneeScolaire if annee_selectionnee else None,
        'cycle_filtre': cycle,
        'classes_1er': enrichir(classes_1er),
        'classes_2e': enrichir(classes_2e),
    }
    return render(request, 'ecole/emploi_temps/index.html', context)


@login_required
def emploi_temps_gestion(request, classe_id, annee_scolaire):
    """Affiche la grille d'édition de l'emploi du temps d'une classe."""
    classe = get_object_or_404(Classe, idClasse=classe_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)

    emploi_temps, created = EmploiTemps.objects.get_or_create(
        classe=classe, anneeScolaire=annee
    )

    plages = PlageHoraire.objects.filter(
        cycle=classe.cycle
    ).order_by('ordre', 'heure_debut')

    jours = CreneauEmploiTemps.JOURS

    creneaux_existants = {}
    for c in emploi_temps.creneaux.all():
        creneaux_existants[(c.jour, c.plage_id)] = c

    grille = []
    for plage in plages:
        ligne = {
            'plage': plage,
            'cases': []
        }
        for jour_num, jour_nom in jours:
            creneau = creneaux_existants.get((jour_num, plage.pk))
            ligne['cases'].append({
                'jour': jour_num,
                'jour_nom': jour_nom,
                'creneau': creneau,
            })
        grille.append(ligne)

    # ✅ FIX: Filtrer les matières par classe ET par année
    matieres_classe = MatiereClasse.objects.filter(
        classe=classe,
        annee_scolaire=annee  # ✅ Ajout du filtre par année
    ).select_related('matiere').order_by(
        'ordre_affichage', 'matiere__nomMatiere'
    )

    matieres = [mc.matiere for mc in matieres_classe]

    if not matieres:
        matieres = list(
            Matiere.objects.filter(cycle=classe.cycle).order_by('nomMatiere')
        )

    annee_precedente = _trouver_annee_precedente(annee)
    emploi_precedent = None
    if annee_precedente:
        emploi_precedent = EmploiTemps.objects.filter(
            classe=classe, anneeScolaire=annee_precedente
        ).first()


    context = {
        'classe': classe,
        'annee': annee,
        'annee_scolaire': annee_scolaire,
        'emploi_temps': emploi_temps,
        'plages': plages,
        'jours': jours,
        'grille': grille,
        'matieres': matieres,
        'nb_creneaux_remplis': emploi_temps.nb_creneaux_remplis,
        'emploi_precedent': emploi_precedent,
        'annee_precedente': annee_precedente,
    }
    return render(request, 'ecole/emploi_temps/gestion.html', context)


@login_required
@require_POST
def emploi_temps_enregistrer_creneau(request):
    """Enregistre ou supprime un créneau via AJAX."""
    import json as json_module

    try:
        data = json_module.loads(request.body)
    except (json_module.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'error': 'Données invalides'})

    emploi_temps_id = data.get('emploi_temps_id')
    jour = data.get('jour')
    plage_id = data.get('plage_id')
    matiere_id = data.get('matiere_id')
    salle = (data.get('salle') or '').strip() or None

    if not emploi_temps_id or not jour or not plage_id:
        return JsonResponse({'success': False, 'error': 'Paramètres manquants'})

    try:
        emploi_temps = EmploiTemps.objects.select_related('classe').get(
            id=emploi_temps_id
        )
    except EmploiTemps.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Emploi du temps introuvable'})

    try:
        plage = PlageHoraire.objects.get(idPlage=plage_id)
    except PlageHoraire.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Plage introuvable'})

    if plage.cycle != emploi_temps.classe.cycle:
        return JsonResponse({
            'success': False,
            'error': f"La plage sélectionnée appartient au "
                     f"{plage.get_cycle_display()}, mais l'emploi du temps "
                     f"concerne le {emploi_temps.classe.get_cycle_display()}."
        })

    if plage.est_pause and matiere_id:
        return JsonResponse({
            'success': False,
            'error': "Impossible d'affecter une matière à une pause"
        })

    if not matiere_id:
        CreneauEmploiTemps.objects.filter(
            emploi_temps=emploi_temps, jour=jour, plage=plage
        ).delete()
        return JsonResponse({
            'success': True,
            'action': 'deleted',
            'message': 'Créneau supprimé'
        })

    try:
        matiere = Matiere.objects.get(idMatiere=matiere_id)
    except Matiere.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Matière introuvable'})

    # ✅ FIX: Vérifier que la matière est autorisée pour l'année de l'emploi du temps
    matiere_autorisee = MatiereClasse.objects.filter(
        classe=emploi_temps.classe,
        matiere=matiere,
        annee_scolaire=emploi_temps.anneeScolaire  # ✅ Ajout du filtre par année
    ).exists()

    if not matiere_autorisee:
        classe_a_des_matieres = MatiereClasse.objects.filter(
            classe=emploi_temps.classe,
            annee_scolaire=emploi_temps.anneeScolaire
        ).exists()

        if classe_a_des_matieres:
            return JsonResponse({
                'success': False,
                'error': f"La matière '{matiere.nomMatiere}' n'est pas enseignée "
                         f"dans la classe {emploi_temps.classe.nomClasse} pour cette année."
            })

    if matiere.cycle != emploi_temps.classe.cycle:
        return JsonResponse({
            'success': False,
            'error': f"La matière '{matiere.nomMatiere}' appartient au "
                     f"{matiere.get_cycle_display()}, mais l'emploi du temps "
                     f"concerne le {emploi_temps.classe.get_cycle_display()}."
        })

    creneau, created = CreneauEmploiTemps.objects.update_or_create(
        emploi_temps=emploi_temps, jour=jour, plage=plage,
        defaults={
            'matiere': matiere,
            'salle': salle,
        }
    )

    return JsonResponse({
        'success': True,
        'action': 'created' if created else 'updated',
        'creneau': {
            'id': creneau.id,
            'matiere_nom': matiere.nomMatiere,
            'salle': salle or '',
        },
        'message': 'Créneau enregistré'
    })


@login_required
@require_POST
def emploi_temps_reconduire(request, classe_id, annee_scolaire):
    """Reconduit l'emploi du temps de l'année précédente."""
    import json as json_module

    try:
        data = json_module.loads(request.body)
    except (json_module.JSONDecodeError, TypeError):
        data = {}

    annee_precedente_id = data.get('annee_precedente_id')
    remplacer = data.get('remplacer', False)

    classe = get_object_or_404(Classe, idClasse=classe_id)
    annee_actuelle = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)

    if annee_precedente_id:
        annee_precedente = get_object_or_404(
            AnneeScolaire, idAnneeScolaire=annee_precedente_id
        )
    else:
        annee_precedente = _trouver_annee_precedente(annee_actuelle)

    if not annee_precedente:
        return JsonResponse({
            'success': False,
            'error': "Aucune année scolaire précédente trouvée."
        })

    emploi_source = EmploiTemps.objects.filter(
        classe=classe, anneeScolaire=annee_precedente
    ).first()

    if not emploi_source:
        return JsonResponse({
            'success': False,
            'error': f"Aucun emploi du temps trouvé pour {classe.nomClasse} "
                     f"en {annee_precedente.anneeScolaire}."
        })

    emploi_cible, created = EmploiTemps.objects.get_or_create(
        classe=classe, anneeScolaire=annee_actuelle
    )

    creneaux_existants = emploi_cible.creneaux.count()

    if creneaux_existants > 0 and not remplacer:
        return JsonResponse({
            'success': False,
            'error': f"Cet emploi du temps contient déjà {creneaux_existants} "
                     f"créneau(x). Confirmez pour les remplacer.",
            'requires_confirmation': True,
            'nb_existants': creneaux_existants,
        })

    if remplacer and creneaux_existants > 0:
        emploi_cible.creneaux.all().delete()

    plages_valides = set(
        PlageHoraire.objects.filter(
            cycle=classe.cycle
        ).values_list('idPlage', flat=True)
    )

    creneaux_source = emploi_source.creneaux.all()
    nb_copies = 0
    nb_ignores = 0

    for creneau in creneaux_source:
        if creneau.plage_id not in plages_valides:
            nb_ignores += 1
            continue
        if creneau.matiere and creneau.matiere.cycle != classe.cycle:
            nb_ignores += 1
            continue

        CreneauEmploiTemps.objects.create(
            emploi_temps=emploi_cible,
            jour=creneau.jour,
            plage=creneau.plage,
            matiere=creneau.matiere,
            salle=creneau.salle,
            observation=creneau.observation,
        )
        nb_copies += 1

    emploi_cible.reconduit_depuis = emploi_source
    emploi_cible.save()

    message = f"{nb_copies} créneau(x) copié(s) depuis {annee_precedente.anneeScolaire}."
    if nb_ignores > 0:
        message += f" {nb_ignores} créneau(x) ignoré(s) (cycle incompatible)."

    return JsonResponse({
        'success': True,
        'message': message,
        'nb_copies': nb_copies,
        'nb_ignores': nb_ignores,
    })


@login_required
def emploi_temps_pdf(request, classe_id, annee_scolaire):
    """Export PDF de l'emploi du temps d'une classe."""
    from ..utils.pdf_generator import generer_emploi_temps_pdf

    classe = get_object_or_404(Classe, idClasse=classe_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    ecole = EcoleInfo.get_solo()

    emploi_temps = EmploiTemps.objects.filter(
        classe=classe, anneeScolaire=annee
    ).first()

    if not emploi_temps:
        messages.warning(
            request,
            "Aucun emploi du temps n'a été créé pour cette classe."
        )
        return redirect('fondamental:emploi_temps_gestion',
                        classe_id=classe_id,
                        annee_scolaire=annee_scolaire)

    plages = PlageHoraire.objects.filter(
        cycle=classe.cycle
    ).order_by('ordre', 'heure_debut')
    jours = CreneauEmploiTemps.JOURS

    creneaux_par_case = {}
    for c in emploi_temps.creneaux.all():
        creneaux_par_case[(c.jour, c.plage_id)] = c

    buffer = generer_emploi_temps_pdf(
        classe, annee_scolaire, ecole, plages, jours, creneaux_par_case
    )

    filename = f"emploi_temps_{classe.nomClasse}_{annee_scolaire}.pdf"
    filename = filename.replace(' ', '_')

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def emploi_temps_tous_pdf(request, annee_scolaire):
    """Export PDF de tous les emplois du temps d'une année."""
    from ..utils.pdf_generator import generer_emploi_temps_pdf
    from PyPDF2 import PdfMerger
    import tempfile

    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    ecole = EcoleInfo.get_solo()

    emplois = EmploiTemps.objects.filter(
        anneeScolaire=annee
    ).select_related('classe').order_by('classe__nomClasse')

    if not emplois.exists():
        messages.warning(request, "Aucun emploi du temps pour cette année.")
        return redirect('fondamental:emploi_temps_index')

    merger = PdfMerger()
    temp_files = []
    jours = CreneauEmploiTemps.JOURS

    try:
        for emploi in emplois:
            plages = PlageHoraire.objects.filter(
                cycle=emploi.classe.cycle
            ).order_by('ordre', 'heure_debut')

            creneaux_par_case = {}
            for c in emploi.creneaux.all():
                creneaux_par_case[(c.jour, c.plage_id)] = c

            buffer = generer_emploi_temps_pdf(
                emploi.classe, annee_scolaire, ecole,
                plages, jours, creneaux_par_case
            )

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file.write(buffer.getvalue())
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
            f'attachment; filename="emplois_temps_{annee_scolaire}.pdf"'
        )
        return response

    except Exception as e:
        messages.error(request, f"Erreur : {e}")
        return redirect('fondamental:emploi_temps_index')


