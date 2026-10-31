"""Vues : résultats scolaires (compositions 1er cycle, trimestres 2e/lycée)."""
from ._deps import *
from ._helpers import *
from ..models import Section
from ..services.resultats import SECTIONS_RESULTATS, resultats, resume_global


@login_required
@permission_required('ecole.view_note', raise_exception=True)
def resultats_index(request):
    """
    Vue unique des résultats du fondamental (1er cycle + 2e cycle).

    La section 'lycee' est redirigée vers la vue lycée dédiée :
    les résultats du lycée ont leur propre écran (bulletins + classement).
    """
    section = request.GET.get('section') or Section.PREMIER
    periode = request.GET.get('periode')
    classe_id = request.GET.get('classe')

    if section == Section.LYCEE:
        return redirect('lycee:resultats_lycee_index')

    if section not in SECTIONS_RESULTATS:
        section = Section.PREMIER

    annees_scolaires = AnneeScolaire.objects.all().order_by('-anneeScolaire')
    annee_id = request.GET.get('annee')
    if annee_id:
        annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
    else:
        annee_selectionnee = annees_scolaires.first()

    sections_choix = [
        {'code': 'global', 'label': 'Synthèse', 'actif': section == 'global'},
    ] + [
        {'code': c, 'label': Section(c).label, 'actif': section == c}
        for c in (Section.PREMIER, Section.SECOND)
    ]

    context = {
        'annees_scolaires': annees_scolaires,
        'annee_selectionnee': annee_selectionnee,
        'sections_choix': sections_choix,
        'section': section,
        'classe_id': classe_id,
    }

    if section == 'global':
        context['resume'] = resume_global(annee_selectionnee)
    else:
        donnees = resultats(
            annee_selectionnee, section,
            periode=periode, classe_id=classe_id,
        )
        context.update(donnees)
        context['section'] = section

    return render(request, 'ecole/resultats/index.html', context)
