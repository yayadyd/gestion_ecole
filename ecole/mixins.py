# ecole/mixins.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse

from .cycles import Cycle, matieres_du_cycle, classes_du_cycle
from .models import AnneeScolaire, Classe, Inscription


class CycleMixin:
    """Injecte le cycle courant dans la vue."""
    cycle_requis = None  # '1er' ou '2e'

    def dispatch(self, request, *args, **kwargs):
        if self.cycle_requis:
            request.cycle = Cycle(self.cycle_requis)
        return super().dispatch(request, *args, **kwargs)

    @property
    def cycle(self):
        return Cycle(self.cycle_requis) if self.cycle_requis else None


class ContexteFiltresMixin:
    """Fournit les listes filtrées par cycle pour les formulaires."""

    def get_contexte_cycle(self, cycle_value=None):
        cycle_value = cycle_value or self.cycle_requis
        return {
            'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
            'classes': classes_du_cycle(cycle_value),
            'matieres': matieres_du_cycle(cycle_value),
        }


class ClasseAnneeMixin:
    """Récupère classe + année depuis la requête et valide le cycle."""

    def get_classe_annee(self, cycle_requis):
        annee_id = self.request.GET.get('annee') or self.request.POST.get('annee_id')
        classe_id = self.request.GET.get('classe') or self.request.POST.get('classe_id')
        if not (annee_id and classe_id):
            return None, None, None
        annee = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_id)
        classe = get_object_or_404(Classe, idClasse=classe_id, cycle=cycle_requis)
        return annee, classe, None


class RetourAvecCycleMixin:
    """
    Mixin pour conserver le paramètre ?cycle= (1er/2e) lors du retour
    à la liste après une action (create / update / delete).
    """

    list_url_name = None
    cycle_param = 'cycle'

    def get_cycle_filtre(self):
        """Retourne la valeur du paramètre cycle (GET ou POST), ou '' si absent."""
        valeur = (
            self.request.GET.get(self.cycle_param) or
            self.request.POST.get(self.cycle_param, '')
        )
        # ✅ FIX: normaliser None en chaîne vide
        return valeur or ''

    def get_success_url(self):
        """URL de retour avec conservation du cycle."""
        if not self.list_url_name:
            raise ValueError(
                f"{self.__class__.__name__} doit définir 'list_url_name'."
            )
        
        # ✅ FIX: Ajouter le préfixe fondamental si nécessaire
        nom_url = self.list_url_name
        if not nom_url.startswith('fondamental:') and not nom_url.startswith('lycee:'):
            nom_url = f'fondamental:{nom_url}'
            
        base = reverse(nom_url)
        cycle = self.get_cycle_filtre()
        return f"{base}?{self.cycle_param}={cycle}" if cycle else base

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cycle_filtre'] = self.get_cycle_filtre()
        return context