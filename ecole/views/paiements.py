"""Vues : paiements."""
from ._deps import *
from ._helpers import *


def get_montants_attendu(inscription):
    """
    ✅ FIX : Utilise le service pour calculer les montants attendus,
    selon le mode de l'école.
    """
    ecole = EcoleInfo.get_solo()
    montants = calculer_montants_inscription(inscription)

    return {
        'frais_attendu': montants['frais_inscription_attendu'],
        'scolarite_attendue': montants['scolarite_attendue'],
        'total_attendu': montants['total_attendu'],
    }


def get_montants_payes(inscription):
    """Récupère les montants payés (inchangé)."""
    paiements = Paiement.objects.filter(inscription=inscription)
    frais_paye = paiements.filter(est_inscription=True).aggregate(Sum('montant'))['montant__sum'] or 0
    scolarite_payee = paiements.filter(est_inscription=False).aggregate(Sum('montant'))['montant__sum'] or 0
    return {
        'frais_paye': frais_paye,
        'scolarite_payee': scolarite_payee,
        'total_paye': frais_paye + scolarite_payee,
    }


@login_required
@permission_required('ecole.view_paiement_global', raise_exception=True)
def paiements_par_mois_scolaire(request, annee_scolaire, mois):
    annee_scolaire_obj = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    annee_debut = annee_scolaire_obj.get_annee_debut()
    annee_fin = annee_scolaire_obj.get_annee_fin()
    annee_paiement = annee_debut if mois in [10, 11, 12] else annee_fin

    paiements = Paiement.objects.filter(
        mois=mois, annee_paiement=annee_paiement
    ).select_related('inscription__eleve', 'inscription__classe')

    total = paiements.aggregate(Sum('montant'))['montant__sum'] or 0
    mois_scolaires = annee_scolaire_obj.get_mois_scolaires()

    index_actuel = None
    for i, (m, nom, an) in enumerate(mois_scolaires):
        if m == mois and an == annee_paiement:
            index_actuel = i
            break

    mois_precedent = mois_suivant = None
    if index_actuel is not None:
        if index_actuel > 0:
            m, nom, an = mois_scolaires[index_actuel - 1]
            mois_precedent = {'mois': m, 'annee': an, 'nom': nom}
        if index_actuel < len(mois_scolaires) - 1:
            m, nom, an = mois_scolaires[index_actuel + 1]
            mois_suivant = {'mois': m, 'annee': an, 'nom': nom}

    paiements_par_eleve = {}
    for paiement in paiements:
        eleve = paiement.inscription.eleve
        if eleve.id not in paiements_par_eleve:
            paiements_par_eleve[eleve.id] = {
                'eleve': eleve,
                'classe': paiement.inscription.classe,
                'montant_total': 0,
                'paiements': []
            }
        paiements_par_eleve[eleve.id]['montant_total'] += paiement.montant
        paiements_par_eleve[eleve.id]['paiements'].append(paiement)
    nb_paiements = paiements.count()
    moyenne_par_paiement = (total / nb_paiements) if nb_paiements > 0 else 0
    context = {
        'paiements': paiements,
        'paiements_par_eleve': paiements_par_eleve.values(),
        'total': total,
        'mois': mois,
        'annee_paiement': annee_paiement,
        'annee_scolaire': annee_scolaire,
        'annee_scolaire_obj': annee_scolaire_obj,
        'nom_mois': dict(Paiement.MOIS_SCOLAIRES).get(mois),
        'mois_scolaires': mois_scolaires,
        'mois_precedent': mois_precedent,
        'mois_suivant': mois_suivant,
        'moyenne_par_paiement': moyenne_par_paiement,
    }
    return render(request, 'ecole/paiement/par_mois_scolaire.html', context)


@login_required
@permission_required('ecole.view_paiement_global', raise_exception=True)
def paiements_annee_scolaire(request, annee_scolaire):
    """
    Vue annuelle des paiements par classe.

    ✅ Utilise les 12 mois de l'année scolaire (Sept → Août).
    ✅ Filtre par date_paiement (réelle).
    ✅ Affiche le mode de l'école dans une colonne.
    ✅ Chaque cellule est cliquable pour voir le détail.
    """
    from ..utils.dates import get_mois_annee_scolaire

    annee_scolaire_obj = get_object_or_404(
        AnneeScolaire, anneeScolaire=annee_scolaire
    )
    ecole = EcoleInfo.get_solo()

    # 12 mois de l'année scolaire (Sept → Août)
    mois_liste = get_mois_annee_scolaire(annee_scolaire_obj)

    classes = Classe.objects.all().order_by('cycle', 'nomClasse')

    resultats = []
    totaux_par_mois = [0] * 12
    total_general = 0

    # Labels pour le graphique
    labels_mois = [label for num, nom, an, label in mois_liste]

    # Datasets pour le graphique
    graph_datasets = []

    for classe in classes:
        paiements_mensuels_liste = []
        total_classe = 0

        for idx, (num_mois, nom_mois, annee_reelle, label) in enumerate(mois_liste):
            # ✅ Filtre par date_paiement
            total_mois = Paiement.objects.filter(
                inscription__classe=classe,
                inscription__anneeScolaire=annee_scolaire_obj,
                date_paiement__month=num_mois,
                date_paiement__year=annee_reelle,
            ).aggregate(Sum('montant'))['montant__sum'] or 0

            paiements_mensuels_liste.append({
                'mois': num_mois,
                'nom': nom_mois,
                'annee': annee_reelle,
                'label': label,
                'total': float(total_mois),
            })

            total_classe += float(total_mois)
            totaux_par_mois[idx] += float(total_mois)

        nb_eleves = Inscription.objects.filter(
            classe=classe, anneeScolaire=annee_scolaire_obj
        ).count()

        moyenne_par_eleve = (
            total_classe / nb_eleves if nb_eleves > 0 else 0
        )

        resultats.append({
            'classe': classe,
            'paiements_mensuels_liste': paiements_mensuels_liste,
            'total': total_classe,
            'nb_eleves': nb_eleves,
            'moyenne_par_eleve': moyenne_par_eleve,
        })

        total_general += total_classe

        graph_datasets.append({
            'label': classe.nomClasse,
            'data': [p['total'] for p in paiements_mensuels_liste],
        })

    context = {
        'ecole': ecole,
        'mode_frais_scolarite': ecole.get_mode_frais_scolarite_display(),
        'mode_frais_inscription': ecole.get_mode_frais_inscription_display(),

        'resultats': resultats,
        'annee_scolaire': annee_scolaire,
        'annee_scolaire_obj': annee_scolaire_obj,
        'mois_liste': mois_liste,
        'totaux_par_mois': totaux_par_mois,
        'total_general': total_general,
        'annees_scolaires': AnneeScolaire.objects.all().order_by('-anneeScolaire'),

        # JSON pour Chart.js
        'graph_labels_json': json.dumps(labels_mois, ensure_ascii=False),
        'graph_datasets_json': json.dumps(graph_datasets, ensure_ascii=False),
    }
    return render(request, 'ecole/paiement/annee_scolaire.html', context)


@login_required
@permission_required('ecole.view_paiement', raise_exception=True)
def paiements_eleve_annee(request, eleve_id, annee_scolaire):
    """Suivi des paiements d'un élève - Simplifié grâce au service."""
    eleve = get_object_or_404(Eleve, id=eleve_id)
    annee_scolaire_obj = get_object_or_404(
        AnneeScolaire, anneeScolaire=annee_scolaire
    )

    inscription = Inscription.objects.filter(
        eleve=eleve, anneeScolaire=annee_scolaire_obj
    ).first()

    montants = {}
    if inscription:
        montants = calculer_montants_inscription(inscription)

    context = {
        'eleve': eleve,
        'inscription': inscription,
        'annee_scolaire': annee_scolaire,
        'annee_scolaire_obj': annee_scolaire_obj,
        'montants': montants,
        'annees_scolaires': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
    }
    return render(
        request,
        'ecole/paiement/suivi_paiements_annee.html',
        context
    )


@login_required
@permission_required('ecole.view_paiement_global', raise_exception=True)
def suivi_paiements_par_classe(request):
    """
    Suivi des paiements par classe.
    ✅ FIX: Prend en compte les frais d'inscription "Payés avant l'app".
    """
    classe_id = request.GET.get('classe')
    annee_id = request.GET.get('annee')

    inscriptions = Inscription.objects.select_related(
        'eleve', 'classe', 'anneeScolaire'
    )
    if classe_id:
        inscriptions = inscriptions.filter(classe__idClasse=classe_id)
    if annee_id:
        inscriptions = inscriptions.filter(anneeScolaire__idAnneeScolaire=annee_id)

    data = []
    for inscription in inscriptions:
        # On récupère les montants via le service
        montants = calculer_montants_inscription(inscription)
        
        frais_paye = montants['frais_inscription_paye']
        frais_reste = montants['frais_inscription_reste']

        # ✅ FIX: Si l'inscription est marquée "Payé avant l'app", 
        # on considère que les frais sont payés.
        if inscription.frais_inscription_historique:
            frais_paye = montants['frais_inscription_attendu']
            frais_reste = 0

        data.append({
            'eleve': inscription.eleve,
            'inscription': inscription,
            'frais_attendu': montants['frais_inscription_attendu'],
            'frais_paye': frais_paye,                       # ✅ Utilise la valeur corrigée
            'reste_frais': frais_reste,                     # ✅ Utilise la valeur corrigée
            'scolarite_attendue': montants['scolarite_attendue'],
            'scolarite_payee': montants['scolarite_payee'],
            'reste_scolarite': montants['scolarite_reste'],
            'total_attendu': montants['total_attendu'],
            'total_paye': montants['total_paye'] + (montants['frais_inscription_attendu'] if inscription.frais_inscription_historique else 0),
            'reste_total': max(0, montants['reste'] - (montants['frais_inscription_attendu'] if inscription.frais_inscription_historique else 0)),
        })

    # Calcul des totaux globaux
    totaux = {
        'frais_attendu': sum(d['frais_attendu'] for d in data),
        'frais_paye': sum(d['frais_paye'] for d in data),
        'reste_frais': sum(d['reste_frais'] for d in data),
        'scolarite_attendue': sum(d['scolarite_attendue'] for d in data),
        'scolarite_payee': sum(d['scolarite_payee'] for d in data),
        'reste_scolarite': sum(d['reste_scolarite'] for d in data),
        'total_attendu': sum(d['total_attendu'] for d in data),
        'total_paye': sum(d['total_paye'] for d in data),
        'reste_total': sum(d['reste_total'] for d in data),
    }

    context = {
        'data': data,
        'classes': Classe.objects.all().order_by('nomClasse'),
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'classe_id': classe_id,
        'annee_id': annee_id,
        'totaux': totaux,
    }
    return render(request, 'ecole/paiement/suivi_par_classe.html', context)


@login_required
@permission_required('ecole.change_classe', raise_exception=True)
def frais_classe_annee_edit(request):
    """
    Permet de configurer les frais pour toutes les classes d'une année en une seule fois.
    """
    annee_id = request.GET.get('annee')
    
    if not annee_id:
        annee_actuelle = AnneeScolaire.objects.order_by('-anneeScolaire').first()
        if annee_actuelle:
            annee_id = annee_actuelle.idAnneeScolaire
            return redirect(f"{reverse('fondamental:frais_classe_annee_edit')}?annee={annee_id}")
        else:
            messages.error(request, "Veuillez créer une année scolaire d'abord.")
            return redirect('fondamental:annee_list')

    annee = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_id)
    classes = Classe.objects.all().order_by('cycle', 'nomClasse')

    for c in classes:
        FraisClasseAnnee.objects.get_or_create(
            classe=c, 
            annee_scolaire=annee,
            defaults={'frais_inscription': 0, 'frais_scolarite': 0}
        )

    FraisFormSet = modelformset_factory(
        FraisClasseAnnee, 
        form=FraisClasseAnneeForm, 
        extra=0
    )

    if request.method == 'POST':
        formset = FraisFormSet(
            request.POST, 
            queryset=FraisClasseAnnee.objects.filter(annee_scolaire=annee).select_related('classe')
        )
        if formset.is_valid():
            formset.save()
            messages.success(request, f"Les frais pour l'année {annee.anneeScolaire} ont été mis à jour avec succès.")
            return redirect(f"{reverse('fondamental:frais_classe_annee_edit')}?annee={annee_id}")
    else:
        formset = FraisFormSet(
            queryset=FraisClasseAnnee.objects.filter(annee_scolaire=annee).select_related('classe')
        )

    for form in formset:
        form.classe_obj = form.instance.classe

    context = {
        'formset': formset,
        'annee': annee,
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
    }
    return render(request, 'ecole/classe/frais_annee.html', context)


