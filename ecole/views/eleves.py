"""Vues : eleves."""
from ._deps import *
from ._helpers import *


@login_required
def eleve_list_filtered(request):
    """Liste des élèves avec filtres et impression."""
    classe_id = request.GET.get('classe')
    annee_id = request.GET.get('annee')
    cycle = request.GET.get('cycle', '')
    search = request.GET.get('search', '').strip()

    eleves = Eleve.objects.all().order_by('nomEleve', 'prenomEleve')

    if classe_id:
        eleves = eleves.filter(inscription__classe__idClasse=classe_id)
    if annee_id:
        eleves = eleves.filter(inscription__anneeScolaire__idAnneeScolaire=annee_id)
    if cycle:
        eleves = eleves.filter(inscription__classe__cycle=cycle)
    if search:
        eleves = eleves.filter(
            Q(nomEleve__icontains=search) |
            Q(prenomEleve__icontains=search) |
            Q(matricule__icontains=search)
        )

    eleves = eleves.distinct()

    classe_nom = None
    annee_nom = None
    if classe_id:
        classe = Classe.objects.filter(idClasse=classe_id).first()
        classe_nom = classe.nomClasse if classe else None
    if annee_id:
        annee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
        annee_nom = annee.anneeScolaire if annee else None

    classes_qs = Classe.objects.all().order_by('nomClasse')
    if cycle:
        classes_qs = classes_qs.filter(cycle=cycle)

    eleve_ids = [e.id for e in eleves]
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

    for eleve in eleves:
        eleve.cycle_actuel = cycles_par_eleve.get(eleve.id)

    context = {
        'eleves': eleves,
        'classes': classes_qs,
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'classe_id': classe_id,
        'annee_id': annee_id,
        'cycle_filtre': cycle,
        'search': search,
        'classe_nom': classe_nom,
        'annee_nom': annee_nom,
        'total_eleves': eleves.count(),
    }
    return render(request, 'ecole/eleve/list_filtered.html', context)


@login_required
def eleve_list_filtered_pdf(request):
    """Export PDF de la liste filtrée des élèves."""
    classe_id = request.GET.get('classe')
    annee_id = request.GET.get('annee')
    cycle = request.GET.get('cycle', '')
    search = request.GET.get('search', '').strip()

    eleves = Eleve.objects.all().order_by('nomEleve', 'prenomEleve')

    if classe_id:
        eleves = eleves.filter(inscription__classe__idClasse=classe_id)
    if annee_id:
        eleves = eleves.filter(inscription__anneeScolaire__idAnneeScolaire=annee_id)
    if cycle:
        eleves = eleves.filter(inscription__classe__cycle=cycle)
    if search:
        eleves = eleves.filter(
            Q(nomEleve__icontains=search) |
            Q(prenomEleve__icontains=search) |
            Q(matricule__icontains=search)
        )

    eleves = eleves.distinct()

    classe_nom = None
    annee_nom = None
    if classe_id:
        classe = Classe.objects.filter(idClasse=classe_id).first()
        classe_nom = classe.nomClasse if classe else None
    if annee_id:
        annee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
        annee_nom = annee.anneeScolaire if annee else None

    ecole = EcoleInfo.get_solo()

    filtres = {
        'classe_nom': classe_nom,
        'annee_nom': annee_nom,
        'cycle_filtre': cycle,
        'search': search,
    }

    buffer = generer_liste_eleves_pdf(list(eleves), ecole, filtres)

    filename_parts = ['liste_eleves']
    if classe_nom:
        filename_parts.append(classe_nom.replace(' ', '_'))
    if annee_nom:
        filename_parts.append(annee_nom)
    filename = '_'.join(filename_parts) + '.pdf'

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def statistiques_eleve(request, eleve_id):
    """Statistiques d'un élève (notes 1er + 2e cycle, paiements, inscriptions)."""
    eleve = get_object_or_404(Eleve, id=eleve_id)

    notes_2e = Note.objects.filter(eleve=eleve).values(
        'matiere__nomMatiere', 'matiere__cycle'
    ).annotate(
        moyenne=Avg('note'),
        total=Count('note')
    )

    notes_1er = NoteMensuelle.objects.filter(eleve=eleve).values(
        'matiere__nomMatiere', 'matiere__cycle'
    ).annotate(
        moyenne=Avg('note'),
        total=Count('note')
    )

    notes_par_matiere = {}
    for item in list(notes_1er) + list(notes_2e):
        cle = item['matiere__nomMatiere']
        if cle not in notes_par_matiere:
            notes_par_matiere[cle] = {
                'matiere__nomMatiere': cle,
                'cycle': item['matiere__cycle'],
                'moyennes': [],
                'total': 0,
            }
        if item['moyenne'] is not None:
            notes_par_matiere[cle]['moyennes'].append(float(item['moyenne']))
        notes_par_matiere[cle]['total'] += item['total']

    notes_finales = []
    for matiere, data in notes_par_matiere.items():
        moyenne = round(sum(data['moyennes']) / len(data['moyennes']), 2) if data['moyennes'] else 0
        notes_finales.append({
            'matiere__nomMatiere': matiere,
            'cycle': data['cycle'],
            'moyenne': moyenne,
            'total': data['total'],
        })

    notes_finales.sort(key=lambda x: x['moyenne'], reverse=True)

    nb_notes_1er = NoteMensuelle.objects.filter(eleve=eleve).count()
    nb_notes_2e = Note.objects.filter(eleve=eleve).count()
    nb_notes_total = nb_notes_1er + nb_notes_2e

    toutes_moyennes = [n['moyenne'] for n in notes_finales if n['moyenne'] > 0]
    moyenne_generale = round(sum(toutes_moyennes) / len(toutes_moyennes), 2) if toutes_moyennes else None

    paiements = Paiement.objects.filter(
        inscription__eleve=eleve
    ).select_related('inscription', 'inscription__classe').order_by('-date_paiement')
    total_paye = paiements.aggregate(Sum('montant'))['montant__sum'] or 0

    inscriptions = Inscription.objects.filter(
        eleve=eleve
    ).select_related('classe', 'anneeScolaire').order_by('-anneeScolaire__anneeScolaire')

    inscription_recente = inscriptions.first()
    cycle_actuel = inscription_recente.classe.cycle if inscription_recente else None

    context = {
        'eleve': eleve,
        'notes_par_matiere': notes_finales,
        'nb_notes_1er': nb_notes_1er,
        'nb_notes_2e': nb_notes_2e,
        'nb_notes_total': nb_notes_total,
        'moyenne_generale': moyenne_generale,
        'paiements': paiements,
        'total_paye': total_paye,
        'inscriptions': inscriptions,
        'cycle_actuel': cycle_actuel,
    }
    return render(request, 'ecole/eleve/statistiques.html', context)


@login_required
def eleve_resultats(request):
    """Liste des élèves avec moyenne générale et rang, séparée par cycle."""
    classe_id = request.GET.get('classe')
    annee_id = request.GET.get('annee')
    cycle = request.GET.get('cycle', '')
    search = request.GET.get('search', '').strip()

    inscriptions = Inscription.objects.select_related('eleve', 'classe', 'anneeScolaire')

    if classe_id:
        inscriptions = inscriptions.filter(classe__idClasse=classe_id)
    if annee_id:
        inscriptions = inscriptions.filter(anneeScolaire__idAnneeScolaire=annee_id)
    if cycle:
        inscriptions = inscriptions.filter(classe__cycle=cycle)
    if search:
        inscriptions = inscriptions.filter(
            Q(eleve__nomEleve__icontains=search) |
            Q(eleve__prenomEleve__icontains=search) |
            Q(eleve__matricule__icontains=search)
        )

    eleves_data = []

    for inscription in inscriptions:
        eleve = inscription.eleve
        annee = inscription.anneeScolaire
        cycle_inscription = inscription.classe.cycle

        if cycle_inscription == '1er':
            resultats = ResultatMensuel.objects.filter(
                inscription=inscription
            ).select_related('composition').order_by('composition__mois')

            moyennes_par_periode = {}
            for r in resultats:
                moyennes_par_periode[r.composition.get_mois_display()] = r.moyenne_generale

            moyennes = [float(r.moyenne_generale) for r in resultats]
            moyenne_generale = round(sum(moyennes) / len(moyennes), 2) if moyennes else 0
            rang = resultats.first().rang if resultats.exists() else None

            periodes_ordonnees = list(moyennes_par_periode.items())[-3:]

            eleves_data.append({
                'id': eleve.id,
                'matricule': eleve.matricule,
                'nom': eleve.nomEleve,
                'prenom': eleve.prenomEleve,
                'sexe': eleve.get_sexe_display() if eleve.sexe else '-',
                'date_naiss': eleve.dateNaiss.strftime('%d/%m/%Y') if eleve.dateNaiss else '',
                'lieu_naiss': eleve.lieuNaiss,
                'classe': inscription.classe.nomClasse,
                'cycle': '1er',
                'annee_scolaire': annee.anneeScolaire,
                'periode1': periodes_ordonnees[0] if len(periodes_ordonnees) > 0 else ('-', '-'),
                'periode2': periodes_ordonnees[1] if len(periodes_ordonnees) > 1 else ('-', '-'),
                'periode3': periodes_ordonnees[2] if len(periodes_ordonnees) > 2 else ('-', '-'),
                'moyenne_generale': moyenne_generale,
                'rang': rang,
            })
        else:
            resultats = ResultatTrimestre.objects.filter(
                inscription=inscription
            ).order_by('trimestre')

            trimestres = {}
            moyennes_trimestres = []
            for r in resultats:
                trimestres[r.trimestre] = r.moyenne_generale
                moyennes_trimestres.append(float(r.moyenne_generale))

            moyenne_generale = round(sum(moyennes_trimestres) / len(moyennes_trimestres), 2) \
                if moyennes_trimestres else 0
            premier_resultat = resultats.first()

            eleves_data.append({
                'id': eleve.id,
                'matricule': eleve.matricule,
                'nom': eleve.nomEleve,
                'prenom': eleve.prenomEleve,
                'sexe': eleve.get_sexe_display() if eleve.sexe else '-',
                'date_naiss': eleve.dateNaiss.strftime('%d/%m/%Y') if eleve.dateNaiss else '',
                'lieu_naiss': eleve.lieuNaiss,
                'classe': inscription.classe.nomClasse,
                'cycle': '2e',
                'annee_scolaire': annee.anneeScolaire,
                'periode1': ('Premier trimestre', trimestres.get('Premier trimestre', '-')),
                'periode2': ('Deuxieme trimestre', trimestres.get('Deuxieme trimestre', '-')),
                'periode3': ('Troisieme trimestre', trimestres.get('Troisieme trimestre', '-')),
                'moyenne_generale': moyenne_generale,
                'rang': premier_resultat.rang if premier_resultat else None,
            })

    eleves_data.sort(key=lambda x: x['moyenne_generale'], reverse=True)
    for index, eleve in enumerate(eleves_data, 1):
        eleve['rang_general'] = index

    classe_nom = None
    annee_nom = None
    if classe_id:
        classe = Classe.objects.filter(idClasse=classe_id).first()
        classe_nom = classe.nomClasse if classe else None
    if annee_id:
        annee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
        annee_nom = annee.anneeScolaire if annee else None

    classes_qs = Classe.objects.all().order_by('nomClasse')
    if cycle:
        classes_qs = classes_qs.filter(cycle=cycle)

    context = {
        'eleves_data': eleves_data,
        'classes': classes_qs,
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'classe_id': classe_id,
        'annee_id': annee_id,
        'cycle_filtre': cycle,
        'search': search,
        'classe_nom': classe_nom,
        'annee_nom': annee_nom,
        'total_eleves': len(eleves_data),
    }
    return render(request, 'ecole/eleve/resultats.html', context)


