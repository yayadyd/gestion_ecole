# ecole/context_processors.py
from django.core.cache import cache
from django.conf import settings
from .models import AnneeScolaire
from .cycles import Cycle


def parametres_globaux(request):
    """Injecte les indicateurs d'activation des modules dans tous les templates."""
    from .models import EcoleInfo
    try:
        ecole = EcoleInfo.get_solo()
        return {
            'ACTIVER_FONDAMENTAL': ecole.activer_fondamental,
            'ACTIVER_LYCEE': ecole.activer_lycee,
        }
    except Exception:
        return {
            'ACTIVER_FONDAMENTAL': True,
            'ACTIVER_LYCEE': True,
        }


def annee_encours(request):
    """Ajoute l'année scolaire en cours à tous les templates (avec cache)."""
    annee = cache.get('annee_encours_globale')
    if annee is None:
        try:
            annee_obj = AnneeScolaire.objects.order_by('-anneeScolaire').first()
            annee = annee_obj.anneeScolaire if annee_obj else "2025-2026"
        except Exception:
            annee = "2025-2026"
        cache.set('annee_encours_globale', annee, 3600)  # Cache 1 heure
    return {'annee_encours': annee}


def trimestres(request):
    """Ajoute les trimestres à tous les templates."""
    from .models import Evaluation
    return {'trimestres': dict(Evaluation.TRIMESTRE)}


def cycle_courant(request):
    """Déduit le cycle courant depuis l'URL."""
    url_name = getattr(request.resolver_match, 'url_name', '') or ''
    cycle = None

    if url_name.startswith('cycle1_') or 'mensuel' in url_name:
        cycle = Cycle.PREMIER.value
    elif url_name.startswith('cycle2_'):
        cycle = Cycle.SECOND.value
    elif request.GET.get('cycle') in ('1er', '2e'):
        cycle = request.GET.get('cycle')

    return {
        'cycle_courant': cycle,
        'peut_gerer_1er': True,
        'peut_gerer_2e': True,
    }


def licence_context(request):
    """Expose la licence dans tous les templates (avec cache)."""
    licence = cache.get('licence_globale')
    if licence is None:
        try:
            from .models import Licence
            licence = Licence.get_licence()
        except Exception:
            licence = None
        cache.set('licence_globale', licence, 300)  # Cache 5 minutes
    return {'licence': licence}


def alertes_configuration(request):
    """Alertes de configuration — avec cache."""
    if not request.user.is_authenticated:
        return {}

    nb = cache.get('classes_sans_matieres_count')
    if nb is None:
        from .models import Classe
        try:
            nb = Classe.objects.filter(matieres_classe__isnull=True).distinct().count()
        except Exception:
            nb = 0
        cache.set('classes_sans_matieres_count', nb, 300)

    return {'classes_sans_matieres': nb}


def ecole_info(request):
    """Expose les informations de l'école."""
    try:
        from .models import EcoleInfo
        ecole = EcoleInfo.get_solo()

        return {
            'ecole': ecole,
            'mode_frais_inscription': ecole.mode_frais_inscription,
            'mode_frais_scolarite': ecole.mode_frais_scolarite,
            'nombre_tranches': ecole.nombre_tranches,
            'libelle_mode_inscription': ecole.get_mode_frais_inscription_display(),
            'libelle_mode_scolarite': ecole.get_mode_frais_scolarite_display(),
            'type_ecole': ecole.type_ecole,
            'libelle_type_ecole': ecole.get_type_ecole_display(),
            'est_franco_arabe': ecole.est_franco_arabe,
            'est_classique': ecole.est_classique,
        }
    except Exception:
        return {
            'ecole': None,
            'mode_frais_inscription': 'annuel',
            'mode_frais_scolarite': 'mensuel',
            'nombre_tranches': 4,
            'libelle_mode_inscription': "Chaque année",
            'libelle_mode_scolarite': "Mensuel (9 versements)",
            'type_ecole': 'franco_arabe',
            'libelle_type_ecole': 'Franco-arabe',
            'est_franco_arabe': True,
            'est_classique': False,
        }


def stats_lycee_header(request):
    """Fournit les stats du lycée pour le bandeau."""
    if not request.user.is_authenticated:
        return {}

    from .lycee_models import ClasseLycee, InscriptionLycee

    try:
        annee_id_url = request.GET.get('annee')
        if annee_id_url:
            # Résoudre en id numérique si c'est une chaîne année ("2027-2028")
            if not str(annee_id_url).isdigit():
                obj = AnneeScolaire.objects.filter(anneeScolaire=annee_id_url).first()
                if obj:
                    annee_id_url = obj.idAnneeScolaire
            request.session['lycee_annee_filtre'] = annee_id_url

        annee_id = request.session.get('lycee_annee_filtre')

        annee_selectionnee = None
        if annee_id:
            annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
        
        if not annee_selectionnee:
            annee_selectionnee = AnneeScolaire.objects.order_by('-anneeScolaire').first()
            if annee_selectionnee:
                request.session['lycee_annee_filtre'] = annee_selectionnee.idAnneeScolaire

        if annee_selectionnee:
            nb_eleves = InscriptionLycee.objects.filter(annee_scolaire=annee_selectionnee).count()
            nb_classes = ClasseLycee.objects.filter(annee_scolaire=annee_selectionnee).count()
            annee_nom = annee_selectionnee.anneeScolaire
        else:
            nb_eleves = 0
            nb_classes = 0
            annee_nom = "—"

        return {
            'nb_eleves': nb_eleves,
            'nb_classes': nb_classes,
            'annee_encours': annee_nom,
            'annee_encours_id': annee_selectionnee.idAnneeScolaire if annee_selectionnee else None,
        }
    except Exception:
        return {
            'nb_eleves': 0,
            'nb_classes': 0,
            'annee_encours': "—",
            'annee_encours_id': None,
        }