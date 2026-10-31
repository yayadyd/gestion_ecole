"""Vues : matieres."""
from ._deps import *
from ._helpers import *


@login_required
@require_POST
@permission_required('ecole.add_matiereclasse', raise_exception=True)
def matiere_classe_copier_annee(request, annee_source_id):
    """Copie toutes les associations de matières d'une année vers une autre."""
    annee_source = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_source_id)
    
    annee_cible = AnneeScolaire.objects.order_by('-anneeScolaire').first()
    
    if annee_source == annee_cible:
        messages.error(request, "L'année source et l'année cible sont identiques.")
        return redirect('fondamental:matiere_classe_list')

    matieres_source = MatiereClasse.objects.filter(annee_scolaire=annee_source)
    
    nb_copiees = 0
    nb_ignorees = 0

    for mc in matieres_source:
        _, created = MatiereClasse.objects.get_or_create(
            classe=mc.classe,
            matiere=mc.matiere,
            annee_scolaire=annee_cible,
            defaults={
                'ordre_affichage': mc.ordre_affichage,
                'obligatoire': mc.obligatoire,
            }
        )
        if created:
            nb_copiees += 1
        else:
            nb_ignorees += 1

    messages.success(
        request, 
        f"✅ Copie terminée : {nb_copiees} matière(s) copiée(s) de {annee_source.anneeScolaire} vers {annee_cible.anneeScolaire}. "
        f"({nb_ignorees} déjà existantes)."
    )
    
    return redirect(f"{reverse('fondamental:matiere_classe_list')}?annee={annee_cible.idAnneeScolaire}")


@login_required
@require_POST
@permission_required('ecole.add_matiereclasse', raise_exception=True)
def matiere_classe_copier_pour_classe(request, classe_id, annee_source_id):
    """Copie les matières d'une classe d'une année précédente vers l'année en cours."""
    classe = get_object_or_404(Classe, idClasse=classe_id)
    annee_source = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_source_id)
    
    # L'année cible est l'année la plus récente (ou celle en cours)
    annee_cible = AnneeScolaire.objects.order_by('-anneeScolaire').first()
    
    if annee_source == annee_cible:
        messages.error(request, "L'année source et l'année cible sont identiques.")
        return redirect('fondamental:matiere_classe_list')

    # Récupérer les matières de cette classe pour l'année source
    matieres_source = MatiereClasse.objects.filter(
        classe=classe, 
        annee_scolaire=annee_source
    )
    
    nb_copiees = 0
    for mc in matieres_source:
        _, created = MatiereClasse.objects.get_or_create(
            classe=classe,
            matiere=mc.matiere,
            annee_scolaire=annee_cible,
            defaults={
                'ordre_affichage': mc.ordre_affichage,
                'obligatoire': mc.obligatoire,
            }
        )
        if created:
            nb_copiees += 1

    messages.success(
        request, 
        f"✅ {nb_copiees} matière(s) copiée(s) pour la classe {classe.nomClasse} de {annee_source.anneeScolaire} vers {annee_cible.anneeScolaire}."
    )
    
    return redirect(f"{reverse('fondamental:matiere_classe_list')}?annee={annee_cible.idAnneeScolaire}")


@login_required
@permission_required('ecole.add_matiereclasse', raise_exception=True)
def matiere_classe_copier_depuis_classe(request, classe_cible_id):
    """Copie les matières d'une classe source vers une classe cible (pour la même année)."""
    classe_cible = get_object_or_404(Classe, idClasse=classe_cible_id)
    annee_id = request.GET.get('annee') or AnneeScolaire.objects.order_by('-anneeScolaire').first().idAnneeScolaire
    annee = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_id)

    if request.method == 'POST':
        classe_source_id = request.POST.get('classe_source')
        classe_source = get_object_or_404(Classe, idClasse=classe_source_id)

        if classe_source.idClasse == classe_cible.idClasse:
            messages.error(request, "La classe source et la classe cible sont identiques.")
            return redirect('fondamental:matiere_classe_list')

        matieres_source = MatiereClasse.objects.filter(
            classe=classe_source, 
            annee_scolaire=annee
        )
        
        nb_copiees = 0
        for mc in matieres_source:
            _, created = MatiereClasse.objects.get_or_create(
                classe=classe_cible,
                matiere=mc.matiere,
                annee_scolaire=annee,
                defaults={
                    'ordre_affichage': mc.ordre_affichage,
                    'obligatoire': mc.obligatoire,
                }
            )
            if created:
                nb_copiees += 1

        messages.success(
            request, 
            f"✅ {nb_copiees} matière(s) copiée(s) de la classe {classe_source.nomClasse} vers {classe_cible.nomClasse}."
        )
        return redirect(f"{reverse('fondamental:matiere_classe_list')}?annee={annee.idAnneeScolaire}")

    # GET : on propose les classes du même cycle
    classes_sources = Classe.objects.filter(
        cycle=classe_cible.cycle
    ).exclude(idClasse=classe_cible.idClasse).order_by('nomClasse')

    context = {
        'classe_cible': classe_cible,
        'classes_sources': classes_sources,
        'annee': annee,
    }
    return render(request, 'ecole/matiere_classe/copier_depuis.html', context)

