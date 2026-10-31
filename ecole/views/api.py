"""Vues : api."""
from ._deps import *
from ._helpers import *


@login_required
def api_eleves_par_classe(request, classe_id):
    annee = request.GET.get('annee')
    qs = Inscription.objects.filter(classe_id=classe_id)
    if annee:
        qs = qs.filter(anneeScolaire_id=annee)
    qs = qs.select_related('eleve')
    data = [{
        'id': ins.eleve.id,
        'matricule': ins.eleve.matricule,
        'nom': ins.eleve.nomEleve,
        'prenom': ins.eleve.prenomEleve,
    } for ins in qs]
    return JsonResponse({'eleves': data})


@login_required
def api_notes_eleve(request, eleve_id):
    annee = request.GET.get('annee')
    notes = Note.objects.filter(eleve_id=eleve_id)
    if annee:
        notes = notes.filter(anneeScolaire_id=annee)
    notes = notes.select_related('matiere', 'evaluation')
    data = [{
        'matiere': n.matiere.nomMatiere,
        'evaluation': n.evaluation.nomEvaluation,
        'note': float(n.note),
        'annee': str(n.anneeScolaire),
    } for n in notes]
    return JsonResponse({'notes': data})


@login_required
def api_recherche_inscriptions(request):
    """API pour rechercher des inscriptions par élève, filtrées par cycle."""
    search_term = request.GET.get('q', '').strip()
    annee_id = request.GET.get('annee_id')
    cycle = request.GET.get('cycle', '').strip()

    try:
        inscriptions = Inscription.objects.select_related(
            'eleve', 'classe', 'anneeScolaire'
        )
        if annee_id:
            inscriptions = inscriptions.filter(anneeScolaire_id=annee_id)
        if cycle:
            inscriptions = inscriptions.filter(classe__cycle=cycle)
        if search_term:
            inscriptions = inscriptions.filter(
                Q(eleve__prenomEleve__icontains=search_term) |
                Q(eleve__nomEleve__icontains=search_term) |
                Q(eleve__matricule__icontains=search_term)
            )
        inscriptions = inscriptions.order_by(
            'eleve__nomEleve', 'eleve__prenomEleve'
        )

        data = []
        for inscription in inscriptions[:50]:
            data.append({
                'id': inscription.idInscription,
                'eleve': str(inscription.eleve),
                'matricule': inscription.eleve.matricule,
                'classe': inscription.classe.nomClasse,
                'cycle': inscription.classe.cycle,
                'annee': inscription.anneeScolaire.anneeScolaire,
                'display': (
                    f"{inscription.eleve.matricule} - "
                    f"{inscription.eleve.nomEleve} {inscription.eleve.prenomEleve} "
                    f"({inscription.classe.nomClasse})"
                )
            })

        return JsonResponse({
            'success': True,
            'inscriptions': data,
            'total': inscriptions.count()
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_recherche_eleves(request):
    """API pour rechercher des élèves."""
    search_term = request.GET.get('q', '').strip()
    cycle = request.GET.get('cycle', '')

    if not search_term or len(search_term) < 2:
        return JsonResponse({'success': True, 'eleves': []})

    try:
        eleves = Eleve.objects.filter(
            Q(matricule__icontains=search_term) |
            Q(prenomEleve__icontains=search_term) |
            Q(nomEleve__icontains=search_term)
        )
        if cycle:
            eleves = eleves.filter(inscription__classe__cycle=cycle)
        eleves = eleves.distinct().order_by('nomEleve', 'prenomEleve')[:50]

        annee_encours = AnneeScolaire.objects.order_by('-anneeScolaire').first()
        data = []
        for eleve in eleves:
            deja_inscrit = False
            if annee_encours:
                deja_inscrit = Inscription.objects.filter(
                    eleve=eleve, anneeScolaire=annee_encours
                ).exists()
            data.append({
                'id': eleve.id,
                'matricule': eleve.matricule,
                'prenom': eleve.prenomEleve,
                'nom': eleve.nomEleve,
                'date_naiss': eleve.dateNaiss.strftime('%d/%m/%Y') if eleve.dateNaiss else '',
                'lieu_naiss': eleve.lieuNaiss,
                'deja_inscrit': deja_inscrit,
            })

        return JsonResponse({'success': True, 'eleves': data, 'total': len(data)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_classe_info(request):
    """Retourne les infos de la classe et de l'élève en fonction du MODE et de l'année."""
    inscription_id = request.GET.get('inscription')
    classe_id = request.GET.get('classe')
    annee_id = request.GET.get('annee')

    ecole = EcoleInfo.get_solo()

    if inscription_id:
        try:
            inscription = Inscription.objects.select_related('eleve', 'classe', 'anneeScolaire').get(idInscription=inscription_id)
            classe = inscription.classe
            annee = inscription.anneeScolaire
            eleve = inscription.eleve
            
            frais = FraisClasseAnnee.objects.filter(classe=classe, annee_scolaire=annee).first()
            frais_inscription = frais.frais_inscription if frais else 0
            frais_scolarite = frais.frais_scolarite if frais else 0

            echeances = calculer_echeances(ecole, classe, annee)
            montant_echeance = echeances[0]['montant'] if echeances else 0

            # ✅ AJOUT DES CHAMPS MANQUANTS POUR LE PRÉ-REMPLISSAGE
            return JsonResponse({
                'success': True,
                'frais_inscription': float(frais_inscription),
                'frais_scolarite_annuel': float(frais_scolarite),
                'montant_echeance': float(montant_echeance),
                'mode_frais_inscription': ecole.mode_frais_inscription,
                'mode_frais_scolarite': ecole.mode_frais_scolarite,
                'nombre_tranches': ecole.nombre_tranches,
                'nb_echeances': len(echeances),
                'classe_nom': classe.nomClasse,
                'eleve_nom': f"{eleve.nomEleve} {eleve.prenomEleve}",
                'matricule': eleve.matricule,
                'cycle': classe.cycle,
            })
        except Inscription.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Inscription non trouvée'})

    elif classe_id:
        try:
            classe = Classe.objects.get(idClasse=classe_id)
            if not annee_id:
                return JsonResponse({
                    'success': False,
                    'error': "L'année scolaire est requise pour afficher les frais."
                })

            annee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
            if annee is None:
                return JsonResponse({'success': False, 'error': 'Année introuvable'})

            frais = FraisClasseAnnee.objects.filter(classe=classe, annee_scolaire=annee).first()
            frais_inscription = frais.frais_inscription if frais else 0
            frais_scolarite = frais.frais_scolarite if frais else 0

            echeances = calculer_echeances(ecole, classe, annee)
            montant_echeance = echeances[0]['montant'] if echeances else 0

            return JsonResponse({
                'success': True,
                'frais_inscription': float(frais_inscription),
                'frais_scolarite_annuel': float(frais_scolarite),
                'montant_echeance': float(montant_echeance),
                'mode_frais_inscription': ecole.mode_frais_inscription,
                'mode_frais_scolarite': ecole.mode_frais_scolarite,
                'nombre_tranches': ecole.nombre_tranches,
                'nb_echeances': len(echeances),
            })
        except Classe.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Classe non trouvée'})

    return JsonResponse({'success': False, 'error': 'Paramètre manquant'})


@login_required
def api_detail_paiements_mois(request):
    """
    API JSON : retourne le détail des paiements pour (classe, mois, année).

    Utilisé par le clic sur une cellule du tableau annuel.
    """
    classe_id = request.GET.get('classe')
    mois = request.GET.get('mois')
    annee = request.GET.get('annee')

    if not (classe_id and mois and annee):
        return JsonResponse({
            'success': False,
            'error': 'Paramètres manquants (classe, mois, annee)'
        })

    try:
        classe_id = int(classe_id)
        mois = int(mois)
        annee = int(annee)
    except (ValueError, TypeError):
        return JsonResponse({
            'success': False,
            'error': 'Paramètres invalides'
        })

    try:
        classe = Classe.objects.get(idClasse=classe_id)
    except Classe.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Classe introuvable'
        })

    # Récupérer les paiements de ce mois
    paiements = Paiement.objects.filter(
        inscription__classe=classe,
        date_paiement__month=mois,
        date_paiement__year=annee,
    ).select_related(
        'inscription__eleve',
        'inscription__classe',
    ).order_by('date_paiement', 'inscription__eleve__nomEleve')

    paiements_data = []
    for p in paiements:
        # Info mois scolaire (si disponible)
        mois_scolaire = None
        if p.mois:
            mois_scolaire = p.get_mois_display()

        paiements_data.append({
            'id': p.idPaiement,
            'date': p.date_paiement.strftime('%d/%m/%Y'),
            'eleve': f"{p.inscription.eleve.nomEleve} {p.inscription.eleve.prenomEleve}",
            'matricule': p.inscription.eleve.matricule,
            'montant': float(p.montant),
            'est_inscription': p.est_inscription,
            'type': "Inscription" if p.est_inscription else "Scolarité",
            'mois_scolaire': mois_scolaire,
            'annee_paiement': p.annee_paiement,
            'observation': p.observation or '',
        })

    # Total
    total = sum(item['montant'] for item in paiements_data)

    # Nom du mois
    MOIS_NOMS = {
        1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
        5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
        9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre',
    }

    return JsonResponse({
        'success': True,
        'classe': classe.nomClasse,
        'mois': mois,
        'mois_nom': MOIS_NOMS.get(mois, ''),
        'annee': annee,
        'paiements': paiements_data,
        'total': total,
        'nb_paiements': len(paiements_data),
    })


@login_required
def api_matieres_par_classe(request, classe_id):
    """API : retourne les matières associées à une classe (vide si non configurée)."""
    try:
        classe = Classe.objects.get(idClasse=classe_id)
    except Classe.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Classe introuvable'})

    # ✅ Matières de l'année demandée (?annee=ID), sinon de la plus récente
    matieres = _matieres_classe_annee(classe, request.GET.get('annee'))

    data = [{'id': m.idMatiere, 'nom': m.nomMatiere} for m in matieres]

    return JsonResponse({
        'success': True,
        'matieres': data,
        'classe': classe.nomClasse,
        'cycle': classe.cycle,
        'has_matieres': len(data) > 0,
    })


