"""Vues : comptabilite."""
from ._deps import *
from ._helpers import *
from ..models import Section


@login_required
@permission_required('ecole.voir_comptabilite', raise_exception=True)
def depense_list(request):
    """Liste des dépenses avec filtres."""
    depenses = Depense.objects.select_related(
        'categorie', 'anneeScolaire', 'saisi_par'
    ).all()

    categorie_id = request.GET.get('categorie', '')
    annee_id = request.GET.get('annee', '')
    mois = request.GET.get('mois', '')
    section = request.GET.get('section', '')
    search = request.GET.get('search', '').strip()

    if categorie_id:
        depenses = depenses.filter(categorie_id=categorie_id)
    if annee_id:
        depenses = depenses.filter(anneeScolaire_id=annee_id)
    if section:
        depenses = depenses.filter(section=section)
    if mois:
        depenses = depenses.filter(date_depense__month=mois)
    if search:
        depenses = depenses.filter(
            Q(libelle__icontains=search) |
            Q(beneficiaire__icontains=search) |
            Q(numero_piece__icontains=search)
        )

    total = depenses.aggregate(Sum('montant'))['montant__sum'] or 0

    paginator = Paginator(depenses, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'depenses': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'total': total,
        'nb_depenses': depenses.count(),
        'categories': CategorieDepense.objects.filter(active=True).order_by('ordre_affichage', 'nom'),
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'mois_choices': MOIS_CALENDAIRES,
        'sections_choix': [(c, Section(c).label) for c in __import__('ecole.services.comptabilite', fromlist=['sections_disponibles']).sections_disponibles()],
        'section': section,
        'categorie_id': categorie_id,
        'annee_id': annee_id,
        'mois_filter': mois,
        'search': search,
    }
    return render(request, 'ecole/comptabilite/depense/list.html', context)


class DepenseCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.gerer_depenses'
    raise_exception = True
    model = Depense
    form_class = DepenseForm
    template_name = 'ecole/comptabilite/depense/form.html'
    success_url = reverse_lazy('fondamental:depense_list')

    def form_valid(self, form):
        form.instance.saisi_par = self.request.user
        messages.success(self.request, "Dépense enregistrée avec succès!")
        return super().form_valid(form)


class DepenseUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.gerer_depenses'
    raise_exception = True
    model = Depense
    form_class = DepenseForm
    template_name = 'ecole/comptabilite/depense/form.html'
    success_url = reverse_lazy('fondamental:depense_list')

    def form_valid(self, form):
        messages.success(self.request, "Dépense mise à jour avec succès!")
        return super().form_valid(form)


class DepenseDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.gerer_depenses'
    raise_exception = True
    model = Depense
    template_name = 'ecole/comptabilite/depense/confirm_delete.html'
    success_url = reverse_lazy('fondamental:depense_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Dépense supprimée avec succès!")
        return super().delete(request, *args, **kwargs)


@login_required
@permission_required('ecole.voir_comptabilite', raise_exception=True)
def comptabilite_dashboard(request):
    """
    Tableau de bord comptable — vue unifiée 1er / 2e / lycée / global.

    Tous les montants proviennent de `services/comptabilite.py` : la vue
    ne fait que présenter. L'invariant `global == 1er + 2e + lycée + commun`
    est garanti par le service (et couvert par un test).
    """
    from ..models import Section
    from ..services.comptabilite import (
        SECTIONS, detail_financier, etat_comptable, evolution_mensuelle,
        section_valide,
    )

    annee_id = request.GET.get('annee')
    section_code = section_valide(request.GET.get('section'))

    annees_scolaires = AnneeScolaire.objects.all().order_by('-anneeScolaire')
    if annee_id:
        annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
    else:
        annee_selectionnee = annees_scolaires.first()

    etat = etat_comptable(annee_selectionnee)
    detail = detail_financier(annee_selectionnee, section_code)
    evolution = evolution_mensuelle(annee_selectionnee, section_code)

    context = {
        'annees_scolaires': annees_scolaires,
        'annee_selectionnee': annee_selectionnee,
        'annee_encours': annee_selectionnee.anneeScolaire if annee_selectionnee else None,

        # --- sélecteur de section ---
        'section_active': section_code or 'global',
        'section_courante_label': 'Global' if not section_code else Section(section_code).label,
        'sections': etat['sections'],
        'global': etat['global'],
        'sections_choix': [
            {'code': 'global', 'label': 'Global', 'actif': section_code is None},
        ] + [
            {'code': c, 'label': Section(c).label, 'actif': section_code == c}
            for c in SECTIONS
        ],

        # --- chiffres détaillés (clés conservées pour le template) ---
        'recettes_frais': detail['recettes_frais'],
        'recettes_scolarite': detail['recettes_scolarite'],
        'recettes_autres': detail['recettes_autres'],
        'nb_recettes_autres': detail['nb_recettes_autres'],
        'recettes_par_categorie': detail['recettes_par_categorie'],
        'total_recettes': detail['total_recettes'],
        'nb_paiements': detail['nb_paiements'],

        'total_depenses': detail['total_depenses'],
        'nb_depenses': detail['nb_depenses'],
        'depenses_par_categorie': detail['depenses_par_categorie'],

        'resultat': detail['resultat'],
        'resultat_positif': detail['resultat'] >= 0,

        'evolution_mensuelle': evolution,
        'evolution_mensuelle_json': json.dumps(evolution),
        'depenses_categorie_json': json.dumps([
            {'label': d['categorie__nom'], 'value': float(d['total'])}
            for d in detail['depenses_par_categorie']
        ]),
        'recettes_categorie_json': json.dumps([
            {'label': r['categorie__nom'], 'value': float(r['total'])}
            for r in detail['recettes_par_categorie']
        ]),

        'dernieres_depenses': detail['dernieres_depenses'],
    }
    return render(request, 'ecole/comptabilite/dashboard.html', context)


@login_required
@permission_required('ecole.voir_comptabilite', raise_exception=True)
def recette_list(request):
    """Liste des recettes hors paiements."""
    recettes = Recette.objects.select_related(
        'categorie', 'anneeScolaire', 'saisi_par'
    ).all()

    categorie_id = request.GET.get('categorie', '')
    annee_id = request.GET.get('annee', '')
    mois = request.GET.get('mois', '')
    section = request.GET.get('section', '')
    search = request.GET.get('search', '').strip()

    if categorie_id:
        recettes = recettes.filter(categorie_id=categorie_id)
    if annee_id:
        recettes = recettes.filter(anneeScolaire_id=annee_id)
    if section:
        recettes = recettes.filter(section=section)
    if mois:
        recettes = recettes.filter(date_recette__month=mois)
    if search:
        recettes = recettes.filter(
            Q(libelle__icontains=search) |
            Q(source__icontains=search) |
            Q(numero_piece__icontains=search)
        )

    total = recettes.aggregate(Sum('montant'))['montant__sum'] or 0
    paginator = Paginator(recettes, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'recettes': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'total': total,
        'nb_recettes': recettes.count(),
        'categories': CategorieRecette.objects.filter(active=True).order_by('ordre_affichage', 'nom'),
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'mois_choices': MOIS_CALENDAIRES,
        'sections_choix': [(c, Section(c).label) for c in __import__('ecole.services.comptabilite', fromlist=['sections_disponibles']).sections_disponibles()],
        'section': section,
        'categorie_id': categorie_id,
        'annee_id': annee_id,
        'mois_filter': mois,
        'search': search,
    }
    return render(request, 'ecole/comptabilite/recette/list.html', context)


class RecetteCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.gerer_recettes'
    raise_exception = True
    model = Recette
    form_class = RecetteForm
    template_name = 'ecole/comptabilite/recette/form.html'
    success_url = reverse_lazy('fondamental:recette_list')

    def form_valid(self, form):
        form.instance.saisi_par = self.request.user
        messages.success(self.request, "Recette enregistrée avec succès!")
        return super().form_valid(form)


class RecetteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.gerer_recettes'
    raise_exception = True
    model = Recette
    form_class = RecetteForm
    template_name = 'ecole/comptabilite/recette/form.html'
    success_url = reverse_lazy('fondamental:recette_list')

    def form_valid(self, form):
        messages.success(self.request, "Recette mise à jour avec succès!")
        return super().form_valid(form)


class RecetteDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.gerer_recettes'
    raise_exception = True
    model = Recette
    template_name = 'ecole/comptabilite/recette/confirm_delete.html'
    success_url = reverse_lazy('fondamental:recette_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Recette supprimée avec succès!")
        return super().delete(request, *args, **kwargs)


@login_required
@permission_required('ecole.voir_comptabilite', raise_exception=True)
def rapports_comptables(request):
    """
    Rapports comptables.

    ✅ Filtre par date_paiement + liste des mois de l'année scolaire.
    ✅ Filtre par section (1er / 2e / lycee / global).
    """
    from ..utils.dates import get_mois_annee_scolaire, get_annee_reelle_mois

    annee_id = request.GET.get('annee')
    mois = request.GET.get('mois')  # mois calendaire 1-12
    section = request.GET.get('section', '')  # ✅ nouveau

    annees_scolaires = AnneeScolaire.objects.all().order_by('-anneeScolaire')
    if annee_id:
        annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
    else:
        annee_selectionnee = annees_scolaires.first()

    # Filtre section
    if section:
        depenses_qs = Depense.objects.filter(
            anneeScolaire=annee_selectionnee, section=section)
        recettes_qs = Recette.objects.filter(
            anneeScolaire=annee_selectionnee, section=section)
        # Paiements : section dérivée de inscription.classe.cycle
        # On filtre par section uniquement si ce n'est pas 'global'
        if section != 'global':
            paiements_qs = Paiement.objects.filter(
                inscription__anneeScolaire=annee_selectionnee,
                inscription__classe__cycle=section,
            )
        else:
            paiements_qs = Paiement.objects.filter(
                inscription__anneeScolaire=annee_selectionnee,
            )
    else:
        depenses_qs = Depense.objects.filter(anneeScolaire=annee_selectionnee)
        recettes_qs = Recette.objects.filter(anneeScolaire=annee_selectionnee)
        paiements_qs = Paiement.objects.filter(
            inscription__anneeScolaire=annee_selectionnee
        )

    # ... reste inchangé (mois, calculs, context) ...
    # Pour garder la brièveté, je réutilise la structure existante.
    # Les filtres 'section' ont été appliqués ci-dessus.

    # ================================================================
    # Parse du mois sélectionné
    # ================================================================
    mois_scolaires_liste = []
    if annee_selectionnee:
        mois_scolaires_liste = get_mois_annee_scolaire(annee_selectionnee)

    mois_int = None
    annee_reelle_mois = None
    mois_label = None

    if mois and annee_selectionnee:
        try:
            mois_int = int(mois)
            if mois_int in range(1, 13):
                annee_reelle_mois = get_annee_reelle_mois(mois_int, annee_selectionnee)
                # Trouver le label
                for num, nom, an, label in get_mois_annee_scolaire(annee_selectionnee):
                    if num == mois_int:
                        mois_label = label
                        break
            else:
                mois_int = None
        except (ValueError, TypeError):
            mois_int = None

    # ================================================================
    # Filtres de base
    # ================================================================
    # Les filtres section ont été appliqués plus haut.
    # On applique maintenant le filtre mensuel.

    # Filtre mensuel
    if mois_int and annee_reelle_mois:
        # Dépenses : par date_depense
        depenses_qs = depenses_qs.filter(
            date_depense__month=mois_int,
            date_depense__year=annee_reelle_mois,
        )
        # Recettes : par date_recette
        recettes_qs = recettes_qs.filter(
            date_recette__month=mois_int,
            date_recette__year=annee_reelle_mois,
        )
        # Paiements : ✅ par date_paiement (au lieu de mois)
        paiements_qs = paiements_qs.filter(
            date_paiement__month=mois_int,
            date_paiement__year=annee_reelle_mois,
        )

    # ================================================================
    # CALCULS
    # ================================================================
    recettes_frais = paiements_qs.filter(est_inscription=True).aggregate(
        Sum('montant'))['montant__sum'] or 0
    recettes_scolarite = paiements_qs.filter(est_inscription=False).aggregate(
        Sum('montant'))['montant__sum'] or 0
    recettes_autres = recettes_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    total_recettes = recettes_frais + recettes_scolarite + recettes_autres

    total_depenses = depenses_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    resultat = total_recettes - total_depenses

    # Détail dépenses par catégorie
    depenses_par_categorie = list(
        depenses_qs.values('categorie__nom')
        .annotate(total=Sum('montant'), nb=Count('id'))
        .order_by('-total')
    )
    for item in depenses_par_categorie:
        item['pourcentage'] = round(
            float(item['total']) / float(total_depenses) * 100, 1
        ) if total_depenses > 0 else 0

    # Détail recettes par catégorie
    recettes_par_categorie = list(
        recettes_qs.values('categorie__nom')
        .annotate(total=Sum('montant'), nb=Count('id'))
        .order_by('-total')
    )

    # ================================================================
    # DÉTAIL DES PAIEMENTS (avec info mois scolaire)
    # ================================================================
    paiements_detail = []
    for p in paiements_qs.select_related(
        'inscription__eleve', 'inscription__classe'
    ).order_by('-date_paiement')[:100]:
        # Info mois scolaire (si mode mensuel)
        mois_scolaire_info = None
        if p.mois:
            mois_scolaire_info = p.get_mois_display()

        paiements_detail.append({
            'date': p.date_paiement,
            'eleve': str(p.inscription.eleve),
            'classe': p.inscription.classe.nomClasse,
            'montant': p.montant,
            'est_inscription': p.est_inscription,
            'mois_scolaire': mois_scolaire_info,   # ✅ Info mois scolaire
            'annee_paiement': p.annee_paiement,
            'observation': p.observation,
        })

    # ================================================================
    # RÉPARTITION MENSUELLE (12 mois de l'année scolaire)
    # ✅ Filtre par date_paiement + date_depense + date_recette
    # ================================================================
    repartition_mensuelle = []

    if annee_selectionnee:
        for num_mois, nom_mois, annee_reelle, label in mois_scolaires_liste:
            # Paiements
            pai_mois = Paiement.objects.filter(
                inscription__anneeScolaire=annee_selectionnee,
                date_paiement__month=num_mois,
                date_paiement__year=annee_reelle,
            ).aggregate(Sum('montant'))['montant__sum'] or 0

            # Autres recettes
            rec_mois = Recette.objects.filter(
                anneeScolaire=annee_selectionnee,
                date_recette__month=num_mois,
                date_recette__year=annee_reelle,
            ).aggregate(Sum('montant'))['montant__sum'] or 0

            # Dépenses
            dep_mois = Depense.objects.filter(
                anneeScolaire=annee_selectionnee,
                date_depense__month=num_mois,
                date_depense__year=annee_reelle,
            ).aggregate(Sum('montant'))['montant__sum'] or 0

            recettes_total_mois = float(pai_mois + rec_mois)
            depenses_total_mois = float(dep_mois)
            solde_mois = recettes_total_mois - depenses_total_mois

            repartition_mensuelle.append({
                'mois': num_mois,
                'nom': nom_mois,
                'annee': annee_reelle,
                'label': label,
                'recettes_paiements': float(pai_mois),
                'recettes_autres': float(rec_mois),
                'recettes': recettes_total_mois,
                'depenses': depenses_total_mois,
                'solde': solde_mois,
            })

    context = {
        'annees_scolaires': annees_scolaires,
        'annee_selectionnee': annee_selectionnee,
        'annee_encours': annee_selectionnee.anneeScolaire if annee_selectionnee else None,

        # ✅ Sélecteur de section
        'section_active': section or 'global',
        'sections_choix': [(c, Section(c).label) for c in __import__('ecole.services.comptabilite', fromlist=['sections_disponibles']).sections_disponibles()],

        # ✅ Mois de l'année scolaire (avec année explicite)
        'mois_scolaires_liste': mois_scolaires_liste,
        'mois_selectionne': mois_int,
        'mois_label': mois_label,

        'recettes_frais': recettes_frais,
        'recettes_scolarite': recettes_scolarite,   # ✅ renommé
        'recettes_autres': recettes_autres,
        'total_recettes': total_recettes,

        'total_depenses': total_depenses,
        'depenses_par_categorie': depenses_par_categorie,
        'recettes_par_categorie': recettes_par_categorie,

        'resultat': resultat,
        'resultat_positif': resultat >= 0,

        # ✅ Détail des paiements (avec mois scolaire)
        'paiements_detail': paiements_detail,

        'repartition_mensuelle': repartition_mensuelle,
        'repartition_mensuelle_json': json.dumps(repartition_mensuelle),
    }
    return render(request, 'ecole/comptabilite/rapports.html', context)


@login_required
@permission_required('ecole.voir_comptabilite', raise_exception=True)
def rapport_pdf(request):
    """Génère un rapport PDF de la comptabilité."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    from ..utils.dates import get_mois_annee_scolaire, get_annee_reelle_mois

    annee_id = request.GET.get('annee')
    mois = request.GET.get('mois')
    section = request.GET.get('section', '')  # ✅ nouveau filtre

    if annee_id:
        annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
    else:
        annee_selectionnee = AnneeScolaire.objects.first()

    if not annee_selectionnee:
        messages.error(request, "Aucune année scolaire disponible.")
        return redirect('fondamental:rapports_comptables')

    # ================================================================
    # Parse du mois
    # ================================================================
    mois_int = None
    annee_reelle_mois = None
    mois_label = None

    if mois:
        try:
            mois_int = int(mois)
            if mois_int in range(1, 13):
                annee_reelle_mois = get_annee_reelle_mois(mois_int, annee_selectionnee)
                for num, nom, an, label in get_mois_annee_scolaire(annee_selectionnee):
                    if num == mois_int:
                        mois_label = label
                        break
            else:
                mois_int = None
        except (ValueError, TypeError):
            mois_int = None

    # ================================================================
    # Filtres
    # ================================================================
    depenses_qs = Depense.objects.filter(anneeScolaire=annee_selectionnee)
    recettes_qs = Recette.objects.filter(anneeScolaire=annee_selectionnee)
    paiements_qs = Paiement.objects.filter(
        inscription__anneeScolaire=annee_selectionnee
    )

    if section:
        depenses_qs = depenses_qs.filter(section=section)
        recettes_qs = recettes_qs.filter(section=section)
        if section != 'global':
            # ✅ Paiement n'a pas de champ `section` : la section est dérivée
            # de inscription.classe.cycle (1er / 2e). On filtre donc par cycle.
            paiements_qs = paiements_qs.filter(
                inscription__classe__cycle=section
            )
        else:
            paiements_qs = paiements_qs.filter(
                inscription__anneeScolaire=annee_selectionnee
            )

    if mois_int and annee_reelle_mois:
        depenses_qs = depenses_qs.filter(
            date_depense__month=mois_int,
            date_depense__year=annee_reelle_mois,
        )
        recettes_qs = recettes_qs.filter(
            date_recette__month=mois_int,
            date_recette__year=annee_reelle_mois,
        )
        paiements_qs = paiements_qs.filter(
            date_paiement__month=mois_int,
            date_paiement__year=annee_reelle_mois,
        )

    # ================================================================
    # Calculs
    # ================================================================
    recettes_frais = paiements_qs.filter(est_inscription=True).aggregate(
        Sum('montant'))['montant__sum'] or 0
    recettes_scolarite = paiements_qs.filter(est_inscription=False).aggregate(
        Sum('montant'))['montant__sum'] or 0
    recettes_autres = recettes_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    total_recettes = recettes_frais + recettes_scolarite + recettes_autres

    total_depenses = depenses_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    resultat = total_recettes - total_depenses

    depenses_par_categorie = list(
        depenses_qs.values('categorie__nom')
        .annotate(total=Sum('montant'), nb=Count('id'))
        .order_by('-total')
    )

    recettes_par_categorie = list(
        recettes_qs.values('categorie__nom')
        .annotate(total=Sum('montant'), nb=Count('id'))
        .order_by('-total')
    )

    # ================================================================
    # Génération du PDF (code inchangé dans la structure)
    # ================================================================
    response = HttpResponse(content_type='application/pdf')
    filename = f"rapport_comptable_{annee_selectionnee.anneeScolaire}"
    if mois_int:
        filename += f"_{mois_int:02d}"
    filename += ".pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'],
        alignment=TA_CENTER, fontSize=16, spaceAfter=10
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Heading2'],
        alignment=TA_CENTER, fontSize=12, spaceAfter=20, textColor=colors.grey
    )
    section_style = ParagraphStyle(
        'Section', parent=styles['Heading2'],
        fontSize=12, spaceAfter=10, textColor=colors.HexColor('#2c3e50')
    )

    story = []
    ecole = EcoleInfo.get_solo()
    story.append(Paragraph(f"<b>{ecole.nom}</b>", title_style))
    if ecole.ville:
        story.append(Paragraph(f"{ecole.ville}, {ecole.pays or 'Mali'}", subtitle_style))

    story.append(Paragraph("RAPPORT COMPTABLE", title_style))

    if mois_label:
        periode = f"Année scolaire {annee_selectionnee.anneeScolaire} — {mois_label}"
    else:
        periode = f"Année scolaire {annee_selectionnee.anneeScolaire} (complète)"
    if section:
        section_label = dict(Section.choices).get(section, section)
        periode += f" — Section : {section_label}"
    story.append(Paragraph(periode, subtitle_style))
    story.append(Spacer(1, 15))

    # --- Synthèse ---
    story.append(Paragraph("1. SYNTHÈSE", section_style))
    synthesis_data = [
        ['RECETTES', f"{total_recettes:,.0f} FCFA"],
        ['DÉPENSES', f"{total_depenses:,.0f} FCFA"],
        ['RÉSULTAT NET', f"{'+' if resultat >= 0 else ''}{resultat:,.0f} FCFA"],
    ]
    t = Table(synthesis_data, colWidths=[10*cm, 6*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d4edda')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f8d7da')),
        ('BACKGROUND', (0, 2), (-1, 2),
         colors.HexColor('#cce5ff' if resultat >= 0 else '#fff3cd')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

    # --- Détail recettes ---
    story.append(Paragraph("2. DÉTAIL DES RECETTES", section_style))
    recettes_data = [
        ['Type', 'Montant (FCFA)'],
        ["Frais d'inscription", f"{recettes_frais:,.0f}"],
        ['Scolarité', f"{recettes_scolarite:,.0f}"],   # ✅ renommé
    ]
    if recettes_autres > 0:
        recettes_data.append(['Autres recettes (hors paiements)', f"{recettes_autres:,.0f}"])
    recettes_data.append(['TOTAL RECETTES', f"{total_recettes:,.0f}"])

    t = Table(recettes_data, colWidths=[11*cm, 5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28a745')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d4edda')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

    # --- Dépenses par catégorie ---
    story.append(Paragraph("3. DÉPENSES PAR CATÉGORIE", section_style))
    if depenses_par_categorie:
        depenses_data = [['Catégorie', 'Nb', 'Montant (FCFA)', '%']]
        for item in depenses_par_categorie:
            pct = round(float(item['total']) / float(total_depenses) * 100, 1) if total_depenses > 0 else 0
            depenses_data.append([
                item['categorie__nom'],
                str(item['nb']),
                f"{float(item['total']):,.0f}",
                f"{pct}%",
            ])
        depenses_data.append(['TOTAL DÉPENSES', '', f"{total_depenses:,.0f}", '100%'])

        t = Table(depenses_data, colWidths=[7*cm, 1.5*cm, 4*cm, 3*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc3545')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f8d7da')),
            ('ALIGN', (1, 0), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
    else:
        story.append(Paragraph(
            "<i>Aucune dépense enregistrée pour cette période.</i>",
            styles['Normal']
        ))

    story.append(Spacer(1, 20))

    # --- Répartition mensuelle ---
    story.append(Paragraph(
        f"4. RÉPARTITION MENSUELLE — {annee_selectionnee.anneeScolaire}",
        section_style
    ))

    mois_liste = get_mois_annee_scolaire(annee_selectionnee)
    repart_data = [['Mois', 'Paiements', 'Autres rec.', 'Total rec.', 'Dépenses', 'Solde']]

    total_pai, total_aut, total_rec, total_dep, total_sol = 0, 0, 0, 0, 0

    for num_mois, nom_mois, annee_reelle, label in mois_liste:
        pai_m = Paiement.objects.filter(
            inscription__anneeScolaire=annee_selectionnee,
            date_paiement__month=num_mois,
            date_paiement__year=annee_reelle,
        ).aggregate(Sum('montant'))['montant__sum'] or 0

        rec_m = Recette.objects.filter(
            anneeScolaire=annee_selectionnee,
            date_recette__month=num_mois,
            date_recette__year=annee_reelle,
        ).aggregate(Sum('montant'))['montant__sum'] or 0

        dep_m = Depense.objects.filter(
            anneeScolaire=annee_selectionnee,
            date_depense__month=num_mois,
            date_depense__year=annee_reelle,
        ).aggregate(Sum('montant'))['montant__sum'] or 0

        rec_tot = float(rec_m + pai_m)
        dep_tot = float(dep_m)
        solde = rec_tot - dep_tot

        repart_data.append([
            label,
            f"{float(pai_m):,.0f}" if pai_m else '—',
            f"{float(rec_m):,.0f}" if rec_m else '—',
            f"{rec_tot:,.0f}" if rec_tot else '—',
            f"{dep_tot:,.0f}" if dep_tot else '—',
            f"{'+' if solde >= 0 else ''}{solde:,.0f}" if solde else '—',
        ])
        total_pai += float(pai_m)
        total_aut += float(rec_m)
        total_rec += rec_tot
        total_dep += dep_tot
        total_sol += solde

    repart_data.append([
        'TOTAL',
        f"{total_pai:,.0f}",
        f"{total_aut:,.0f}",
        f"{total_rec:,.0f}",
        f"{total_dep:,.0f}",
        f"{'+' if total_sol >= 0 else ''}{total_sol:,.0f}",
    ])

    t = Table(repart_data, colWidths=[2.5*cm, 2.8*cm, 2.8*cm, 2.8*cm, 2.8*cm, 2.8*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e9ecef')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8f9fa')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)

    # Pied de page
    story.append(Spacer(1, 30))
    story.append(Paragraph(
        f"<i>Document généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}</i>",
        ParagraphStyle(
            'Footer', parent=styles['Normal'],
            alignment=TA_RIGHT, textColor=colors.grey, fontSize=9
        )
    ))
    story.append(Spacer(1, 30))

    sig_data = [
        ['Le Comptable', 'Le Directeur'],
        ['', ''],
        ['_________________', '_________________'],
    ]
    t = Table(sig_data, colWidths=[8*cm, 8*cm])
    t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
    ]))
    story.append(t)

    doc.build(story)
    return response


@login_required
@permission_required('ecole.voir_comptabilite', raise_exception=True)
def rapport_csv(request):
    """Génère un export CSV du rapport comptable."""
    from ..utils.dates import get_mois_annee_scolaire, get_annee_reelle_mois

    annee_id = request.GET.get('annee')
    mois = request.GET.get('mois')
    section = request.GET.get('section', '')  # ✅ nouveau filtre

    if annee_id:
        annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
    else:
        annee_selectionnee = AnneeScolaire.objects.first()

    if not annee_selectionnee:
        messages.error(request, "Aucune année scolaire disponible.")
        return redirect('fondamental:rapports_comptables')

    # Parse du mois
    mois_int = None
    annee_reelle_mois = None
    mois_label = None

    if mois:
        try:
            mois_int = int(mois)
            if mois_int in range(1, 13):
                annee_reelle_mois = get_annee_reelle_mois(mois_int, annee_selectionnee)
                for num, nom, an, label in get_mois_annee_scolaire(annee_selectionnee):
                    if num == mois_int:
                        mois_label = label
                        break
            else:
                mois_int = None
        except (ValueError, TypeError):
            mois_int = None

    # Filtres de base
    depenses_qs = Depense.objects.filter(anneeScolaire=annee_selectionnee)
    recettes_qs = Recette.objects.filter(anneeScolaire=annee_selectionnee)
    paiements_qs = Paiement.objects.filter(
        inscription__anneeScolaire=annee_selectionnee
    )

    # ✅ Filtre par section
    if section:
        depenses_qs = depenses_qs.filter(section=section)
        recettes_qs = recettes_qs.filter(section=section)
        if section != 'global':
            # ✅ Paiement n'a pas de champ `section` : la section est dérivée
            # de inscription.classe.cycle (1er / 2e). On filtre donc par cycle.
            paiements_qs = paiements_qs.filter(
                inscription__classe__cycle=section
            )
        else:
            paiements_qs = paiements_qs.filter(
                inscription__anneeScolaire=annee_selectionnee
            )

    if mois_int and annee_reelle_mois:
        depenses_qs = depenses_qs.filter(
            date_depense__month=mois_int,
            date_depense__year=annee_reelle_mois,
        )
        recettes_qs = recettes_qs.filter(
            date_recette__month=mois_int,
            date_recette__year=annee_reelle_mois,
        )
        paiements_qs = paiements_qs.filter(
            date_paiement__month=mois_int,
            date_paiement__year=annee_reelle_mois,
        )

    # Calculs
    recettes_frais = paiements_qs.filter(est_inscription=True).aggregate(
        Sum('montant'))['montant__sum'] or 0
    recettes_scolarite = paiements_qs.filter(est_inscription=False).aggregate(
        Sum('montant'))['montant__sum'] or 0
    recettes_autres = recettes_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    total_recettes = recettes_frais + recettes_scolarite + recettes_autres
    total_depenses = depenses_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    resultat = total_recettes - total_depenses

    # Réponse CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f"rapport_comptable_{annee_selectionnee.anneeScolaire}"
    if mois_int:
        filename += f"_{mois_int:02d}"
    filename += ".csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')

    writer.writerow(['RAPPORT COMPTABLE'])
    if mois_label:
        writer.writerow([f"Période : {mois_label} (année scolaire {annee_selectionnee.anneeScolaire})"])
    else:
        writer.writerow([f"Année scolaire : {annee_selectionnee.anneeScolaire} (complète)"])
    writer.writerow([])

    # Synthèse
    writer.writerow(['SYNTHÈSE'])
    writer.writerow(['Total Recettes', f'{total_recettes:.0f} FCFA'])
    writer.writerow(['Total Dépenses', f'{total_depenses:.0f} FCFA'])
    writer.writerow(['Résultat', f'{resultat:.0f} FCFA'])
    writer.writerow([])

    # Détail recettes
    writer.writerow(['DÉTAIL DES RECETTES'])
    writer.writerow(['Type', 'Montant (FCFA)'])
    writer.writerow(["Frais d'inscription", f'{recettes_frais:.0f}'])
    writer.writerow(['Scolarité', f'{recettes_scolarite:.0f}'])   # ✅ renommé
    if recettes_autres > 0:
        writer.writerow(['Autres recettes (hors paiements)', f'{recettes_autres:.0f}'])
    writer.writerow(['TOTAL', f'{total_recettes:.0f}'])
    writer.writerow([])

    # Détail des paiements (avec mois scolaire)
    writer.writerow(['DÉTAIL DES PAIEMENTS ÉLÈVES'])
    writer.writerow(['Date', 'Élève', 'Classe', 'Type', 'Mois scolaire', 'Montant (FCFA)'])
    for p in paiements_qs.select_related(
        'inscription__eleve', 'inscription__classe'
    ).order_by('date_paiement'):
        type_paiement = "Inscription" if p.est_inscription else "Scolarité"
        mois_sco = p.get_mois_display() if p.mois else '—'
        writer.writerow([
            p.date_paiement.strftime('%d/%m/%Y'),
            _safe_csv(str(p.inscription.eleve)),
            _safe_csv(p.inscription.classe.nomClasse),
            type_paiement,
            mois_sco,   # ✅ Info mois scolaire
            f'{float(p.montant):.0f}',
        ])
    writer.writerow([])

    # Dépenses par catégorie
    writer.writerow(['DÉPENSES PAR CATÉGORIE'])
    writer.writerow(['Catégorie', 'Nb', 'Montant (FCFA)', 'Pourcentage'])
    depenses_par_categorie = depenses_qs.values('categorie__nom').annotate(
        total=Sum('montant'), nb=Count('id')
    ).order_by('-total')
    for item in depenses_par_categorie:
        pct = round(float(item['total']) / float(total_depenses) * 100, 1) if total_depenses > 0 else 0
        writer.writerow([
            _safe_csv(item['categorie__nom']),
            item['nb'],
            f"{float(item['total']):.0f}",
            f'{pct}%',
        ])
    writer.writerow(['TOTAL', '', f'{total_depenses:.0f}', '100%'])
    writer.writerow([])

    # Répartition mensuelle
    writer.writerow([f'RÉPARTITION MENSUELLE — {annee_selectionnee.anneeScolaire}'])
    writer.writerow(['Mois', 'Paiements', 'Autres recettes', 'Total recettes', 'Dépenses', 'Solde'])

    mois_liste = get_mois_annee_scolaire(annee_selectionnee)
    total_pai, total_aut, total_rec, total_dep, total_sol = 0, 0, 0, 0, 0

    for num_mois, nom_mois, annee_reelle, label in mois_liste:
        pai_m = Paiement.objects.filter(
            inscription__anneeScolaire=annee_selectionnee,
            date_paiement__month=num_mois,
            date_paiement__year=annee_reelle,
        ).aggregate(Sum('montant'))['montant__sum'] or 0

        rec_m = Recette.objects.filter(
            anneeScolaire=annee_selectionnee,
            date_recette__month=num_mois,
            date_recette__year=annee_reelle,
        ).aggregate(Sum('montant'))['montant__sum'] or 0

        dep_m = Depense.objects.filter(
            anneeScolaire=annee_selectionnee,
            date_depense__month=num_mois,
            date_depense__year=annee_reelle,
        ).aggregate(Sum('montant'))['montant__sum'] or 0

        rec_tot = float(rec_m + pai_m)
        dep_tot = float(dep_m)
        solde = rec_tot - dep_tot

        writer.writerow([
            label,
            f'{float(pai_m):.0f}',
            f'{float(rec_m):.0f}',
            f'{rec_tot:.0f}',
            f'{dep_tot:.0f}',
            f'{solde:.0f}',
        ])
        total_pai += float(pai_m)
        total_aut += float(rec_m)
        total_rec += rec_tot
        total_dep += dep_tot
        total_sol += solde

    writer.writerow([
        'TOTAL',
        f'{total_pai:.0f}',
        f'{total_aut:.0f}',
        f'{total_rec:.0f}',
        f'{total_dep:.0f}',
        f'{total_sol:.0f}',
    ])

    return response


