"""Vues : crud."""
from ._deps import *
from ._helpers import *


class AnneeScolaireListView(LoginRequiredMixin, ListView):
    model = AnneeScolaire
    template_name = 'ecole/annee_scolaire/list.html'
    context_object_name = 'annees'

    def get_queryset(self):
        return AnneeScolaire.objects.all().order_by('-anneeScolaire')


class AnneeScolaireCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.add_anneescolaire'
    raise_exception = True
    model = AnneeScolaire
    form_class = AnneeScolaireForm
    template_name = 'ecole/annee_scolaire/form.html'
    success_url = reverse_lazy('fondamental:annee_list')

    def form_valid(self, form):
        messages.success(self.request, "Année scolaire créée avec succès!")
        return super().form_valid(form)


class AnneeScolaireUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.change_anneescolaire'
    raise_exception = True
    model = AnneeScolaire
    form_class = AnneeScolaireForm
    template_name = 'ecole/annee_scolaire/form.html'
    success_url = reverse_lazy('fondamental:annee_list')

    def form_valid(self, form):
        messages.success(self.request, "Année scolaire mise à jour avec succès!")
        return super().form_valid(form)


class AnneeScolaireDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.delete_anneescolaire'
    raise_exception = True
    model = AnneeScolaire
    template_name = 'ecole/annee_scolaire/confirm_delete.html'
    success_url = reverse_lazy('fondamental:annee_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Année scolaire supprimée avec succès!")
        return super().delete(request, *args, **kwargs)


class ClasseListView(LoginRequiredMixin, ListView):
    model = Classe
    template_name = 'ecole/classe/list.html'
    context_object_name = 'classes'

    def get_queryset(self):
        qs = super().get_queryset()
        cycle = self.request.GET.get('cycle')
        if cycle:
            qs = qs.filter(cycle=cycle)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cycle_filtre = self.request.GET.get('cycle')
        annee_filtre = self.request.GET.get('annee')

        # ✅ Si aucune année n'est sélectionnée, on prend la plus récente
        if not annee_filtre:
            annee_actuelle = AnneeScolaire.objects.order_by('-anneeScolaire').first()
            if annee_actuelle:
                annee_filtre = str(annee_actuelle.idAnneeScolaire)

        context['cycle_filtre'] = cycle_filtre
        context['annee_filtre'] = annee_filtre
        context['annees'] = AnneeScolaire.objects.all().order_by('-anneeScolaire')

        # Statistiques par cycle
        context['nb_classes_1er'] = Classe.objects.filter(cycle='1er').count()
        context['nb_classes_2e'] = Classe.objects.filter(cycle='2e').count()
        context['nb_classes_total'] = Classe.objects.count()

        # ✅ Associer les frais ET le nombre d'élèves pour l'année sélectionnée
        if annee_filtre:
            # Trouver le nom de l'année pour l'affichage
            annee_obj = AnneeScolaire.objects.filter(idAnneeScolaire=annee_filtre).first()
            context['annee_selectionnee_nom'] = annee_obj.anneeScolaire if annee_obj else ""

            for classe in context['classes']:
                try:
                    frais = FraisClasseAnnee.objects.get(
                        classe=classe, 
                        annee_scolaire_id=annee_filtre
                    )
                    classe.frais_inscription = frais.frais_inscription
                    classe.frais_scolarite = frais.frais_scolarite
                except FraisClasseAnnee.DoesNotExist:
                    classe.frais_inscription = 0
                    classe.frais_scolarite = 0

                classe.nb_eleves_annee = Inscription.objects.filter(
                    classe=classe,
                    anneeScolaire_id=annee_filtre
                ).count()
        
        return context


class ClasseCreateView(LoginRequiredMixin, RetourAvecCycleMixin, CreateView):
    model = Classe
    form_class = ClasseForm
    template_name = 'ecole/classe/form.html'
    list_url_name = 'classe_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cycle'] = self.get_cycle_filtre()
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Classe créée avec succès!")
        return super().form_valid(form)


class ClasseUpdateView(LoginRequiredMixin, RetourAvecCycleMixin, UpdateView):
    model = Classe
    form_class = ClasseForm
    template_name = 'ecole/classe/form.html'
    list_url_name = 'classe_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cycle'] = self.get_cycle_filtre()
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Classe mise à jour avec succès!")
        return super().form_valid(form)


class ClasseDeleteView(LoginRequiredMixin, RetourAvecCycleMixin, DeleteView):
    model = Classe
    template_name = 'ecole/classe/confirm_delete.html'
    list_url_name = 'classe_list'

    def post(self, request, *args, **kwargs):
        """Surcharge de la suppression pour vérifier s'il y a des élèves."""
        self.object = self.get_object()
        
        # ✅ Vérifier s'il y a des inscriptions (élèves) liées à cette classe
        if self.object.inscription_set.exists():
            messages.error(
                request, 
                f"Impossible de supprimer la classe '{self.object.nomClasse}' car elle contient des élèves inscrits. "
                "Veuillez d'abord supprimer ou transférer ces élèves."
            )
            return redirect('fondamental:classe_list')
            
        return super().post(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Classe supprimée avec succès !")
        return super().delete(request, *args, **kwargs)


class EleveListView(LoginRequiredMixin, ListView):
    model = Eleve
    template_name = 'ecole/eleve/list.html'
    context_object_name = 'eleves'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('search', '')
        if search:
            qs = qs.filter(
                Q(matricule__icontains=search) |
                Q(prenomEleve__icontains=search) |
                Q(nomEleve__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        eleve_ids = [e.id for e in context['eleves']]

        inscriptions = Inscription.objects.filter(
            eleve_id__in=eleve_ids
        ).select_related('classe').order_by(
            'eleve_id', '-anneeScolaire__anneeScolaire'
        )

        vues = set()
        cycles_par_eleve = {}
        for ins in inscriptions:
            if ins.eleve_id in vues:
                continue
            vues.add(ins.eleve_id)
            cycles_par_eleve[ins.eleve_id] = ins.classe.cycle

        for eleve in context['eleves']:
            eleve.cycle_actuel = cycles_par_eleve.get(eleve.id)

        return context


class EleveDetailView(LoginRequiredMixin, DetailView):
    model = Eleve
    template_name = 'ecole/eleve/detail.html'
    context_object_name = 'eleve'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        eleve = self.get_object()
        context['inscriptions'] = Inscription.objects.filter(eleve=eleve)
        context['notes'] = Note.objects.filter(eleve=eleve).select_related('matiere', 'evaluation')
        return context


class EleveCreateView(LoginRequiredMixin, CreateView):
    model = Eleve
    form_class = EleveForm
    template_name = 'ecole/eleve/form.html'
    success_url = reverse_lazy('fondamental:eleve_list')

    def form_valid(self, form):
        messages.success(self.request, "Élève créé avec succès!")
        return super().form_valid(form)


class EleveUpdateView(LoginRequiredMixin, UpdateView):
    model = Eleve
    form_class = EleveForm
    template_name = 'ecole/eleve/form.html'
    success_url = reverse_lazy('fondamental:eleve_list')

    def form_valid(self, form):
        # ✅ Le matricule est figé après création : il ne change plus ici.
        # (Changement volontaire : voir eleve_regenerer_matricule.)
        messages.success(self.request, "Élève mis à jour avec succès!")
        return super().form_valid(form)


@login_required
@require_POST
def eleve_regenerer_matricule(request, pk):
    """
    Change volontairement le matricule d'un élève (directeur uniquement).
    POST « matricule » vide  → recalcul automatique ;
    POST « matricule » rempli → saisie manuelle (doit être unique).
    """
    if not request.user.has_perm('ecole.change_ecoleinfo'):
        messages.error(request, "Action réservée au directeur.")
        return redirect('fondamental:eleve_detail', pk=pk)

    eleve = get_object_or_404(Eleve, pk=pk)
    try:
        ancien, nouveau = eleve.regenerer_matricule(request.POST.get('matricule'))
    except ValueError as e:
        messages.error(request, str(e))
    else:
        if ancien == nouveau:
            messages.info(request, f"Le matricule reste {nouveau}.")
        else:
            logger.warning(
                "Matricule modifié par %s : %s → %s (élève id=%s)",
                request.user.username, ancien, nouveau, eleve.pk,
            )
            messages.warning(
                request,
                f"Matricule modifié : {ancien} → {nouveau}. "
                f"Pensez à réimprimer la carte scolaire de l'élève."
            )
    return redirect('fondamental:eleve_detail', pk=pk)


class EleveDeleteView(LoginRequiredMixin, DeleteView):
    model = Eleve
    template_name = 'ecole/eleve/confirm_delete.html'
    success_url = reverse_lazy('fondamental:eleve_list')


class MatiereListView(LoginRequiredMixin, ListView):
    model = Matiere
    template_name = 'ecole/matiere/list.html'
    context_object_name = 'matieres'

    def get_queryset(self):
        qs = super().get_queryset()
        cycle = self.request.GET.get('cycle')
        if cycle:
            qs = qs.filter(cycle=cycle)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cycle_filtre'] = self.request.GET.get('cycle')
        context['nb_matieres_1er'] = Matiere.objects.filter(cycle='1er').count()
        context['nb_matieres_2e'] = Matiere.objects.filter(cycle='2e').count()
        context['nb_matieres_total'] = Matiere.objects.count()
        return context


class MatiereCreateView(LoginRequiredMixin, RetourAvecCycleMixin, CreateView):
    model = Matiere
    form_class = MatiereForm
    template_name = 'ecole/matiere/form.html'
    list_url_name = 'matiere_list'

    def get_initial(self):
        initial = super().get_initial()
        cycle = self.get_cycle_filtre()
        if cycle:
            initial['cycle'] = cycle
        return initial

    def form_valid(self, form):
        messages.success(self.request, "Matière créée avec succès!")
        return super().form_valid(form)


class MatiereUpdateView(LoginRequiredMixin, RetourAvecCycleMixin, UpdateView):
    model = Matiere
    form_class = MatiereForm
    template_name = 'ecole/matiere/form.html'
    list_url_name = 'matiere_list'

    def form_valid(self, form):
        messages.success(self.request, "Matière mise à jour avec succès!")
        return super().form_valid(form)


class MatiereDeleteView(LoginRequiredMixin, RetourAvecCycleMixin, DeleteView):
    model = Matiere
    template_name = 'ecole/matiere/confirm_delete.html'
    list_url_name = 'matiere_list'


@login_required
def matiere_classe_list(request):
    """Liste des matières par classe avec filtre par année."""
    cycle = request.GET.get('cycle', '')
    classe_id = request.GET.get('classe', '')
    annee_id = request.GET.get('annee', '')

    if not annee_id:
        annee_actuelle = AnneeScolaire.objects.order_by('-anneeScolaire').first()
        if annee_actuelle:
            annee_id = str(annee_actuelle.idAnneeScolaire)

    # ✅ RECHERCHE DE L'ANNÉE PRÉCÉDENTE
    annee_precedente = None
    has_matieres_precedentes = False
    if annee_id:
        annee_obj = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
        if annee_obj:
            annee_precedente_str = f"{annee_obj.get_annee_debut() - 1}-{annee_obj.get_annee_debut()}"
            annee_precedente = AnneeScolaire.objects.filter(anneeScolaire=annee_precedente_str).first()
            
            # ✅ On vérifie s'il y a des matières, mais on garde le bouton visible
            # même si c'est vide, pour que l'utilisateur comprenne qu'il peut copier
            if annee_precedente:
                has_matieres_precedentes = MatiereClasse.objects.filter(
                    annee_scolaire=annee_precedente
                ).exists()

    # ✅ On récupère TOUTES les classes
    classes_qs = Classe.objects.all().order_by('nomClasse')
    if cycle:
        classes_qs = classes_qs.filter(cycle=cycle)
    if classe_id:
        classes_qs = classes_qs.filter(idClasse=classe_id)

    # ✅ Liste de dictionnaires
    liste_classes = []
    for classe in classes_qs:
        matieres = []
        if annee_id:
            matieres = list(MatiereClasse.objects.filter(
                classe=classe,
                annee_scolaire_id=annee_id
            ).select_related('matiere').order_by('ordre_affichage', 'matiere__nomMatiere'))
        
        liste_classes.append({
            'classe': classe,
            'matieres': matieres,
            'nb_matieres': len(matieres),
        })

    # Statistiques
    matieres_classe_all = MatiereClasse.objects.filter(annee_scolaire_id=annee_id) if annee_id else MatiereClasse.objects.none()
    nb_total = matieres_classe_all.count()
    nb_1er = matieres_classe_all.filter(classe__cycle='1er').count()
    nb_2e = matieres_classe_all.filter(classe__cycle='2e').count()

    annee_selectionnee_nom = ""
    if annee_id:
        annee_obj = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
        if annee_obj:
            annee_selectionnee_nom = annee_obj.anneeScolaire

    context = {
        'liste_classes': liste_classes,
        'classes': classes_qs,
        'classe_id': classe_id,
        'cycle_filtre': cycle,
        'annee_filtre': annee_id,
        'annee_selectionnee_nom': annee_selectionnee_nom,
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'total': nb_total,
        'nb_1er': nb_1er,
        'nb_2e': nb_2e,
        'nb_total': nb_total,
        'annee_precedente': annee_precedente,
        'has_matieres_precedentes': has_matieres_precedentes,
    }
    return render(request, 'ecole/matiere_classe/list.html', context)


class MatiereClasseCreateView(LoginRequiredMixin, RetourAvecCycleMixin, CreateView):
    model = MatiereClasse
    form_class = MatiereClasseForm
    template_name = 'ecole/matiere_classe/form.html'
    list_url_name = 'fondamental:matiere_classe_list'  # ✅ Ajout de fondamental:

    def get_initial(self):
        initial = super().get_initial()
        cycle = self.get_cycle_filtre()
        annee = self.request.GET.get('annee')  # ✅ Récupérer l'année de l'URL
        
        if cycle:
            initial['cycle'] = cycle
        if annee:
            initial['annee_scolaire'] = annee  # ✅ Pré-remplir l'année
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cycle'] = self.get_cycle_filtre()
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Matière associée à la classe avec succès!")
        return super().form_valid(form)


class MatiereClasseUpdateView(LoginRequiredMixin, UpdateView):
    model = MatiereClasse
    form_class = MatiereClasseForm
    template_name = 'ecole/matiere_classe/form.html'
    success_url = reverse_lazy('fondamental:matiere_classe_list')  # ✅ Ajout de fondamental:

    def form_valid(self, form):
        messages.success(self.request, "Association mise à jour avec succès!")
        return super().form_valid(form)


class MatiereClasseDeleteView(LoginRequiredMixin, DeleteView):
    model = MatiereClasse
    template_name = 'ecole/matiere_classe/confirm_delete.html'
    success_url = reverse_lazy('fondamental:matiere_classe_list')  # ✅ Ajout de fondamental:

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Association supprimée avec succès!")
        return super().delete(request, *args, **kwargs)


class InscriptionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = 'ecole.view_inscription'
    raise_exception = True
    model = Inscription
    template_name = 'ecole/inscription/list.html'
    context_object_name = 'inscriptions'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('eleve', 'classe', 'anneeScolaire')
        annee = self.request.GET.get('annee', '')
        classe = self.request.GET.get('classe', '')
        cycle = self.request.GET.get('cycle', '')

        if annee:
            qs = qs.filter(anneeScolaire__idAnneeScolaire=annee)
        if classe:
            qs = qs.filter(classe__idClasse=classe)
        if cycle:
            qs = qs.filter(classe__cycle=cycle)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cycle = self.request.GET.get('cycle', '')
        context['annees'] = AnneeScolaire.objects.all()
        context['classes'] = Classe.objects.all()
        if cycle:
            context['classes'] = context['classes'].filter(cycle=cycle)
        context['cycle_filtre'] = cycle
        return context


class InscriptionCreateView(LoginRequiredMixin, PermissionRequiredMixin,
                             RetourAvecCycleMixin, CreateView):
    permission_required = 'ecole.add_inscription'
    raise_exception = True
    model = Inscription
    form_class = InscriptionForm
    template_name = 'ecole/inscription/form.html'
    list_url_name = 'inscription_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cycle'] = self.get_cycle_filtre()
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Inscription créée avec succès!")
        return super().form_valid(form)


class InscriptionUpdateView(LoginRequiredMixin, PermissionRequiredMixin,
                             RetourAvecCycleMixin, UpdateView):
    permission_required = 'ecole.change_inscription'
    raise_exception = True
    model = Inscription
    form_class = InscriptionForm
    template_name = 'ecole/inscription/form.html'
    list_url_name = 'inscription_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cycle'] = self.get_cycle_filtre()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        inscription = self.get_object()
        eleve = inscription.eleve
        context['eleve_selected'] = {
            'id': eleve.id,
            'matricule': eleve.matricule,
            'nom': eleve.nomEleve,
            'prenom': eleve.prenomEleve,
            'date_naiss': eleve.dateNaiss.strftime('%d/%m/%Y') if eleve.dateNaiss else '',
            'lieu_naiss': eleve.lieuNaiss,
        }
        return context


class InscriptionDeleteView(LoginRequiredMixin, PermissionRequiredMixin,
                             RetourAvecCycleMixin, DeleteView):
    permission_required = 'ecole.delete_inscription'
    raise_exception = True
    model = Inscription
    template_name = 'ecole/inscription/confirm_delete.html'
    list_url_name = 'inscription_list'


@login_required
@permission_required('ecole.view_paiement_global', raise_exception=True)
def PaiementListView(request):
    paiements = Paiement.objects.select_related(
        'inscription__eleve', 'inscription__classe'
    ).all()

    annee = request.GET.get('annee')
    mois = request.GET.get('mois')
    classe = request.GET.get('classe')
    cycle = request.GET.get('cycle')

    if annee:
        paiements = paiements.filter(inscription__anneeScolaire__anneeScolaire=annee)
    if mois:
        paiements = paiements.filter(mois=mois)
    if classe:
        paiements = paiements.filter(inscription__classe_id=classe)
    if cycle:
        paiements = paiements.filter(inscription__classe__cycle=cycle)

    paginator = Paginator(paiements, 20)
    paiements_page = paginator.get_page(request.GET.get('page'))
    total_general = paiements.aggregate(Sum('montant'))['montant__sum'] or 0

    annee_encours = AnneeScolaire.objects.order_by('-anneeScolaire').first()
    annee_encours_str = annee_encours.anneeScolaire if annee_encours else "2025-2026"

    classes = Classe.objects.all().order_by('nomClasse')
    if cycle:
        classes = classes.filter(cycle=cycle)

    context = {
        'paiements': paiements_page,
        'total_general': total_general,
        'annees_scolaires': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'mois_choices': Paiement.MOIS_SCOLAIRES_ORDONNES,
        'classes': classes,
        'annee_encours': annee_encours_str,
        'is_paginated': True,
        'page_obj': paiements_page,
        'cycle_filtre': cycle,
    }
    return render(request, 'ecole/paiement/list.html', context)


class PaiementCreateView(LoginRequiredMixin, PermissionRequiredMixin,
                         RetourAvecCycleMixin, CreateView):
    permission_required = 'ecole.add_paiement'
    raise_exception = True
    model = Paiement
    form_class = PaiementForm
    template_name = 'ecole/paiement/form.html'
    list_url_name = 'paiement_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cycle'] = self.get_cycle_filtre()
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        inscription_id = self.request.GET.get('inscription')
        mois = self.request.GET.get('mois')
        annee = self.request.GET.get('annee')
        est_inscription = self.request.GET.get('est_inscription')

        if inscription_id:
            try:
                inscription = Inscription.objects.select_related('eleve', 'classe', 'anneeScolaire').get(idInscription=inscription_id)
                initial['inscription'] = inscription
                initial['recherche_inscription'] = (
                    f"{inscription.eleve.matricule} - "
                    f"{inscription.eleve.nomEleve} {inscription.eleve.prenomEleve} "
                    f"({inscription.classe.nomClasse})"
                )
                initial['annee_scolaire_filter'] = inscription.anneeScolaire

                ecole = EcoleInfo.get_solo()

                if est_inscription:
                    initial['montant'] = inscription.frais_inscription_attendu

                elif mois:
                    echeances = calculer_echeances(ecole, inscription.classe, inscription.anneeScolaire)
                    try:
                        mois_int = int(mois)
                        for ech in echeances:
                            if ech.get('mois') == mois_int:
                                initial['montant'] = ech['montant']
                                break
                    except (ValueError, TypeError):
                        pass

            except Inscription.DoesNotExist:
                pass

        # Pré-remplir le mois et l'année
        if mois:
            try:
                initial['mois'] = int(mois)
            except (ValueError, TypeError):
                pass

        if annee:
            try:
                initial['annee_paiement'] = int(annee)
            except (ValueError, TypeError):
                pass

        if est_inscription in ('on', 'true', '1', 'True'):
            initial['est_inscription'] = True

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        inscription_id = self.request.GET.get('inscription')
        est_inscription = self.request.GET.get('est_inscription')

        context['prefill_est_inscription'] = (
            est_inscription in ('on', 'true', '1', 'True')
        )
        context['prefill_inscription_id'] = inscription_id or ''

        if inscription_id:
            try:
                inscription = Inscription.objects.select_related(
                    'eleve', 'classe'
                ).get(idInscription=inscription_id)
                context['prefill_inscription'] = inscription
            except Inscription.DoesNotExist:
                pass

        return context

    def get_success_url(self):
        inscription = self.object.inscription
        return reverse('fondamental:paiement_eleve_annee', kwargs={
            'eleve_id': inscription.eleve_id,
            'annee_scolaire': inscription.anneeScolaire.anneeScolaire
        })

    def form_valid(self, form):
        messages.success(self.request, "Paiement enregistré avec succès!")
        return super().form_valid(form)

    def get(self, request, *args, **kwargs):
        """
        ✅ FIX : Sécurité — si on tente de créer un paiement pour une échéance
        déjà complètement payée, on redirige avec un message d'avertissement.
        Utilise le SERVICE pour calculer les montants attendus (selon le mode).
        """
        inscription_id = request.GET.get('inscription')
        mois = request.GET.get('mois')
        est_inscription = request.GET.get('est_inscription')

        if inscription_id:
            try:
                inscription = Inscription.objects.get(idInscription=inscription_id)
                ecole = EcoleInfo.get_solo()

                montants = calculer_montants_inscription(inscription)

                # Vérifier si les frais d'inscription sont déjà complets
                if est_inscription in ('on', 'true', '1', 'True'):
                    if montants['frais_inscription_attendu'] > 0 and \
                       montants['frais_inscription_paye'] >= montants['frais_inscription_attendu']:
                        messages.warning(
                            request,
                            f"Les frais d'inscription sont déjà complètement payés "
                            f"({montants['frais_inscription_paye']:,.0f} FCFA). "
                            f"Vous pouvez modifier les paiements existants."
                        )
                        return redirect('fondamental:paiement_eleve_annee', kwargs={
                            'eleve_id': inscription.eleve_id,
                            'annee_scolaire': inscription.anneeScolaire.anneeScolaire
                        })

                # Vérifier si l'échéance mensuelle est déjà complète (mode mensuel)
                if mois and not est_inscription:
                    try:
                        mois_int = int(mois)
                        for ech in montants['detail_echeances']:
                            if ech.get('mois') == mois_int:
                                if ech['paye'] >= ech['attendu'] and not ech['deja_paye']:
                                    messages.warning(
                                        request,
                                        f"L'échéance {ech['libelle']} est déjà "
                                        f"complètement payée "
                                        f"({ech['paye']:,.0f} FCFA). "
                                        f"Vous pouvez modifier les paiements existants."
                                    )
                                    return redirect('fondamental:paiement_eleve_annee', kwargs={
                                        'eleve_id': inscription.eleve_id,
                                        'annee_scolaire': inscription.anneeScolaire.anneeScolaire
                                    })
                                break
                    except (ValueError, TypeError):
                        pass

            except Inscription.DoesNotExist:
                pass

        return super().get(request, *args, **kwargs)


class PaiementUpdateView(LoginRequiredMixin, PermissionRequiredMixin,
                         RetourAvecCycleMixin, UpdateView):
    permission_required = 'ecole.change_paiement'
    raise_exception = True
    model = Paiement
    form_class = PaiementForm
    template_name = 'ecole/paiement/form.html'
    list_url_name = 'paiement_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cycle'] = self.get_cycle_filtre()
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Paiement mis à jour avec succès!")
        return super().form_valid(form)


class PaiementDeleteView(LoginRequiredMixin, PermissionRequiredMixin,
                         RetourAvecCycleMixin, DeleteView):
    permission_required = 'ecole.delete_paiement'
    raise_exception = True
    model = Paiement
    template_name = 'ecole/paiement/confirm_delete.html'
    list_url_name = 'paiement_list'


class EvaluationListView(LoginRequiredMixin, ListView):
    model = Evaluation
    template_name = 'ecole/evaluation/list.html'
    context_object_name = 'evaluations'


class EvaluationCreateView(LoginRequiredMixin, CreateView):
    model = Evaluation
    form_class = EvaluationForm
    template_name = 'ecole/evaluation/form.html'
    success_url = reverse_lazy('fondamental:evaluation_list')


class EvaluationUpdateView(LoginRequiredMixin, UpdateView):
    model = Evaluation
    form_class = EvaluationForm
    template_name = 'ecole/evaluation/form.html'
    success_url = reverse_lazy('fondamental:evaluation_list')


class EvaluationDeleteView(LoginRequiredMixin, DeleteView):
    model = Evaluation
    template_name = 'ecole/evaluation/confirm_delete.html'
    success_url = reverse_lazy('fondamental:evaluation_list')


class NoteListView(LoginRequiredMixin, ListView):
    model = Note
    template_name = 'ecole/cycle2/notes/list.html'
    context_object_name = 'notes'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            'eleve', 'matiere', 'evaluation', 'anneeScolaire'
        )
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(eleve__nomEleve__icontains=search) |
                Q(eleve__prenomEleve__icontains=search) |
                Q(eleve__matricule__icontains=search)
            )
        classe = self.request.GET.get('classe', '')
        if classe:
            qs = qs.filter(eleve__inscription__classe__idClasse=classe)
        matiere = self.request.GET.get('matiere', '')
        if matiere:
            qs = qs.filter(matiere__idMatiere=matiere)
        annee = self.request.GET.get('annee', '')
        if annee:
            qs = qs.filter(anneeScolaire__idAnneeScolaire=annee)
        trimestre = self.request.GET.get('trimestre', '')
        if trimestre:
            qs = qs.filter(evaluation__nomEvaluation=trimestre)
        return qs.order_by(
            '-anneeScolaire__anneeScolaire', 'eleve__nomEleve', 'matiere__nomMatiere'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        eleve_ids = [n.eleve_id for n in context['notes']]
        annee_ids = [n.anneeScolaire_id for n in context['notes']]

        inscriptions_map = {}
        if eleve_ids and annee_ids:
            inscriptions = Inscription.objects.filter(
                eleve_id__in=eleve_ids,
                anneeScolaire_id__in=annee_ids,
            ).select_related('classe')
            for ins in inscriptions:
                inscriptions_map[(ins.eleve_id, ins.anneeScolaire_id)] = ins

        for note in context['notes']:
            key = (note.eleve_id, note.anneeScolaire_id)
            note.inscription_courante = inscriptions_map.get(key)

        classe_id = self.request.GET.get('classe', '')
        matieres_affichees = []
        classe_sans_matieres = False

        if classe_id:
            try:
                classe_selectionnee = Classe.objects.get(idClasse=classe_id)
                matieres_affichees = _matieres_classe_annee(
                    classe_selectionnee, self.request.GET.get('annee')
                )

                if not matieres_affichees:
                    classe_sans_matieres = True

            except Classe.DoesNotExist:
                pass
        else:
            matieres_affichees = list(Matiere.objects.filter(cycle='2e').order_by('nomMatiere'))

        context['classes'] = classes_du_cycle(Cycle.SECOND.value)
        context['matieres'] = matieres_affichees
        context['classe_sans_matieres'] = classe_sans_matieres
        context['annees_scolaires'] = AnneeScolaire.objects.all().order_by('-anneeScolaire')
        context['trimestres'] = dict(Evaluation.TRIMESTRE)
        context['search'] = self.request.GET.get('search', '')
        context['classe_filter'] = self.request.GET.get('classe', '')
        context['matiere_filter'] = self.request.GET.get('matiere', '')
        context['annee_filter'] = self.request.GET.get('annee', '')
        context['trimestre_filter'] = self.request.GET.get('trimestre', '')
        return context


class NoteCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.add_note'
    raise_exception = True
    model = Note
    form_class = NoteForm
    template_name = 'ecole/note/form.html'
    success_url = reverse_lazy('fondamental:note_list')

    def form_valid(self, form):
        messages.success(self.request, "Note enregistrée avec succès!")
        return super().form_valid(form)


class NoteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.change_note'
    raise_exception = True
    model = Note
    form_class = NoteForm
    template_name = 'ecole/note/form.html'
    success_url = reverse_lazy('fondamental:note_list')

    def form_valid(self, form):
        messages.success(self.request, "Note mise à jour avec succès!")
        return super().form_valid(form)


class NoteDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.delete_note'
    raise_exception = True
    model = Note
    template_name = 'ecole/note/confirm_delete.html'
    success_url = reverse_lazy('fondamental:note_list')


@login_required
@permission_required('ecole.delete_notemensuelle', raise_exception=True)
@require_POST
def cycle1_supprimer_note(request, pk):
    """Supprime une note mensuelle (1er cycle) et redirige vers la liste."""
    from ..models import NoteMensuelle
    
    note = get_object_or_404(NoteMensuelle, pk=pk)
    eleve = note.eleve
    matiere = note.matiere
    
    note.delete()
    messages.success(request, f"La note de {eleve.nomEleve} en {matiere.nomMatiere} a été supprimée.")
    
    # On redirige vers la liste en conservant les filtres actuels si possible
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('fondamental:cycle1_notes_list')


