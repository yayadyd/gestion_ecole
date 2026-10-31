# ecole/lycee_views.py
"""
Vues du Lycée - INDÉPENDANTES des cycles 1er et 2e.

Contient :
- CRUD Matières, Coefficients, Classes, Élèves, Inscriptions
- Saisie des notes PAR CLASSE (filtrage classe + matière + trimestre)
- Calcul des moyennes et classement
- Bulletins (affichage + PDF)
- APIs de recherche (élèves, inscriptions, matières par classe/série)
- Paiements (vues)
- Emploi du temps (vues)

⚠️ Toute la logique métier est dans lycee_services.py.
   Ce fichier ne contient QUE des vues.
"""
import io
import json
import logging
import os
from urllib.parse import urlencode
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Sum, Avg, Count, Q
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.utils import timezone

from .lycee_models import (
    MatiereLycee, CoefficientLycee, ClasseLycee,
    EleveLycee, InscriptionLycee, NoteLycee,
    ResultatTrimestreLycee, DetailResultatLycee, PaiementLycee,
    PlageHoraireLycee, EmploiTempsLycee,
    CreneauEmploiTempsLycee, MatiereClasseLycee,
)
from .lycee_forms import (
    MatiereLyceeForm, CoefficientLyceeForm, ClasseLyceeForm,
    EleveLyceeForm, InscriptionLyceeForm, NoteLyceeForm,
    SaisieNotesLyceeFilterForm, PaiementLyceeForm,
    PlageHoraireLyceeForm, MatiereClasseLyceeForm,
)
from .models import AnneeScolaire, EcoleInfo
from .forms import AnneeScolaireForm, EcoleInfoForm

# ✅ FIX: Import UNIQUE de toutes les fonctions métier depuis lycee_services.py
from .lycee_services import (
    calculer_montants_inscription_lycee,
    calculer_echeances_lycee,
    calculer_montants_paiement_lycee,
    calculer_moyennes_classe,
    classer_classe,
)
from .cycles import appreciation_sur_20
from .lycee_services import generer_carte_lycee_pdf, generer_planche_cartes_lycee_pdf
from .utils.qr_code import generer_qr_code_base64
from .utils.cartes import couleur_valide, fond_valide


logger = logging.getLogger(__name__)


# =====================================================================
# HELPERS (locaux aux vues — pas de logique métier)
# =====================================================================

def _construire_lignes_resultat(resultats):
    """Prépare les lignes pour les tableaux de bulletins."""
    lignes = []
    for r in resultats:
        lignes.append({
            'resultat': r,
            'eleve': r.inscription.eleve,
            'classe': r.inscription.classe,
        })
    return lignes


def _stats_resultats(resultats):
    """Calcule les statistiques d'une liste de résultats."""
    if not resultats:
        return None
    moyennes = [float(r.moyenne_generale) for r in resultats]
    return {
        'moyenne_classe': round(sum(moyennes) / len(moyennes), 2),
        'meilleure_moyenne': max(moyennes),
        'nb_eleves': len(resultats),
    }


def _get_coefficient(matiere, niveau, serie):
    """Récupère le coefficient d'une matière pour un niveau/série donné."""
    try:
        coef = CoefficientLycee.objects.get(
            matiere=matiere, niveau=niveau, serie=serie or ''
        )
        return coef.coefficient
    except CoefficientLycee.DoesNotExist:
        return Decimal('1.0')


def _appreciation_lycee(moyenne):
    """Appréciation d'une moyenne sur 20 (échelle unique de l'application)."""
    return appreciation_sur_20(moyenne)


def _trouver_annee_precedente_lycee(annee):
    """Retourne l'année scolaire précédente ou None."""
    try:
        annee_debut = annee.get_annee_debut()
        annee_precedente_str = f"{annee_debut - 1}-{annee_debut}"
        return AnneeScolaire.objects.filter(
            anneeScolaire=annee_precedente_str
        ).first()
    except Exception:
        return None


# =====================================================================
# 1. TABLEAU DE BORD
# =====================================================================

@login_required
def dashboard_lycee(request):
    """Tableau de bord du lycée."""
    annee_id = request.GET.get('annee')
    annees = AnneeScolaire.objects.all().order_by('-anneeScolaire')

    if annee_id:
        annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
    else:
        annee_selectionnee = annees.first()

    nb_eleves = EleveLycee.objects.count()
    nb_classes = ClasseLycee.objects.filter(
        annee_scolaire=annee_selectionnee
    ).count() if annee_selectionnee else 0
    nb_matieres = MatiereLycee.objects.filter(active=True).count()
    nb_inscriptions = InscriptionLycee.objects.filter(
        annee_scolaire=annee_selectionnee
    ).count() if annee_selectionnee else 0

    niveaux_stats = []
    if annee_selectionnee:
        for code, libelle in ClasseLycee.NIVEAU_CHOICES:
            nb = InscriptionLycee.objects.filter(
                annee_scolaire=annee_selectionnee,
                classe__niveau=code,
            ).count()
            niveaux_stats.append({
                'code': code,
                'libelle': libelle,
                'nb': nb,
            })

    context = {
        'annees': annees,
        'annee_selectionnee': annee_selectionnee,
        'nb_eleves': nb_eleves,
        'nb_classes': nb_classes,
        'nb_matieres': nb_matieres,
        'nb_inscriptions': nb_inscriptions,
        'niveaux_stats': niveaux_stats,
    }
    return render(request, 'lycee/dashboard.html', context)


# =====================================================================
# 2. MATIÈRES DU LYCÉE
# =====================================================================

class MatiereLyceeListView(LoginRequiredMixin, ListView):
    model = MatiereLycee
    template_name = 'lycee/matiere/list.html'
    context_object_name = 'matieres'
    paginate_by = 30

    def get_queryset(self):
        qs = super().get_queryset()
        domaine = self.request.GET.get('domaine')
        if domaine:
            qs = qs.filter(domaine=domaine)
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(Q(nom__icontains=search) | Q(nom_arabe__icontains=search))
        return qs.order_by('ordre_affichage', 'nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['domaine_filtre'] = self.request.GET.get('domaine', '')
        context['search'] = self.request.GET.get('search', '')
        context['domaines'] = MatiereLycee.DOMAINE_CHOICES
        context['total'] = MatiereLycee.objects.count()
        return context


class MatiereLyceeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.add_matiere'
    raise_exception = True
    model = MatiereLycee
    form_class = MatiereLyceeForm
    template_name = 'lycee/matiere/form.html'
    success_url = reverse_lazy('lycee:matiere_list')

    def form_valid(self, form):
        messages.success(self.request, "Matière du lycée créée avec succès !")
        return super().form_valid(form)


class MatiereLyceeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.change_matiere'
    raise_exception = True
    model = MatiereLycee
    form_class = MatiereLyceeForm
    template_name = 'lycee/matiere/form.html'
    success_url = reverse_lazy('lycee:matiere_list')

    def form_valid(self, form):
        messages.success(self.request, "Matière du lycée mise à jour !")
        return super().form_valid(form)


class MatiereLyceeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.delete_matiere'
    raise_exception = True
    model = MatiereLycee
    template_name = 'lycee/matiere/confirm_delete.html'
    success_url = reverse_lazy('lycee:matiere_list')


# =====================================================================
# 3. COEFFICIENTS
# =====================================================================

@login_required
def coefficient_list(request):
    """Liste des coefficients, groupés par niveau et série."""
    coefficients = CoefficientLycee.objects.select_related('matiere').all()

    niveau = request.GET.get('niveau', '')
    serie = request.GET.get('serie', '')
    matiere_id = request.GET.get('matiere', '')

    if niveau:
        coefficients = coefficients.filter(niveau=niveau)
    if serie:
        coefficients = coefficients.filter(serie=serie)
    if matiere_id:
        coefficients = coefficients.filter(matiere_id=matiere_id)

    coefficients = coefficients.order_by('niveau', 'serie', 'matiere__ordre_affichage')

    context = {
        'coefficients': coefficients,
        'niveau_filtre': niveau,
        'serie_filtre': serie,
        'matiere_filtre': matiere_id,
        'niveaux': CoefficientLycee.NIVEAU_CHOICES,
        'series': CoefficientLycee.SERIE_CHOICES,
        'matieres': MatiereLycee.objects.filter(active=True).order_by('nom'),
        'total': coefficients.count(),
    }
    return render(request, 'lycee/coefficient/list.html', context)


class CoefficientCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.change_matiere'
    raise_exception = True
    model = CoefficientLycee
    form_class = CoefficientLyceeForm
    template_name = 'lycee/coefficient/form.html'
    success_url = reverse_lazy('lycee:coefficient_list')

    def form_valid(self, form):
        messages.success(self.request, "Coefficient créé avec succès !")
        return super().form_valid(form)


class CoefficientUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.change_matiere'
    raise_exception = True
    model = CoefficientLycee
    form_class = CoefficientLyceeForm
    template_name = 'lycee/coefficient/form.html'
    success_url = reverse_lazy('lycee:coefficient_list')

    def form_valid(self, form):
        messages.success(self.request, "Coefficient mis à jour !")
        return super().form_valid(form)


class CoefficientDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.change_matiere'
    raise_exception = True
    model = CoefficientLycee
    template_name = 'lycee/coefficient/confirm_delete.html'
    success_url = reverse_lazy('lycee:coefficient_list')


# =====================================================================
# 4. CLASSES DU LYCÉE
# =====================================================================

class ClasseLyceeListView(LoginRequiredMixin, ListView):
    model = ClasseLycee
    template_name = 'lycee/classe/list.html'
    context_object_name = 'classes'

    def get_queryset(self):
        qs = super().get_queryset().select_related('annee_scolaire')
        niveau = self.request.GET.get('niveau')
        annee_id = self.request.GET.get('annee')

        # ✅ Priorité à l'URL, sinon on lit la session
        if not annee_id:
            annee_id = self.request.session.get('lycee_annee_filtre')
            
        if not annee_id:
            annee_actuelle = AnneeScolaire.objects.order_by('-anneeScolaire').first()
            if annee_actuelle:
                annee_id = str(annee_actuelle.idAnneeScolaire)

        if niveau:
            qs = qs.filter(niveau=niveau)
        if annee_id:
            # ✅ L'année peut être un id numérique ou une chaîne "2027-2028"
            if str(annee_id).isdigit():
                qs = qs.filter(annee_scolaire_id=annee_id)
            else:
                qs = qs.filter(annee_scolaire__anneeScolaire=annee_id)
            
        return qs.order_by('niveau', 'serie', 'nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        niveau_filtre = self.request.GET.get('niveau', '')
        
        # On s'assure que annee_filtre correspond à ce qui a été utilisé dans get_queryset
        annee_filtre = self.request.GET.get('annee') or self.request.session.get('lycee_annee_filtre')
        if not annee_filtre:
            annee_actuelle = AnneeScolaire.objects.order_by('-anneeScolaire').first()
            if annee_actuelle:
                annee_filtre = annee_actuelle.idAnneeScolaire
        # Si c'est une chaîne année ("2027-2028"), résoudre en id numérique
        if annee_filtre and not str(annee_filtre).isdigit():
            obj = AnneeScolaire.objects.filter(anneeScolaire=annee_filtre).first()
            if obj:
                annee_filtre = obj.idAnneeScolaire
        # La session peut contenir un entier : on normalise en chaîne,
        # car le template et `isdigit()` attendent du texte.
        annee_filtre = str(annee_filtre) if annee_filtre not in (None, '') else ''

        context['niveau_filtre'] = niveau_filtre
        context['annee_filtre'] = annee_filtre
        context['niveaux'] = ClasseLycee.NIVEAU_CHOICES
        context['annees'] = AnneeScolaire.objects.all().order_by('-anneeScolaire')
        context['total'] = len(context['classes'])

        # ... (le reste de get_context_data pour le nombre d'élèves par classe)
        annee_id_int = None
        if annee_filtre and annee_filtre.isdigit():
            annee_id_int = int(annee_filtre)

        for classe in context['classes']:
            if annee_id_int:
                classe.nb_eleves_affiche = classe.inscriptionlycee_set.filter(
                    annee_scolaire_id=annee_id_int
                ).count()
            else:
                classe.nb_eleves_affiche = classe.inscriptionlycee_set.count()

        return context


class ClasseLyceeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.add_classe'
    raise_exception = True
    model = ClasseLycee
    form_class = ClasseLyceeForm
    template_name = 'lycee/classe/form.html'
    success_url = reverse_lazy('lycee:classe_list')

    def form_valid(self, form):
        # 1. Sauvegarder la nouvelle classe
        response = super().form_valid(form)
        nouvelle_classe = self.object

        # 2. Chercher une classe "modèle" du même niveau et de la même série
        # (On prend la plus récente qui possède déjà des matières)
        classe_modele = ClasseLycee.objects.filter(
            niveau=nouvelle_classe.niveau,
            serie=nouvelle_classe.serie,
            matieres_classe__isnull=False # Assure qu'elle a des matières
        ).exclude(pk=nouvelle_classe.pk).first()

        # 3. Si une classe modèle est trouvée, on copie ses matières
        if classe_modele:
            matieres_modele = MatiereClasseLycee.objects.filter(classe=classe_modele)
            for mc in matieres_modele:
                MatiereClasseLycee.objects.create(
                    classe=nouvelle_classe,
                    matiere=mc.matiere,
                    ordre_affichage=mc.ordre_affichage,
                    obligatoire=mc.obligatoire
                )
            messages.success(
                self.request, 
                f"Classe '{nouvelle_classe.nom}' créée avec succès ! "
                f"Les {matieres_modele.count()} matière(s) de '{classe_modele.nom}' ont été copiées automatiquement."
            )
        else:
            messages.success(
                self.request, 
                f"Classe '{nouvelle_classe.nom}' créée avec succès ! "
                f"(Aucune matière héritée car aucune autre classe de ce niveau/série n'en possède)."
            )

        return response


class ClasseLyceeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.change_classe'
    raise_exception = True
    model = ClasseLycee
    form_class = ClasseLyceeForm
    template_name = 'lycee/classe/form.html'
    success_url = reverse_lazy('lycee:classe_list')

    def form_valid(self, form):
        messages.success(self.request, "Classe du lycée mise à jour !")
        return super().form_valid(form)


class ClasseLyceeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.delete_classe'
    raise_exception = True
    model = ClasseLycee
    template_name = 'lycee/classe/confirm_delete.html'
    success_url = reverse_lazy('lycee:classe_list')


# =====================================================================
# 5. ÉLÈVES DU LYCÉE
# =====================================================================

class EleveLyceeListView(LoginRequiredMixin, ListView):
    model = EleveLycee
    template_name = 'lycee/eleve/list.html'
    context_object_name = 'eleves'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('search', '').strip()
        niveau = self.request.GET.get('niveau', '').strip()

        if search:
            qs = qs.filter(
                Q(matricule__icontains=search) |
                Q(nom__icontains=search) |
                Q(prenom__icontains=search)
            )

        # ✅ FIX: filtre par niveau via les inscriptions
        if niveau:
            qs = qs.filter(inscriptionlycee__classe__niveau=niveau).distinct()

        return qs.order_by('nom', 'prenom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        eleve_ids = [e.id_eleve for e in context['eleves']]

        inscriptions = InscriptionLycee.objects.filter(
            eleve_id__in=eleve_ids
        ).select_related('classe', 'annee_scolaire').order_by(
            'eleve_id', '-annee_scolaire__anneeScolaire'
        )

        vues = set()
        infos_par_eleve = {}
        for ins in inscriptions:
            if ins.eleve_id in vues:
                continue
            vues.add(ins.eleve_id)
            infos_par_eleve[ins.eleve_id] = {
                'classe': ins.classe.nom,
                'niveau': ins.classe.get_niveau_display(),
                'serie': ins.classe.serie,
                'annee': ins.annee_scolaire.anneeScolaire,
            }

        for eleve in context['eleves']:
            eleve.infos_actuelles = infos_par_eleve.get(eleve.id_eleve)

        context['search'] = self.request.GET.get('search', '')
        context['niveau_filtre'] = self.request.GET.get('niveau', '') 
        context['total'] = EleveLycee.objects.count()
        return context


class EleveLyceeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.add_eleve'
    raise_exception = True
    model = EleveLycee
    form_class = EleveLyceeForm
    template_name = 'lycee/eleve/form.html'
    success_url = reverse_lazy('lycee:eleve_list')

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Élève créé avec succès ! Matricule : {form.instance.matricule}"
        )
        return super().form_valid(form)


class EleveLyceeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.change_eleve'
    raise_exception = True
    model = EleveLycee
    form_class = EleveLyceeForm
    template_name = 'lycee/eleve/form.html'
    success_url = reverse_lazy('lycee:eleve_list')

    def form_valid(self, form):
        messages.success(self.request, "Élève mis à jour avec succès !")
        return super().form_valid(form)


class EleveLyceeDetailView(LoginRequiredMixin, DetailView):
    model = EleveLycee
    template_name = 'lycee/eleve/detail.html'
    context_object_name = 'eleve'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        eleve = self.get_object()
        context['inscriptions'] = InscriptionLycee.objects.filter(
            eleve=eleve
        ).select_related('classe', 'annee_scolaire').order_by('-annee_scolaire__anneeScolaire')
        return context


class EleveLyceeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.delete_eleve'
    raise_exception = True
    model = EleveLycee
    template_name = 'lycee/eleve/confirm_delete.html'
    success_url = reverse_lazy('lycee:eleve_list')


@login_required
def eleve_list_filtered_lycee(request):
    """Liste des élèves du lycée avec filtres."""
    classe_id = request.GET.get('classe')
    annee_id = request.GET.get('annee')
    niveau = request.GET.get('niveau', '')
    search = request.GET.get('search', '').strip()

    eleves = EleveLycee.objects.all().order_by('nom', 'prenom')

    if classe_id:
        eleves = eleves.filter(inscriptionlycee__classe_id=classe_id)
    if annee_id:
        eleves = eleves.filter(inscriptionlycee__annee_scolaire_id=annee_id)
    if niveau:
        eleves = eleves.filter(inscriptionlycee__classe__niveau=niveau)
    if search:
        eleves = eleves.filter(
            Q(nom__icontains=search) |
            Q(prenom__icontains=search) |
            Q(matricule__icontains=search)
        )

    eleves = eleves.distinct()

    classe_nom = None
    annee_nom = None
    if classe_id:
        classe = ClasseLycee.objects.filter(id_classe=classe_id).first()
        classe_nom = classe.nom if classe else None
    if annee_id:
        annee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
        annee_nom = annee.anneeScolaire if annee else None

    eleve_ids = [e.id_eleve for e in eleves]
    inscriptions = InscriptionLycee.objects.filter(
        eleve_id__in=eleve_ids
    ).select_related('classe', 'annee_scolaire').order_by(
        'eleve_id', '-annee_scolaire__anneeScolaire'
    )

    vues = set()
    infos_par_eleve = {}
    for ins in inscriptions:
        if ins.eleve_id in vues:
            continue
        vues.add(ins.eleve_id)
        infos_par_eleve[ins.eleve_id] = {
            'classe': ins.classe.nom,
            'niveau': ins.classe.get_niveau_display(),
            'serie': ins.classe.serie,
            'annee': ins.annee_scolaire.anneeScolaire,
            'inscription_id': ins.id_inscription,
        }

    for eleve in eleves:
        eleve.infos_actuelles = infos_par_eleve.get(eleve.id_eleve)

    classes_qs = ClasseLycee.objects.all().order_by('niveau', 'serie', 'nom')
    if annee_id:
        # ✅ Les classes affichées dans le filtre doivent correspondre à
        # l'année scolaire sélectionnée (une classe peut exister plusieurs
        # années, mais ses élèves sont inscrits une année donnée).
        classes_qs = classes_qs.filter(
            inscriptionlycee__annee_scolaire_id=annee_id
        ).distinct()
    if niveau:
        classes_qs = classes_qs.filter(niveau=niveau)

    context = {
        'eleves': eleves,
        'classes': classes_qs,
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'classe_id': classe_id,
        'annee_id': annee_id,
        'niveau_filtre': niveau,
        'search': search,
        'classe_nom': classe_nom,
        'annee_nom': annee_nom,
        'total_eleves': eleves.count(),
    }
    return render(request, 'lycee/eleve/list_filtered.html', context)


@login_required
def eleve_list_filtered_pdf_lycee(request):
    """Export PDF de la liste filtrée des élèves du lycée."""
    messages.info(request, "Export PDF à venir.")
    return redirect('lycee:eleve_list_filtered')


# =====================================================================
# 6. INSCRIPTIONS
# =====================================================================

class InscriptionLyceeListView(LoginRequiredMixin, ListView):
    model = InscriptionLycee
    template_name = 'lycee/inscription/list.html'
    context_object_name = 'inscriptions'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related('eleve', 'classe', 'annee_scolaire')
        classe_id = self.request.GET.get('classe', '')
        annee_id = self.request.GET.get('annee', '')
        niveau = self.request.GET.get('niveau', '')

        if classe_id:
            qs = qs.filter(classe_id=classe_id)
        if annee_id:
            qs = qs.filter(annee_scolaire_id=annee_id)
        if niveau:
            qs = qs.filter(classe__niveau=niveau)

        return qs.order_by('-annee_scolaire__anneeScolaire', 'eleve__nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        annee_id = self.request.GET.get('annee', '')
        classes_qs = ClasseLycee.objects.all().order_by('niveau', 'nom')
        if annee_id:
            # ✅ Les classes du filtre sont limitées à l'année sélectionnée.
            classes_qs = classes_qs.filter(
                inscriptionlycee__annee_scolaire_id=annee_id
            ).distinct()
        context['classes'] = classes_qs
        context['annees'] = AnneeScolaire.objects.all().order_by('-anneeScolaire')
        context['niveaux'] = ClasseLycee.NIVEAU_CHOICES
        context['classe_filtre'] = self.request.GET.get('classe', '')
        context['annee_filtre'] = annee_id
        context['niveau_filtre'] = self.request.GET.get('niveau', '')
        return context
    


class InscriptionLyceeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.add_inscription'
    raise_exception = True
    model = InscriptionLycee
    form_class = InscriptionLyceeForm
    template_name = 'lycee/inscription/form.html'
    success_url = reverse_lazy('lycee:inscription_list')

    def form_valid(self, form):
        messages.success(self.request, "Inscription créée avec succès !")
        return super().form_valid(form)


class InscriptionLyceeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.change_inscription'
    raise_exception = True
    model = InscriptionLycee
    form_class = InscriptionLyceeForm
    template_name = 'lycee/inscription/form.html'
    success_url = reverse_lazy('lycee:inscription_list')


class InscriptionLyceeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.delete_inscription'
    raise_exception = True
    model = InscriptionLycee
    template_name = 'lycee/inscription/confirm_delete.html'
    success_url = reverse_lazy('lycee:inscription_list')


# =====================================================================
# 7. SAISIE DES NOTES PAR CLASSE
# =====================================================================

@login_required
@permission_required('ecole.add_note', raise_exception=True)
def saisie_notes_par_classe(request):
    """
    Saisie des notes du lycée par classe.

    Étape 1 : Formulaire de filtrage (classe + matière + trimestre + année)
              ✅ Les matières sont filtrées selon la classe sélectionnée.
    Étape 2 : Saisie des notes pour tous les élèves de la classe
    """
    # Récupération des paramètres (GET ou POST)
    classe_id = request.GET.get('classe') or request.POST.get('classe')
    matiere_id = request.GET.get('matiere') or request.POST.get('matiere')
    trimestre = request.GET.get('trimestre') or request.POST.get('trimestre')
    annee_id = request.GET.get('annee_scolaire') or request.POST.get('annee_scolaire')

    # ============================================================
    # ÉTAPE 1 : Afficher le formulaire de filtrage
    # ============================================================
    if not all([classe_id, matiere_id, trimestre, annee_id]):
        # ✅ FIX: passer les données GET au formulaire pour que
        # le filtrage des matières fonctionne dès que la classe est choisie
        form = SaisieNotesLyceeFilterForm(
            data=request.GET if request.GET else None,
            initial={
                'classe': classe_id,
                'matiere': matiere_id,
                'trimestre': trimestre,
                'annee_scolaire': annee_id,
            }
        )
        return render(request, 'lycee/notes/saisie_filtre.html', {'form': form})

    # ============================================================
    # ÉTAPE 2 : Saisie des notes
    # ============================================================
    try:
        classe = ClasseLycee.objects.get(id_classe=classe_id)
        matiere = MatiereLycee.objects.get(id_matiere=matiere_id)
        annee = AnneeScolaire.objects.get(idAnneeScolaire=annee_id)
    except (ClasseLycee.DoesNotExist, MatiereLycee.DoesNotExist, AnneeScolaire.DoesNotExist):
        messages.error(request, "Paramètres invalides.")
        return redirect('lycee:saisie_notes_par_classe')

    # ✅ FIX: vérifier que la matière est bien enseignée dans cette classe
    matiere_autorisee = MatiereClasseLycee.objects.filter(
        classe=classe, matiere=matiere
    ).exists()

    if not matiere_autorisee:
        # Vérifier si la classe a des matières configurées
        classe_a_des_matieres = MatiereClasseLycee.objects.filter(
            classe=classe
        ).exists()

        if classe_a_des_matieres:
            messages.error(
                request,
                f"La matière « {matiere.nom} » n'est pas enseignée dans la classe "
                f"{classe.nom}. Choisissez une autre matière."
            )
            return redirect('lycee:saisie_notes_par_classe')
        
    inscriptions = InscriptionLycee.objects.filter(
        classe=classe, annee_scolaire=annee
    ).select_related('eleve').order_by('eleve__nom', 'eleve__prenom')

    notes_existantes = {
        n.inscription_id: n
        for n in NoteLycee.objects.filter(
            inscription__in=inscriptions,
            matiere=matiere,
            trimestre=trimestre,
        )
    }

    eleves_avec_notes = []
    for inscription in inscriptions:
        note = notes_existantes.get(inscription.id_inscription)
        eleves_avec_notes.append({
            'inscription': inscription,
            'eleve': inscription.eleve,
            'note_classe': note.note_classe if note else None,
            'note_composition': note.note_composition if note else None,
            'note_id': note.id_note if note else None,
        })

    if request.method == 'POST':
        compteurs = {'inserees': 0, 'maj': 0, 'supprimees': 0, 'invalides': 0}

        for inscription in inscriptions:
            key_classe = f'note_{inscription.id_inscription}_classe'
            key_compo = f'note_{inscription.id_inscription}_compo'

            note_classe_raw = request.POST.get(key_classe, '').replace(',', '.').strip()
            note_compo_raw = request.POST.get(key_compo, '').replace(',', '.').strip()

            if not note_classe_raw and not note_compo_raw:
                deleted, _ = NoteLycee.objects.filter(
                    inscription=inscription, matiere=matiere, trimestre=trimestre
                ).delete()
                if deleted:
                    compteurs['supprimees'] += 1
                continue

            try:
                note_classe = Decimal(note_classe_raw) if note_classe_raw else Decimal('0')
                note_compo = Decimal(note_compo_raw) if note_compo_raw else Decimal('0')
            except (ValueError, TypeError):
                compteurs['invalides'] += 1
                continue

            if not (0 <= note_classe <= 20) or not (0 <= note_compo <= 20):
                compteurs['invalides'] += 1
                continue

            _, created = NoteLycee.objects.update_or_create(
                inscription=inscription,
                matiere=matiere,
                trimestre=trimestre,
                defaults={
                    'note_classe': note_classe,
                    'note_composition': note_compo,
                }
            )

            if created:
                compteurs['inserees'] += 1
            else:
                compteurs['maj'] += 1

        message = (
            f"{compteurs['inserees']} nouvelle(s), "
            f"{compteurs['maj']} mise(s) à jour, "
            f"{compteurs['supprimees']} supprimée(s)."
        )
        if compteurs['invalides']:
            message += f" ⚠️ {compteurs['invalides']} valeur(s) invalide(s)."
            messages.warning(request, message)
        else:
            messages.success(request, message)

        url = reverse('lycee:saisie_notes_par_classe')
        params = {
            'classe': classe.id_classe,
            'matiere': matiere.id_matiere,
            'trimestre': trimestre,
            'annee_scolaire': annee.idAnneeScolaire,
        }
        return redirect(f"{url}?{urlencode(params)}")

    classes_qs = ClasseLycee.objects.all().order_by('niveau', 'serie', 'nom')
    if annee:
        classes_qs = classes_qs.filter(annee_scolaire=annee)

    context = {
        'classe': classe,
        'matiere': matiere,
        'trimestre': trimestre,
        'annee_scolaire': annee,
        'eleves_avec_notes': eleves_avec_notes,
        'total_eleves': len(eleves_avec_notes),
        'trimestres': NoteLycee.TRIMESTRE_CHOICES,
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'classes': classes_qs,
        'matieres': MatiereLycee.objects.filter(active=True).order_by('ordre_affichage', 'nom'),
    }
    return render(request, 'lycee/notes/saisie_classe.html', context)


@login_required
def notes_list(request):
    """Liste des notes du lycée avec filtres."""
    notes = NoteLycee.objects.select_related(
        'inscription__eleve', 'inscription__classe', 'matiere'
    ).all()

    search = request.GET.get('search', '').strip()
    classe_id = request.GET.get('classe', '')
    matiere_id = request.GET.get('matiere', '')
    trimestre = request.GET.get('trimestre', '')
    annee_id = request.GET.get('annee', '')

    if search:
        notes = notes.filter(
            Q(inscription__eleve__matricule__icontains=search) |
            Q(inscription__eleve__nom__icontains=search) |
            Q(inscription__eleve__prenom__icontains=search)
        )
    if classe_id:
        notes = notes.filter(inscription__classe_id=classe_id)
    if matiere_id:
        notes = notes.filter(matiere_id=matiere_id)
    if trimestre:
        notes = notes.filter(trimestre=trimestre)
    if annee_id:
        notes = notes.filter(inscription__annee_scolaire_id=annee_id)

    notes = notes.order_by(
        '-inscription__annee_scolaire__anneeScolaire',
        'inscription__eleve__nom',
        'matiere__ordre_affichage',
    )

    paginator = Paginator(notes, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'notes': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'classes': ClasseLycee.objects.all().order_by('niveau', 'serie', 'nom'),
        'matieres': MatiereLycee.objects.filter(active=True).order_by('nom'),
        'trimestres': NoteLycee.TRIMESTRE_CHOICES,
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'search': search,
        'classe_filtre': classe_id,
        'matiere_filtre': matiere_id,
        'trimestre_filtre': trimestre,
        'annee_filtre': annee_id,
    }
    return render(request, 'lycee/notes/list.html', context)


# =====================================================================
# 8. CALCUL DES MOYENNES ET CLASSEMENT
# =====================================================================

@login_required
@permission_required('ecole.add_note', raise_exception=True)
def calculer_moyennes_trimestre(request, classe_id, trimestre, annee_id):
    """
    Calcule les moyennes trimestrielles pour une classe du lycée.
    Calcul en lot (lycee_services) : rapide même avec beaucoup de notes.
    """
    classe = get_object_or_404(ClasseLycee, id_classe=classe_id)
    annee = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_id)

    nb_calcules = calculer_moyennes_classe(classe, trimestre, annee)

    if nb_calcules == 0:
        messages.warning(
            request,
            f"Aucune moyenne calculée pour {classe.nom} — {trimestre} : "
            f"aucune note n'a été saisie pour ce trimestre."
        )
    else:
        messages.success(
            request,
            f"✅ {nb_calcules} moyenne(s) calculée(s) avec succès pour "
            f"{classe.nom} — {trimestre} ({annee.anneeScolaire})."
        )
    return redirect('lycee:bulletins_classe', classe_id=classe_id, trimestre=trimestre, annee_id=annee_id)


@login_required
def classer_eleves_trimestre(request, classe_id, trimestre, annee_id):
    """Classe les élèves d'une classe par moyenne décroissante."""
    classe = get_object_or_404(ClasseLycee, id_classe=classe_id)
    annee = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_id)

    nb_classes = classer_classe(classe, trimestre, annee)

    if nb_classes == 0:
        messages.warning(
            request,
            f"Aucun classement à mettre à jour pour {classe.nom} — {trimestre} : "
            f"calculez d'abord les moyennes."
        )
    else:
        messages.success(
            request,
            f"✅ Classement mis à jour pour {classe.nom} — {trimestre} "
            f"({nb_classes} élève(s) classé(s))."
        )
    return redirect('lycee:bulletins_classe', classe_id=classe_id, trimestre=trimestre, annee_id=annee_id)


# =====================================================================
# 9. BULLETINS
# =====================================================================

@login_required
def bulletins_index(request):
    """Page d'accueil des bulletins du lycée."""
    annees = AnneeScolaire.objects.all().order_by('-anneeScolaire')
    annee_id = request.GET.get('annee')
    annee_selectionnee = None
    if annee_id:
        annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
    if not annee_selectionnee:
        annee_selectionnee = annees.first()

    classes = ClasseLycee.objects.all().order_by('niveau', 'serie', 'nom')
    if annee_selectionnee:
        classes = classes.filter(annee_scolaire=annee_selectionnee)

    context = {
        'annees': annees,
        'annee_selectionnee': annee_selectionnee,
        'classes': classes,
        'trimestres': NoteLycee.TRIMESTRE_CHOICES,
    }
    return render(request, 'lycee/bulletins/index.html', context)


@login_required
def bulletins_classe(request, classe_id, trimestre, annee_id):
    """Bulletins de tous les élèves d'une classe du lycée."""
    classe = get_object_or_404(ClasseLycee, id_classe=classe_id)
    annee = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_id)

    resultats = list(ResultatTrimestreLycee.objects.filter(
        inscription__classe=classe,
        trimestre=trimestre,
        inscription__annee_scolaire=annee,
    ).select_related('inscription__eleve').prefetch_related('details__matiere'))

    resultats.sort(key=lambda r: r.moyenne_generale, reverse=True)

    stats = _stats_resultats(resultats)

    context = {
        'classe': classe,
        'trimestre': trimestre,
        'annee_scolaire': annee,
        'resultats': resultats,
        'stats': stats,
    }
    return render(request, 'lycee/bulletins/classe.html', context)


@login_required
def bulletin_eleve(request, inscription_id, trimestre):
    """Bulletin individuel d'un élève du lycée."""
    inscription = get_object_or_404(InscriptionLycee, id_inscription=inscription_id)
    eleve = inscription.eleve
    classe = inscription.classe
    annee = inscription.annee_scolaire

    resultat = ResultatTrimestreLycee.objects.filter(
        inscription=inscription, trimestre=trimestre
    ).prefetch_related('details__matiere').first()

    details_enrichis = []
    if resultat:
        for d in resultat.details.all():
            details_enrichis.append({
                'matiere': d.matiere,
                'note_classe': d.note_classe,
                'note_composition': d.note_composition,
                'note_composition_40': d.note_composition * 2,
                'moyenne_matiere': d.moyenne_matiere,
                'coefficient': d.coefficient,
                'moyenne_coefficientee': d.moyenne_coefficientee,
                'appreciation': d.appreciation,
            })

    meilleur = ResultatTrimestreLycee.objects.filter(
        inscription__classe=classe, trimestre=trimestre
    ).order_by('-moyenne_generale').first()

    context = {
        'eleve': eleve,
        'inscription': inscription,
        'classe': classe,
        'annee_scolaire': annee,
        'trimestre': trimestre,
        'resultat': resultat,
        'details_enrichis': details_enrichis,
        'meilleur': meilleur,
    }
    return render(request, 'lycee/bulletins/eleve.html', context)


@login_required
def bulletin_eleve_pdf(request, inscription_id, trimestre):
    """Génère le PDF du bulletin d'un élève du lycée."""
    from .lycee_services import generer_bulletin_lycee_pdf, stats_classe

    inscription = get_object_or_404(InscriptionLycee, id_inscription=inscription_id)
    eleve = inscription.eleve
    classe = inscription.classe

    resultat = ResultatTrimestreLycee.objects.filter(
        inscription=inscription, trimestre=trimestre
    ).prefetch_related('details__matiere').first()

    if not resultat:
        messages.warning(request, "Aucun bulletin disponible pour ce trimestre.")
        return redirect('lycee:bulletin_eleve',
                        inscription_id=inscription_id,
                        trimestre=trimestre)

    stats = stats_classe(classe, trimestre, resultat)

    buffer = generer_bulletin_lycee_pdf(
        eleve=eleve,
        inscription=inscription,
        resultat=resultat,
        stats=stats,
        trimestre=trimestre,
    )

    trimestre_clean = trimestre.replace(' ', '_')
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="bulletin_{eleve.matricule}_{trimestre_clean}.pdf"'
    )
    return response

@login_required
def bulletins_classe_pdf(request, classe_id, trimestre, annee_id):
    """Export PDF de tous les bulletins d'une classe."""
    from .lycee_services import generer_bulletins_classe_lycee_pdf

    classe = get_object_or_404(ClasseLycee, id_classe=classe_id)
    annee = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_id)

    buffer = generer_bulletins_classe_lycee_pdf(classe, trimestre)

    if buffer is None:
        messages.warning(request, "Aucun bulletin disponible pour cette classe.")
        return redirect('lycee:bulletins_classe',
                        classe_id=classe_id,
                        trimestre=trimestre,
                        annee_id=annee_id)

    filename = f"bulletins_{classe.nom}_{trimestre}_{annee.anneeScolaire}.pdf"
    filename = filename.replace(' ', '_')

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# =====================================================================
# 10. APIs DE RECHERCHE
# =====================================================================

@login_required
def api_recherche_eleves_lycee(request):
    """API : recherche d'élèves du lycée par nom/prénom/matricule."""
    search = request.GET.get('q', '').strip()

    if not search or len(search) < 2:
        return JsonResponse({'success': True, 'eleves': []})

    eleves = EleveLycee.objects.filter(
        Q(matricule__icontains=search) |
        Q(nom__icontains=search) |
        Q(prenom__icontains=search)
    ).order_by('nom', 'prenom')[:50]

    data = [{
        'id': e.id_eleve,
        'matricule': e.matricule,
        'nom': e.nom,
        'prenom': e.prenom,
        'sexe': e.get_sexe_display(),
        'date_naissance': e.date_naissance.strftime('%d/%m/%Y'),
        'lieu_naissance': e.lieu_naissance,
        'display': f"{e.matricule} — {e.nom} {e.prenom}",
    } for e in eleves]

    return JsonResponse({'success': True, 'eleves': data, 'total': len(data)})


@login_required
def api_recherche_inscriptions_lycee(request):
    """API : recherche d'inscriptions du lycée."""
    search = request.GET.get('q', '').strip()
    classe_id = request.GET.get('classe', '')
    annee_id = request.GET.get('annee', '')

    inscriptions = InscriptionLycee.objects.select_related(
        'eleve', 'classe', 'annee_scolaire'
    )

    if classe_id:
        inscriptions = inscriptions.filter(classe_id=classe_id)
    if annee_id:
        inscriptions = inscriptions.filter(annee_scolaire_id=annee_id)
    if search:
        inscriptions = inscriptions.filter(
            Q(eleve__matricule__icontains=search) |
            Q(eleve__nom__icontains=search) |
            Q(eleve__prenom__icontains=search)
        )

    inscriptions = inscriptions.order_by('eleve__nom')[:50]

    data = [{
        'id': ins.id_inscription,
        'eleve': f"{ins.eleve.nom} {ins.eleve.prenom}",
        'matricule': ins.eleve.matricule,
        'classe': ins.classe.nom,
        'niveau': ins.classe.get_niveau_display(),
        'serie': ins.classe.serie,
        'annee': ins.annee_scolaire.anneeScolaire,
        'display': (
            f"{ins.eleve.matricule} — {ins.eleve.nom} {ins.eleve.prenom} "
            f"({ins.classe.nom})"
        ),
    } for ins in inscriptions]

    return JsonResponse({'success': True, 'inscriptions': data})


@login_required
def api_classes_par_annee_lycee(request, annee_id):
    """
    API : retourne les classes du lycée qui ont au moins une inscription
    pour l'année scolaire donnée. Utilisée par le formulaire d'inscription
    pour filtrer automatiquement la liste des classes selon l'année.
    """
    try:
        annee = AnneeScolaire.objects.get(idAnneeScolaire=annee_id)
    except AnneeScolaire.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Année introuvable'})

    classes = (
        ClasseLycee.objects
        .filter(inscriptionlycee__annee_scolaire=annee)
        .distinct()
        .order_by('niveau', 'serie', 'nom')
    )
    data = []
    for c in classes:
        data.append({
            'id': c.id_classe,
            'nom': c.nom,
            'niveau': c.get_niveau_display(),
            'serie': c.serie,
        })
    return JsonResponse({'success': True, 'classes': data})


@login_required
def api_matieres_par_classe_lycee(request, classe_id):
    try:
        classe = ClasseLycee.objects.get(id_classe=classe_id)
    except ClasseLycee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Classe introuvable'})

    matieres = MatiereLycee.objects.filter(active=True).order_by('ordre_affichage', 'nom')

    data = []
    for m in matieres:
        coef = _get_coefficient(m, classe.niveau, classe.serie)
        data.append({
            'id': m.id_matiere,
            'nom': m.nom,
            'nom_arabe': m.nom_arabe,
            'domaine': m.get_domaine_display(),
            'coefficient': float(coef),
        })

    return JsonResponse({
        'success': True,
        'classe': classe.nom,
        'niveau': classe.niveau,
        'serie': classe.serie,
        'matieres': data,
    })


@login_required
def api_matieres_par_serie(request):
    """
    API : retourne les matières pour un niveau et une série donnés,
    avec leurs coefficients.
    """
    niveau = request.GET.get('niveau', '')
    serie = request.GET.get('serie', '')

    if not niveau:
        return JsonResponse({'success': False, 'error': 'Niveau requis'})

    matieres = MatiereLycee.objects.filter(active=True).order_by('ordre_affichage', 'nom')

    data = []
    for m in matieres:
        coef = _get_coefficient(m, niveau, serie)
        data.append({
            'id': m.id_matiere,
            'nom': m.nom,
            'nom_arabe': m.nom_arabe,
            'coefficient': float(coef),
        })

    return JsonResponse({
        'success': True,
        'niveau': niveau,
        'serie': serie,
        'matieres': data,
    })


@login_required
def api_notes_eleve_lycee(request, eleve_id):
    """API : notes d'un élève du lycée."""
    notes = NoteLycee.objects.filter(
        inscription__eleve_id=eleve_id
    ).select_related('matiere').order_by('-trimestre', 'matiere__ordre_affichage')

    data = [{
        'matiere': n.matiere.nom,
        'trimestre': n.trimestre,
        'note_classe': float(n.note_classe),
        'note_composition': float(n.note_composition),
        'moyenne': float(n.moyenne_matiere),
    } for n in notes]

    return JsonResponse({'success': True, 'notes': data})

@login_required
def api_info_inscription_lycee(request, inscription_id):
    """
    API : retourne les infos de paiement d'une inscription du lycée.
    Utilisée par paiement/form.html pour pré-remplir le montant.
    """
    from .lycee_services import calculer_montants_inscription_lycee

    try:
        inscription = InscriptionLycee.objects.select_related(
            'classe', 'annee_scolaire', 'eleve'
        ).get(id_inscription=inscription_id)
    except InscriptionLycee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Inscription introuvable'})

    montants = calculer_montants_inscription_lycee(inscription)

    return JsonResponse({
        'success': True,
        'est_oriente': montants.get('est_oriente', False),
        'frais_inscription': float(inscription.classe.frais_inscription or 0),
        'frais_inscription_reste': float(montants['frais_inscription_reste']),
        'frais_scolarite_annuel': float(inscription.classe.frais_scolarite or 0),
        'scolarite_attendu': float(montants['scolarite_attendue']),
        'scolarite_paye': float(montants['scolarite_payee']),
        'scolarite_reste': float(montants['scolarite_reste']),
        'reste_total': float(montants['reste']),
    })

@login_required
def api_matieres_par_classe_lycee_avec_coef(request, classe_id):
    """
    API : retourne les matières d'une classe du lycée,
    avec leur coefficient pour le niveau/série.
    """
    try:
        classe = ClasseLycee.objects.get(id_classe=classe_id)
    except ClasseLycee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Classe introuvable'})

    matieres_classe = MatiereClasseLycee.objects.filter(
        classe=classe
    ).select_related('matiere').order_by('ordre_affichage', 'matiere__nom')

    data = []
    for mc in matieres_classe:
        try:
            coef_obj = CoefficientLycee.objects.get(
                matiere=mc.matiere,
                niveau=classe.niveau,
                serie=classe.serie,
            )
            coefficient = float(coef_obj.coefficient)
        except CoefficientLycee.DoesNotExist:
            coefficient = 1.0

        data.append({
            'id': mc.matiere.id_matiere,
            'nom': mc.matiere.nom,
            'nom_arabe': mc.matiere.nom_arabe,
            'domaine': mc.matiere.get_domaine_display(),
            'coefficient': coefficient,
            'ordre_affichage': mc.ordre_affichage,
            'obligatoire': mc.obligatoire,
        })

    return JsonResponse({
        'success': True,
        'classe': classe.nom,
        'niveau': classe.niveau,
        'serie': classe.serie,
        'matieres': data,
        'total': len(data),
    })


# =====================================================================
# 11. PAIEMENTS DU LYCÉE
# =====================================================================

@login_required
def paiement_lycee_list(request):
    """Liste des paiements du lycée."""
    paiements = PaiementLycee.objects.select_related(
        'inscription__eleve', 'inscription__classe'
    ).all()

    search = request.GET.get('search', '').strip()
    classe_id = request.GET.get('classe', '')
    type_paiement = request.GET.get('type', '')
    annee = request.GET.get('annee', '')
    if not annee:
        latest = AnneeScolaire.objects.order_by('-anneeScolaire').first()
        if latest:
            annee = latest.anneeScolaire

    if search:
        paiements = paiements.filter(
            Q(inscription__eleve__matricule__icontains=search) |
            Q(inscription__eleve__nom__icontains=search) |
            Q(inscription__eleve__prenom__icontains=search)
        )
    if classe_id:
        paiements = paiements.filter(inscription__classe_id=classe_id)
    if type_paiement == 'inscription':
        paiements = paiements.filter(est_inscription=True)
    elif type_paiement == 'scolarite':
        paiements = paiements.filter(est_inscription=False)
    if annee:
        paiements = paiements.filter(
            inscription__annee_scolaire__anneeScolaire=annee
        )

    total = paiements.aggregate(Sum('montant'))['montant__sum'] or 0

    paginator = Paginator(paiements, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    classes_qs = ClasseLycee.objects.all().order_by('niveau', 'serie', 'nom')
    if annee:
        classes_qs = classes_qs.filter(annee_scolaire__anneeScolaire=annee)

    context = {
        'paiements': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'total': total,
        'classes': classes_qs,
        'annees_scolaires': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'search': search,
        'classe_filtre': classe_id,
        'type_filtre': type_paiement,
        'annee_filtre': annee,
    }
    return render(request, 'lycee/paiement/list.html', context)


@login_required
def paiement_lycee_detail(request, inscription_id):
    """
    Détail des paiements d'une inscription du lycée.
    ✅ Vue unique : affiche les paiements + sélecteur d'année.
    """
    inscription = get_object_or_404(
        InscriptionLycee.objects.select_related('eleve', 'classe', 'annee_scolaire'),
        id_inscription=inscription_id
    )

    montants = calculer_montants_inscription_lycee(inscription)

    context = {
        'eleve': inscription.eleve,
        'inscription': inscription,
        'classe': inscription.classe,
        'annee_scolaire': inscription.annee_scolaire,
        'montants': montants,
        'annees_scolaires': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'inscriptions_eleve': InscriptionLycee.objects.filter(
            eleve=inscription.eleve
        ).select_related('annee_scolaire').order_by('-annee_scolaire__anneeScolaire'),
    }
    return render(request, 'lycee/paiement/detail.html', context)


class PaiementLyceeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.add_paiement'
    raise_exception = True
    model = PaiementLycee
    form_class = PaiementLyceeForm
    template_name = 'lycee/paiement/form.html'

    def get_initial(self):
        initial = super().get_initial()
        inscription_id = self.request.GET.get('inscription')
        if inscription_id:
            try:
                inscription = InscriptionLycee.objects.select_related(
                    'eleve', 'classe', 'annee_scolaire'
                ).get(id_inscription=inscription_id)
                initial['inscription'] = inscription
                initial['annee_scolaire_filter'] = inscription.annee_scolaire

                est_inscription = self.request.GET.get('est_inscription')
                mois = self.request.GET.get('mois')

                if est_inscription:
                    initial['est_inscription'] = True
                    initial['montant'] = inscription.classe.frais_inscription
                elif mois:
                    from .models import EcoleInfo
                    ecole = EcoleInfo.get_solo()
                    echeances = calculer_echeances_lycee(
                        ecole, inscription.classe, inscription.annee_scolaire
                    )
                    try:
                        mois_int = int(mois)
                        for ech in echeances:
                            if ech.get('mois') == mois_int:
                                initial['montant'] = ech['montant']
                                break
                    except (ValueError, TypeError):
                        pass

                if mois:
                    try:
                        initial['mois'] = int(mois)
                    except (ValueError, TypeError):
                        pass
            except InscriptionLycee.DoesNotExist:
                pass
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ✅ FIX: transmettre le mode de scolarité au template
        ecole = EcoleInfo.get_solo()
        context['mode_frais_scolarite'] = ecole.mode_frais_scolarite
        context['ecole'] = ecole

        inscription_id = self.request.GET.get('inscription')
        context['prefill_inscription_id'] = inscription_id or ''  # ✅ AJOUT

        if inscription_id:
            try:
                context['inscription'] = InscriptionLycee.objects.select_related(
                    'eleve', 'classe', 'annee_scolaire'
                ).get(id_inscription=inscription_id)
            except InscriptionLycee.DoesNotExist:
                pass

        return context

    def form_valid(self, form):
        messages.success(self.request, "Paiement enregistré avec succès !")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('lycee:paiement_detail', kwargs={
            'inscription_id': self.object.inscription_id
        })


class PaiementLyceeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.change_paiement'
    raise_exception = True
    model = PaiementLycee
    form_class = PaiementLyceeForm
    template_name = 'lycee/paiement/form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ✅ FIX: même correction que pour CreateView
        ecole = EcoleInfo.get_solo()
        context['mode_frais_scolarite'] = ecole.mode_frais_scolarite
        context['ecole'] = ecole
        context['prefill_inscription_id'] = (
            self.object.inscription_id if self.object else ''
        )

        if self.object and self.object.inscription:
            context['inscription'] = self.object.inscription

        return context

    def form_valid(self, form):
        messages.success(self.request, "Paiement mis à jour !")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('lycee:paiement_detail', kwargs={
            'inscription_id': self.object.inscription_id
        })


class PaiementLyceeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.delete_paiement'
    raise_exception = True
    model = PaiementLycee
    template_name = 'lycee/paiement/confirm_delete.html'

    def get_success_url(self):
        inscription_id = self.object.inscription_id
        messages.success(self.request, "Paiement supprimé !")
        return reverse('lycee:paiement_detail', kwargs={'inscription_id': inscription_id})


# =====================================================================
# 12. EMPLOI DU TEMPS DU LYCÉE - PLAGES HORAIRES
# =====================================================================

@login_required
def plage_lycee_list(request):
    """Liste des plages horaires du lycée."""
    plages = PlageHoraireLycee.objects.all().order_by('ordre', 'heure_debut')

    context = {
        'plages': plages,
        'total': plages.count(),
        'nb_pauses': plages.filter(est_pause=True).count(),
        'nb_cours': plages.filter(est_pause=False).count(),
    }
    return render(request, 'lycee/emploi_temps/plage/list.html', context)


class PlageLyceeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.add_plagehoraire'
    raise_exception = True
    model = PlageHoraireLycee
    form_class = PlageHoraireLyceeForm
    template_name = 'lycee/emploi_temps/plage/form.html'
    success_url = reverse_lazy('lycee:plage_lycee_list')

    def form_valid(self, form):
        messages.success(self.request, "Plage horaire créée avec succès !")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.warning(
            "Formulaire invalide (Plage Lycée Create) : %s",
            dict(form.errors)
        )
        return super().form_invalid(form)


class PlageLyceeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.change_plagehoraire'
    raise_exception = True
    model = PlageHoraireLycee
    form_class = PlageHoraireLyceeForm
    template_name = 'lycee/emploi_temps/plage/form.html'
    success_url = reverse_lazy('lycee:plage_lycee_list')

    def form_valid(self, form):
        messages.success(self.request, "Plage horaire mise à jour !")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.warning(
            "Formulaire invalide (Plage Lycée Update) : %s",
            dict(form.errors)
        )
        return super().form_invalid(form)


class PlageLyceeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.delete_plagehoraire'
    raise_exception = True
    model = PlageHoraireLycee
    template_name = 'lycee/emploi_temps/plage/confirm_delete.html'
    success_url = reverse_lazy('lycee:plage_lycee_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Plage horaire supprimée !")
        return super().delete(request, *args, **kwargs)


# =====================================================================
# 12.2 INDEX EMPLOI DU TEMPS LYCÉE
# =====================================================================

@login_required
def emploi_temps_lycee_index(request):
    """Page d'accueil : liste des classes du lycée avec accès à leur emploi du temps."""
    annee_param = request.GET.get('annee')
    niveau = request.GET.get('niveau', '')

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

    classes = ClasseLycee.objects.all()
    if niveau:
        classes = classes.filter(niveau=niveau)
    # ✅ ClasseLycee a déjà un champ annee_scolaire : on filtre directement.
    # (Le filtre par inscriptionlycee/emplois_temps éliminait les classes
    #  sans inscription, ce qui masquait les 11ème non encore remplies.)
    if annee_selectionnee:
        classes = classes.filter(annee_scolaire=annee_selectionnee)
    classes = classes.order_by('niveau', 'serie', 'nom')

    emplois_existants = {}
    if annee_selectionnee:
        for et in EmploiTempsLycee.objects.filter(annee_scolaire=annee_selectionnee):
            emplois_existants[et.classe_id] = et

    classes_enrichies = []
    for c in classes:
        classes_enrichies.append({
            'classe': c,
            'emploi_temps': emplois_existants.get(c.id_classe),
        })

    classes_par_niveau = {
        '10': [],
        '11': [],
        '12': [],
    }
    for item in classes_enrichies:
        classes_par_niveau[item['classe'].niveau].append(item)

    context = {
        'annees_scolaires': annees_scolaires,
        'annee_selectionnee': annee_selectionnee,
        'annee_encours': annee_selectionnee.anneeScolaire if annee_selectionnee else None,
        'niveau_filtre': niveau,
        'classes_10': classes_par_niveau.get('10', []),
        'classes_11': classes_par_niveau.get('11', []),
        'classes_12': classes_par_niveau.get('12', []),
    }
    return render(request, 'lycee/emploi_temps/index.html', context)


# =====================================================================
# 12.3 GESTION EMPLOI DU TEMPS LYCÉE
# =====================================================================

@login_required
def emploi_temps_lycee_gestion(request, classe_id, annee_scolaire):
    """Affiche la grille d'édition de l'emploi du temps d'une classe du lycée."""
    classe = get_object_or_404(ClasseLycee, id_classe=classe_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)

    emploi_temps, created = EmploiTempsLycee.objects.get_or_create(
        classe=classe, annee_scolaire=annee
    )

    plages = PlageHoraireLycee.objects.all().order_by('ordre', 'heure_debut')
    jours = CreneauEmploiTempsLycee.JOURS

    creneaux_existants = {}
    for c in emploi_temps.creneaux.all():
        creneaux_existants[(c.jour, c.plage_id)] = c

    grille = []
    for plage in plages:
        ligne = {'plage': plage, 'cases': []}
        for jour_num, jour_nom in jours:
            creneau = creneaux_existants.get((jour_num, plage.pk))
            ligne['cases'].append({
                'jour': jour_num,
                'jour_nom': jour_nom,
                'creneau': creneau,
            })
        grille.append(ligne)

    matieres_classe = MatiereClasseLycee.objects.filter(
        classe=classe
    ).select_related('matiere').order_by('ordre_affichage', 'matiere__nom')

    matieres = [mc.matiere for mc in matieres_classe]

    if not matieres:
        matieres = list(MatiereLycee.objects.filter(active=True).order_by('nom'))

    annee_precedente = _trouver_annee_precedente_lycee(annee)
    emploi_precedent = None
    if annee_precedente:
        emploi_precedent = EmploiTempsLycee.objects.filter(
            classe=classe, annee_scolaire=annee_precedente
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
    return render(request, 'lycee/emploi_temps/gestion.html', context)


# =====================================================================
# 12.4 ENREGISTREMENT DE CRÉNEAU (AJAX)
# =====================================================================

@login_required
@require_POST
def emploi_temps_lycee_enregistrer_creneau(request):
    """Enregistre ou supprime un créneau du lycée via AJAX."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'error': 'Données invalides'})

    emploi_temps_id = data.get('emploi_temps_id')
    jour = data.get('jour')
    plage_id = data.get('plage_id')
    matiere_id = data.get('matiere_id')
    salle = (data.get('salle') or '').strip() or None

    if not emploi_temps_id or not jour or not plage_id:
        return JsonResponse({'success': False, 'error': 'Paramètres manquants'})

    try:
        emploi_temps = EmploiTempsLycee.objects.select_related('classe').get(
            id_emploi_temps=emploi_temps_id
        )
    except EmploiTempsLycee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Emploi du temps introuvable'})

    try:
        plage = PlageHoraireLycee.objects.get(id_plage=plage_id)
    except PlageHoraireLycee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Plage introuvable'})

    if plage.est_pause and matiere_id:
        return JsonResponse({
            'success': False,
            'error': "Impossible d'affecter une matière à une pause"
        })

    if not matiere_id:
        CreneauEmploiTempsLycee.objects.filter(
            emploi_temps=emploi_temps, jour=jour, plage=plage
        ).delete()
        return JsonResponse({
            'success': True,
            'action': 'deleted',
            'message': 'Créneau supprimé'
        })

    try:
        matiere = MatiereLycee.objects.get(id_matiere=matiere_id)
    except MatiereLycee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Matière introuvable'})

    creneau, created = CreneauEmploiTempsLycee.objects.update_or_create(
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
            'id': creneau.id_creneau,
            'matiere_nom': matiere.nom,
            'salle': salle or '',
        },
        'message': 'Créneau enregistré'
    })


# =====================================================================
# 12.5 RECONDUCTION EMPLOI DU TEMPS LYCÉE
# =====================================================================

@login_required
@require_POST
def emploi_temps_lycee_reconduire(request, classe_id, annee_scolaire):
    """Reconduit l'emploi du temps de l'année précédente."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        data = {}

    annee_precedente_id = data.get('annee_precedente_id')
    remplacer = data.get('remplacer', False)

    classe = get_object_or_404(ClasseLycee, id_classe=classe_id)
    annee_actuelle = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)

    if annee_precedente_id:
        annee_precedente = get_object_or_404(
            AnneeScolaire, idAnneeScolaire=annee_precedente_id
        )
    else:
        annee_precedente = _trouver_annee_precedente_lycee(annee_actuelle)

    if not annee_precedente:
        return JsonResponse({
            'success': False,
            'error': "Aucune année scolaire précédente trouvée."
        })

    emploi_source = EmploiTempsLycee.objects.filter(
        classe=classe, annee_scolaire=annee_precedente
    ).first()

    if not emploi_source:
        return JsonResponse({
            'success': False,
            'error': f"Aucun emploi du temps trouvé pour {classe.nom} "
                     f"en {annee_precedente.anneeScolaire}."
        })

    emploi_cible, created = EmploiTempsLycee.objects.get_or_create(
        classe=classe, annee_scolaire=annee_actuelle
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
        PlageHoraireLycee.objects.all().values_list('id_plage', flat=True)
    )

    creneaux_source = emploi_source.creneaux.all()
    nb_copies = 0
    nb_ignores = 0

    for creneau in creneaux_source:
        if creneau.plage_id not in plages_valides:
            nb_ignores += 1
            continue

        CreneauEmploiTempsLycee.objects.create(
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
        message += f" {nb_ignores} créneau(x) ignoré(s)."

    return JsonResponse({
        'success': True,
        'message': message,
        'nb_copies': nb_copies,
        'nb_ignores': nb_ignores,
    })


# =====================================================================
# 12.6 PDF EMPLOI DU TEMPS LYCÉE
# =====================================================================

@login_required
def emploi_temps_lycee_pdf(request, classe_id, annee_scolaire):
    """Export PDF de l'emploi du temps d'une classe du lycée."""
    from .lycee_services import generer_emploi_temps_lycee_pdf

    classe = get_object_or_404(ClasseLycee, id_classe=classe_id)
    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    ecole = EcoleInfo.get_solo()

    emploi_temps = EmploiTempsLycee.objects.filter(
        classe=classe, annee_scolaire=annee
    ).first()

    if not emploi_temps:
        messages.warning(
            request,
            "Aucun emploi du temps n'a été créé pour cette classe."
        )
        return redirect('lycee:emploi_temps_lycee_gestion',
                        classe_id=classe_id,
                        annee_scolaire=annee_scolaire)

    plages = PlageHoraireLycee.objects.all().order_by('ordre', 'heure_debut')
    jours = CreneauEmploiTempsLycee.JOURS

    creneaux_par_case = {}
    for c in emploi_temps.creneaux.all():
        creneaux_par_case[(c.jour, c.plage_id)] = c

    buffer = generer_emploi_temps_lycee_pdf(
        classe, annee_scolaire, ecole, plages, jours, creneaux_par_case
    )

    filename = f"emploi_temps_{classe.nom}_{annee_scolaire}.pdf"
    filename = filename.replace(' ', '_')

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def emploi_temps_lycee_tous_pdf(request, annee_scolaire):
    """Export PDF de tous les emplois du temps du lycée."""
    from .lycee_services import generer_emploi_temps_lycee_pdf
    from PyPDF2 import PdfMerger
    import tempfile

    annee = get_object_or_404(AnneeScolaire, anneeScolaire=annee_scolaire)
    ecole = EcoleInfo.get_solo()

    emplois = EmploiTempsLycee.objects.filter(
        annee_scolaire=annee
    ).select_related('classe').order_by('classe__niveau', 'classe__serie', 'classe__nom')

    if not emplois.exists():
        messages.warning(request, "Aucun emploi du temps pour cette année.")
        return redirect('lycee:emploi_temps_lycee_index')

    merger = PdfMerger()
    temp_files = []
    jours = CreneauEmploiTempsLycee.JOURS

    try:
        for emploi in emplois:
            plages = PlageHoraireLycee.objects.all().order_by('ordre', 'heure_debut')

            creneaux_par_case = {}
            for c in emploi.creneaux.all():
                creneaux_par_case[(c.jour, c.plage_id)] = c

            buffer = generer_emploi_temps_lycee_pdf(
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
            f'attachment; filename="emplois_temps_lycee_{annee_scolaire}.pdf"'
        )
        return response

    except Exception as e:
        messages.error(request, f"Erreur : {e}")
        return redirect('lycee:emploi_temps_lycee_index')


# =====================================================================
# 13. MATIÈRES PAR CLASSE DU LYCÉE
# =====================================================================

@login_required
def matiere_classe_lycee_list(request):
    """
    Liste des matières par classe du lycée.
    Groupées par classe, avec possibilité de filtrer par niveau et par année.
    """
    niveau = request.GET.get('niveau', '')
    classe_id = request.GET.get('classe', '')
    annee_id = request.GET.get('annee', '')

    # ✅ Si aucune année n'est sélectionnée, on prend la plus récente
    if not annee_id:
        annee_actuelle = AnneeScolaire.objects.order_by('-anneeScolaire').first()
        if annee_actuelle:
            annee_id = str(annee_actuelle.idAnneeScolaire)

    # ✅ 1. On récupère TOUTES les classes (filtrées par année, niveau, etc.)
    classes_qs = ClasseLycee.objects.all().order_by('niveau', 'serie', 'nom')
    if annee_id:
        classes_qs = classes_qs.filter(annee_scolaire_id=annee_id)
    if niveau:
        classes_qs = classes_qs.filter(niveau=niveau)
    if classe_id:
        classes_qs = classes_qs.filter(id_classe=classe_id)

    # ✅ 2. On récupère les matières associées pour ces classes
    if annee_id:
        # Puisque le Lycée gère déjà l'année via la classe, on n'a pas besoin de filtrer par annee_scolaire_id
        # dans MatiereClasseLycee (le lien est fait par la classe)
        matieres_classe_qs = MatiereClasseLycee.objects.filter(
            classe__in=classes_qs
        ).select_related('matiere').order_by('ordre_affichage', 'matiere__nom')
    else:
        matieres_classe_qs = MatiereClasseLycee.objects.none()

    # ✅ 3. On construit une LISTE de dictionnaires (plus robuste que le dict)
    liste_classes = []
    for classe in classes_qs:
        # Filtrer les matières pour cette classe
        matieres = [mc for mc in matieres_classe_qs if mc.classe_id == classe.id_classe]
        
        # Enrichir avec le coefficient (pour l'affichage)
        for mc in matieres:
            try:
                coef_obj = CoefficientLycee.objects.get(
                    matiere=mc.matiere,
                    niveau=classe.niveau,
                    serie=classe.serie,
                )
                mc.coefficient_affiche = coef_obj.coefficient
            except CoefficientLycee.DoesNotExist:
                mc.coefficient_affiche = None

        liste_classes.append({
            'classe': classe,
            'matieres': matieres,
            'nb_matieres': len(matieres),
        })

    # ✅ 4. Statistiques pour les cartes du haut
    nb_total = matieres_classe_qs.count()
    nb_10 = matieres_classe_qs.filter(classe__niveau='10').count()
    nb_11 = matieres_classe_qs.filter(classe__niveau='11').count()
    nb_12 = matieres_classe_qs.filter(classe__niveau='12').count()

    # ✅ 5. Années scolaires pour le filtre
    annees = AnneeScolaire.objects.all().order_by('-anneeScolaire')

    # ✅ 6. On garde la liste de toutes les classes pour le filtre
    toutes_classes = ClasseLycee.objects.all().order_by('niveau', 'serie', 'nom')
    if annee_id:
        toutes_classes = toutes_classes.filter(annee_scolaire_id=annee_id)

    context = {
        'liste_classes': liste_classes,   # ✅ Nouvelle variable (liste de dicts)
        'classes': classes_qs,            # ✅ Pour le filtre
        'toutes_classes': toutes_classes,
        'classe_id': classe_id,
        'niveau_filtre': niveau,
        'annee_filtre': annee_id,
        'annees': annees,
        'nb_total': nb_total,
        'nb_10': nb_10,
        'nb_11': nb_11,
        'nb_12': nb_12,
    }
    return render(request, 'lycee/matiere_classe/list.html', context)


class MatiereClasseLyceeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.add_matiere'
    raise_exception = True
    model = MatiereClasseLycee
    form_class = MatiereClasseLyceeForm
    template_name = 'lycee/matiere_classe/form.html'
    success_url = reverse_lazy('lycee:matiere_classe_lycee_list')

    def get_initial(self):
        initial = super().get_initial()
        classe_id = self.request.GET.get('classe')
        if classe_id:
            try:
                classe = ClasseLycee.objects.get(id_classe=classe_id)
                initial['classe'] = classe
            except ClasseLycee.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        messages.success(self.request, "Matière associée à la classe avec succès !")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.warning(
            "Formulaire invalide (MatiereClasseLycee) : %s",
            dict(form.errors)
        )
        return super().form_invalid(form)


class MatiereClasseLyceeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.change_matiere'
    raise_exception = True
    model = MatiereClasseLycee
    form_class = MatiereClasseLyceeForm
    template_name = 'lycee/matiere_classe/form.html'
    success_url = reverse_lazy('lycee:matiere_classe_lycee_list')

    def form_valid(self, form):
        messages.success(self.request, "Association mise à jour avec succès !")
        return super().form_valid(form)


class MatiereClasseLyceeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.delete_matiere'
    raise_exception = True
    model = MatiereClasseLycee
    template_name = 'lycee/matiere_classe/confirm_delete.html'
    success_url = reverse_lazy('lycee:matiere_classe_lycee_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Association supprimée avec succès !")
        return super().delete(request, *args, **kwargs)

# =====================================================================
# 14. PARAMÈTRES PARTAGÉS (Année scolaire + École)
# =====================================================================

# ---------------------------------------------------------------
# 14.1 ANNÉE SCOLAIRE
# ---------------------------------------------------------------

class AnneeLyceeListView(LoginRequiredMixin, ListView):
    """Liste des années scolaires (vue du lycée)."""
    model = AnneeScolaire
    template_name = 'lycee/parametres/annee_list.html'
    context_object_name = 'annees'

    def get_queryset(self):
        return AnneeScolaire.objects.all().order_by('-anneeScolaire')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Année en cours
        annee = AnneeScolaire.objects.order_by('-anneeScolaire').first()
        context['annee_encours'] = annee.anneeScolaire if annee else None
        return context


class AnneeLyceeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'ecole.add_anneescolaire'
    raise_exception = True
    model = AnneeScolaire
    form_class = AnneeScolaireForm
    template_name = 'lycee/parametres/annee_form.html'
    success_url = reverse_lazy('lycee:annee_list')

    def form_valid(self, form):
        messages.success(self.request, "Année scolaire créée avec succès !")
        return super().form_valid(form)


class AnneeLyceeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'ecole.change_anneescolaire'
    raise_exception = True
    model = AnneeScolaire
    form_class = AnneeScolaireForm
    template_name = 'lycee/parametres/annee_form.html'
    success_url = reverse_lazy('lycee:annee_list')

    def form_valid(self, form):
        messages.success(self.request, "Année scolaire mise à jour avec succès !")
        return super().form_valid(form)


class AnneeLyceeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'ecole.delete_anneescolaire'
    raise_exception = True
    model = AnneeScolaire
    template_name = 'lycee/parametres/annee_confirm_delete.html'
    success_url = reverse_lazy('lycee:annee_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Année scolaire supprimée avec succès !")
        return super().delete(request, *args, **kwargs)


# ---------------------------------------------------------------
# 14.2 PARAMÈTRES ÉCOLE
# ---------------------------------------------------------------

@login_required
@permission_required('ecole.change_ecoleinfo', raise_exception=True)
def parametres_ecole_lycee(request):
    """Paramètres de l'école (vue du lycée)."""
    ecole = EcoleInfo.get_solo()

    if request.method == 'POST':
        form = EcoleInfoForm(request.POST, request.FILES, instance=ecole)
        if form.is_valid():
            form.save()
            messages.success(request, "Paramètres de l'école mis à jour avec succès !")
            return redirect('lycee:parametres_ecole')
    else:
        form = EcoleInfoForm(instance=ecole)

    return render(request, 'lycee/parametres/ecole.html', {
        'form': form,
        'ecole': ecole,
    })

@login_required
@require_POST
@permission_required('ecole.add_classelycee', raise_exception=True)
def classe_lycee_dupliquer_annee(request, annee_source_id):
    """Duplique toutes les classes (et leurs matières) d'une année vers une autre."""
    annee_source = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_source_id)
    
    # On prend l'année la plus récente comme cible (ou l'année en cours)
    annee_cible = AnneeScolaire.objects.order_by('-anneeScolaire').first()
    
    if annee_source == annee_cible:
        messages.error(request, "L'année source et l'année cible sont identiques.")
        return redirect('lycee:classe_list')

    classes_source = ClasseLycee.objects.filter(annee_scolaire=annee_source)
    nb_classes_creees = 0
    nb_matieres_copiees = 0

    for c in classes_source:
        # 1. Créer la classe si elle n'existe pas déjà
        classe_cible, created = ClasseLycee.objects.get_or_create(
            nom=c.nom, 
            annee_scolaire=annee_cible,
            defaults={
                'niveau': c.niveau,
                'serie': c.serie,
                'frais_inscription': c.frais_inscription,
                'frais_scolarite': c.frais_scolarite,
            }
        )
        
        if created:
            nb_classes_creees += 1

        # 2. Copier les matières associées à cette classe
        matieres_source = MatiereClasseLycee.objects.filter(classe=c)
        for mc in matieres_source:
            _, mat_created = MatiereClasseLycee.objects.get_or_create(
                classe=classe_cible,
                matiere=mc.matiere,
                defaults={
                    'ordre_affichage': mc.ordre_affichage,
                    'obligatoire': mc.obligatoire,
                }
            )
            if mat_created:
                nb_matieres_copiees += 1

    messages.success(
        request, 
        f"✅ Copie terminée : {nb_classes_creees} classe(s) et {nb_matieres_copiees} association(s) de matières créées pour l'année {annee_cible.anneeScolaire}."
    )
    return redirect(f"{reverse('lycee:classe_list')}?annee={annee_cible.idAnneeScolaire}")

@login_required
@permission_required('ecole.add_matiere', raise_exception=True)
def matiere_classe_lycee_copier(request, classe_source_id):
    """Copie les matières d'une classe vers une autre classe du même niveau/série."""
    classe_source = get_object_or_404(ClasseLycee, id_classe=classe_source_id)
    
    if request.method == 'POST':
        classe_cible_id = request.POST.get('classe_cible')
        classe_cible = get_object_or_404(ClasseLycee, id_classe=classe_cible_id)

        if classe_source.id_classe == classe_cible.id_classe:
            messages.error(request, "La classe source et la classe cible sont identiques.")
            return redirect('lycee:matiere_classe_lycee_list')

        matieres_source = MatiereClasseLycee.objects.filter(classe=classe_source)
        
        nb_copiees = 0
        nb_ignorees = 0

        for mc in matieres_source:
            _, created = MatiereClasseLycee.objects.get_or_create(
                classe=classe_cible,
                matiere=mc.matiere,
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
            f"✅ Copie terminée : {nb_copiees} matière(s) copiée(s) de {classe_source.nom} vers {classe_cible.nom}. "
            f"({nb_ignorees} déjà existantes)."
        )
        return redirect('lycee:matiere_classe_lycee_list')

    # Si GET, on affiche un formulaire pour choisir la classe cible
    # On propose les classes du même niveau et de la même série
    classes_cibles = ClasseLycee.objects.filter(
        niveau=classe_source.niveau,
        serie=classe_source.serie
    ).exclude(id_classe=classe_source.id_classe).order_by('nom')

    context = {
        'classe_source': classe_source,
        'classes_cibles': classes_cibles,
    }
    return render(request, 'lycee/matiere_classe/copier.html', context)


from .lycee_services import generer_carte_lycee_pdf, generer_planche_cartes_lycee_pdf
from .utils.qr_code import generer_qr_code_base64

@login_required
def carte_scolaire_lycee_preview(request, inscription_id):
    """Prévisualisation HTML de la carte scolaire (Lycée)."""
    inscription = get_object_or_404(InscriptionLycee, id_inscription=inscription_id)
    eleve = inscription.eleve
    ecole = EcoleInfo.get_solo()

    texte_qr = f"{eleve.prenom} {eleve.nom.upper()} - {eleve.matricule}"
    qr_code_image = generer_qr_code_base64(texte_qr)
    
    couleur_principale = couleur_valide(request.GET.get('couleur'), '#6f42c1')
    fond_choisi = fond_valide(request.GET.get('fond'), 'fond_blanc.jpg')

    fonds_disponibles = [
            {'code': 'fond_blanc', 'nom': 'Fond blanc'},
            {'code': 'carte_scolaire1.jpg', 'nom': 'Fond 1'},
            {'code': 'carte_scolaire2.jpg', 'nom': 'Fond 2'},
            {'code': 'carte_scolaire3.jpg', 'nom': 'Fond 3'},
            {'code': 'carte_scolaire4.jpg', 'nom': 'Fond 4'},
        ]

    context = {
        'eleve': eleve,
        'inscription': inscription,
        'ecole': ecole,
        'qr_code_image': qr_code_image,
        'couleur_principale': couleur_principale,
        'fond_choisi': fond_choisi,
        'fonds_disponibles': fonds_disponibles,
    }
    return render(request, 'ecole/carte_scolaire/preview_lycee.html', context)


@login_required
def carte_scolaire_lycee_pdf(request, inscription_id):
    inscription = get_object_or_404(InscriptionLycee, id_inscription=inscription_id)
    eleve = inscription.eleve
    ecole = EcoleInfo.get_solo()

    texte_qr = f"{eleve.prenom} {eleve.nom.upper()} - {eleve.matricule}"
    qr_code_image = generer_qr_code_base64(texte_qr)

    couleur = couleur_valide(request.GET.get('couleur'), '#6f42c1')
    fond = fond_valide(request.GET.get('fond'), 'fond_blanc.jpg') # ✅ Récupérer le fond

    buffer = generer_carte_lycee_pdf(eleve, inscription, ecole, qr_code_image, couleur, fond)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="carte_lycee_{eleve.matricule}.pdf"'
    return response


@login_required
def carte_scolaire_lycee_classe_pdf(request, classe_id, annee_id):
    classe = get_object_or_404(ClasseLycee, id_classe=classe_id)
    annee = get_object_or_404(AnneeScolaire, idAnneeScolaire=annee_id)
    ecole = EcoleInfo.get_solo()

    inscriptions = InscriptionLycee.objects.filter(
        classe=classe, annee_scolaire=annee
    ).select_related('eleve').order_by('eleve__nom')

    if not inscriptions.exists():
        messages.warning(request, "Aucun élève inscrit dans cette classe.")
        return redirect('lycee:classe_list')

    couleur = couleur_valide(request.GET.get('couleur'), '#6f42c1')
    fond = fond_valide(request.GET.get('fond'), 'fond_blanc.jpg') # ✅ Récupérer le fond

    buffer = generer_planche_cartes_lycee_pdf(inscriptions, ecole, couleur, fond)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="cartes_lycee_{classe.nom}.pdf"'
    return response

# =====================================================================
# COMPTABILITÉ DU LYCÉE
# =====================================================================
import csv
from django.db.models import Sum, Count
from .models import CategorieDepense, Depense, CategorieRecette, Recette
from .forms import DepenseForm, RecetteForm


@login_required
@permission_required('ecole.voir_comptabilite', raise_exception=True)
def lycee_comptabilite_dashboard(request):
    """
    Tableau de bord comptable du lycée (indépendant du fondamental).

    Utilise le même service que le fondamental mais filtré sur la section
    « lycée » : paiements lycée + dépenses/recettes section lycée.
    """
    from .models import Section, EcoleInfo
    from .services.comptabilite import detail_financier, evolution_mensuelle

    annee_id = request.GET.get('annee')
    annees_scolaires = AnneeScolaire.objects.all().order_by('-anneeScolaire')
    if annee_id:
        annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
    else:
        annee_selectionnee = annees_scolaires.first()

    detail = detail_financier(annee_selectionnee, 'lycee')
    evolution = evolution_mensuelle(annee_selectionnee, 'lycee')

    context = {
        'annees_scolaires': annees_scolaires,
        'annee_selectionnee': annee_selectionnee,
        'annee_encours': annee_selectionnee.anneeScolaire if annee_selectionnee else None,

        'total_recettes': detail['total_recettes'],
        'recettes_frais': detail['recettes_frais'],
        'recettes_scolarite': detail['recettes_scolarite'],
        'recettes_autres': detail['recettes_autres'],
        'nb_recettes_autres': detail['nb_recettes_autres'],
        'total_depenses': detail['total_depenses'],
        'nb_depenses': detail['nb_depenses'],
        'nb_paiements': detail['nb_paiements'],
        'resultat': detail['resultat'],
        'resultat_positif': detail['resultat'] >= 0,
        'depenses_par_categorie': detail['depenses_par_categorie'],
        'recettes_par_categorie': detail['recettes_par_categorie'],
        'dernieres_depenses': detail['dernieres_depenses'],

        'evolution_mensuelle': evolution,
        'evolution_mensuelle_json': json.dumps(evolution),
        'depenses_categorie_json': json.dumps([
            {'label': d['categorie__nom'], 'value': float(d['total'])}
            for d in detail['depenses_par_categorie']
        ]),
        'recettes_categorie_json': json.dumps([]),
    }
    return render(request, 'lycee/comptabilite/dashboard.html', context)


@login_required
@permission_required('ecole.voir_comptabilite', raise_exception=True)
def lycee_depense_list(request):
    """Liste des dépenses (vue lycée)."""
    depenses = Depense.objects.select_related('categorie', 'anneeScolaire').all()

    categorie_id = request.GET.get('categorie', '')
    annee_id = request.GET.get('annee', '')
    search = request.GET.get('search', '').strip()
    section = request.GET.get('section', '')  # ✅ nouveau filtre

    if categorie_id:
        depenses = depenses.filter(categorie_id=categorie_id)
    if annee_id:
        depenses = depenses.filter(anneeScolaire_id=annee_id)
    if section:
        depenses = depenses.filter(section=section)
    if search:
        depenses = depenses.filter(
            Q(libelle__icontains=search) | Q(beneficiaire__icontains=search)
        )

    total = depenses.aggregate(Sum('montant'))['montant__sum'] or 0
    paginator = Paginator(depenses, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    from ..models import Section
    context = {
        'depenses': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'total': total,
        'categories': CategorieDepense.objects.filter(active=True).order_by('ordre_affichage'),
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'categorie_id': categorie_id,
        'annee_id': annee_id,
        'section': section,
        'search': search,
        'sections_choix': Section.choices,
    }
    return render(request, 'lycee/comptabilite/depense/list.html', context)


@login_required
@permission_required('ecole.voir_comptabilite', raise_exception=True)
def lycee_recette_list(request):
    """Liste des recettes hors paiements (vue lycée)."""
    recettes = Recette.objects.select_related('categorie', 'anneeScolaire').all()

    categorie_id = request.GET.get('categorie', '')
    annee_id = request.GET.get('annee', '')
    search = request.GET.get('search', '').strip()
    section = request.GET.get('section', '')  # ✅ nouveau filtre

    if categorie_id:
        recettes = recettes.filter(categorie_id=categorie_id)
    if annee_id:
        recettes = recettes.filter(anneeScolaire_id=annee_id)
    if section:
        recettes = recettes.filter(section=section)
    if search:
        recettes = recettes.filter(
            Q(libelle__icontains=search) | Q(source__icontains=search)
        )

    total = recettes.aggregate(Sum('montant'))['montant__sum'] or 0
    paginator = Paginator(recettes, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    from ..models import Section
    context = {
        'recettes': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'total': total,
        'categories': CategorieRecette.objects.filter(active=True).order_by('ordre_affichage'),
        'annees': AnneeScolaire.objects.all().order_by('-anneeScolaire'),
        'categorie_id': categorie_id,
        'annee_id': annee_id,
        'section': section,
        'search': search,
        'sections_choix': Section.choices,
    }
    return render(request, 'lycee/comptabilite/recette/list.html', context)

# =====================================================================
# COMPTABILITÉ DU LYCÉE — SOUS-CLASSES DES VUES GÉNÉRIQUES
# =====================================================================
# Ces sous-classes réutilisent les vues du fondamental (CRUD des dépenses
# et recettes) mais changent le template et l'URL de redirection pour
# pointer vers l'interface du lycée.

from .views import (
    DepenseCreateView as BaseDepenseCreateView,
    DepenseUpdateView as BaseDepenseUpdateView,
    DepenseDeleteView as BaseDepenseDeleteView,
    RecetteCreateView as BaseRecetteCreateView,
    RecetteUpdateView as BaseRecetteUpdateView,
    RecetteDeleteView as BaseRecetteDeleteView,
)


# -------------------- DÉPENSES --------------------

class DepenseCreateView(BaseDepenseCreateView):
    """Création d'une dépense (interface lycée)."""
    template_name = 'lycee/comptabilite/depense/form.html'
    success_url = reverse_lazy('lycee:depense_list')


class DepenseUpdateView(BaseDepenseUpdateView):
    """Modification d'une dépense (interface lycée)."""
    template_name = 'lycee/comptabilite/depense/form.html'
    success_url = reverse_lazy('lycee:depense_list')


class DepenseDeleteView(BaseDepenseDeleteView):
    """Suppression d'une dépense (interface lycée)."""
    template_name = 'lycee/comptabilite/depense/confirm_delete.html'
    success_url = reverse_lazy('lycee:depense_list')


# -------------------- RECETTES --------------------

class RecetteCreateView(BaseRecetteCreateView):
    """Création d'une recette (interface lycée)."""
    template_name = 'lycee/comptabilite/recette/form.html'
    success_url = reverse_lazy('lycee:recette_list')


class RecetteUpdateView(BaseRecetteUpdateView):
    """Modification d'une recette (interface lycée)."""
    template_name = 'lycee/comptabilite/recette/form.html'
    success_url = reverse_lazy('lycee:recette_list')


class RecetteDeleteView(BaseRecetteDeleteView):
    """Suppression d'une recette (interface lycée)."""
    template_name = 'lycee/comptabilite/recette/confirm_delete.html'
    success_url = reverse_lazy('lycee:recette_list')


# =====================================================================
# RAPPORTS COMPTABLES DU LYCÉE
# =====================================================================
import csv
from django.db.models import Sum, Count
from django.http import HttpResponse
from django.utils import timezone
from .models import EcoleInfo, CategorieDepense, Depense, CategorieRecette, Recette
from .lycee_models import PaiementLycee
from .utils.dates import get_mois_annee_scolaire, get_annee_reelle_mois


@login_required
@permission_required('ecole.voir_comptabilite', raise_exception=True)
def lycee_rapports_comptables(request):
    """
    Page des rapports comptables du lycée (vue HTML).
    Affiche synthèse, détail des paiements, répartition mensuelle.
    """
    annee_id = request.GET.get('annee')
    mois = request.GET.get('mois')

    annees_scolaires = AnneeScolaire.objects.all().order_by('-anneeScolaire')
    if annee_id:
        annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
    else:
        annee_selectionnee = annees_scolaires.first()

    # Mois de l'année scolaire
    mois_scolaires_liste = []
    if annee_selectionnee:
        mois_scolaires_liste = get_mois_annee_scolaire(annee_selectionnee)

    # Parse du mois
    mois_int = None
    annee_reelle_mois = None
    mois_label = None
    if mois and annee_selectionnee:
        try:
            mois_int = int(mois)
            if mois_int in range(1, 13):
                annee_reelle_mois = get_annee_reelle_mois(mois_int, annee_selectionnee)
                for num, nom, an, label in mois_scolaires_liste:
                    if num == mois_int:
                        mois_label = label
                        break
        except (ValueError, TypeError):
            mois_int = None

    # Filtres de base
    if annee_selectionnee:
        depenses_qs = Depense.objects.filter(anneeScolaire=annee_selectionnee)
        recettes_qs = Recette.objects.filter(anneeScolaire=annee_selectionnee)
        paiements_qs = PaiementLycee.objects.filter(
            inscription__annee_scolaire=annee_selectionnee
        )
    else:
        depenses_qs = Depense.objects.none()
        recettes_qs = Recette.objects.none()
        paiements_qs = PaiementLycee.objects.none()

    # Filtre mensuel
    if mois_int and annee_reelle_mois:
        depenses_qs = depenses_qs.filter(
            date_depense__month=mois_int, date_depense__year=annee_reelle_mois
        )
        recettes_qs = recettes_qs.filter(
            date_recette__month=mois_int, date_recette__year=annee_reelle_mois
        )
        paiements_qs = paiements_qs.filter(
            date_paiement__month=mois_int, date_paiement__year=annee_reelle_mois
        )

    # Calculs
    recettes_paiements = paiements_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    recettes_autres = recettes_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    total_recettes = recettes_paiements + recettes_autres

    total_depenses = depenses_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    resultat = total_recettes - total_depenses

    # Détail par catégorie
    depenses_par_categorie = list(
        depenses_qs.values('categorie__nom')
        .annotate(total=Sum('montant'), nb=Count('id'))
        .order_by('-total')
    )
    for item in depenses_par_categorie:
        item['pourcentage'] = round(
            float(item['total']) / float(total_depenses) * 100, 1
        ) if total_depenses > 0 else 0

    recettes_par_categorie = list(
        recettes_qs.values('categorie__nom')
        .annotate(total=Sum('montant'), nb=Count('id'))
        .order_by('-total')
    )

    # Détail des paiements élèves
    paiements_detail = []
    for p in paiements_qs.select_related(
        'inscription__eleve', 'inscription__classe'
    ).order_by('-date_paiement')[:100]:
        paiements_detail.append({
            'date': p.date_paiement,
            'eleve': str(p.inscription.eleve),
            'classe': p.inscription.classe.nom,
            'montant': p.montant,
            'est_inscription': p.est_inscription,
            'mois_scolaire': p.get_mois_display() if p.mois else None,
            'annee_paiement': p.annee_paiement,
            'observation': p.observation,
        })

    # Répartition mensuelle (12 mois)
    repartition_mensuelle = []
    if annee_selectionnee:
        for num_mois, nom_mois, annee_reelle, label in mois_scolaires_liste:
            pai_mois = PaiementLycee.objects.filter(
                inscription__annee_scolaire=annee_selectionnee,
                date_paiement__month=num_mois,
                date_paiement__year=annee_reelle,
            ).aggregate(Sum('montant'))['montant__sum'] or 0

            rec_mois = Recette.objects.filter(
                anneeScolaire=annee_selectionnee,
                date_recette__month=num_mois,
                date_recette__year=annee_reelle,
            ).aggregate(Sum('montant'))['montant__sum'] or 0

            dep_mois = Depense.objects.filter(
                anneeScolaire=annee_selectionnee,
                date_depense__month=num_mois,
                date_depense__year=annee_reelle,
            ).aggregate(Sum('montant'))['montant__sum'] or 0

            recettes_total_mois = float(pai_mois + rec_mois)
            depenses_total_mois = float(dep_mois)

            repartition_mensuelle.append({
                'mois': num_mois,
                'nom': nom_mois,
                'annee': annee_reelle,
                'label': label,
                'recettes_paiements': float(pai_mois),
                'recettes_autres': float(rec_mois),
                'recettes': recettes_total_mois,
                'depenses': depenses_total_mois,
                'solde': recettes_total_mois - depenses_total_mois,
            })

    context = {
        'annees_scolaires': annees_scolaires,
        'annee_selectionnee': annee_selectionnee,
        'mois_scolaires_liste': mois_scolaires_liste,
        'mois_selectionne': mois_int,
        'mois_label': mois_label,
        'recettes_paiements': recettes_paiements,
        'recettes_autres': recettes_autres,
        'total_recettes': total_recettes,
        'total_depenses': total_depenses,
        'depenses_par_categorie': depenses_par_categorie,
        'recettes_par_categorie': recettes_par_categorie,
        'resultat': resultat,
        'resultat_positif': resultat >= 0,
        'paiements_detail': paiements_detail,
        'repartition_mensuelle': repartition_mensuelle,
    }
    return render(request, 'lycee/comptabilite/rapports.html', context)


@login_required
@permission_required('ecole.voir_comptabilite', raise_exception=True)
def lycee_rapport_pdf(request):
    """Génère le rapport comptable PDF du lycée."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    annee_id = request.GET.get('annee')
    mois = request.GET.get('mois')

    if annee_id:
        annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
    else:
        annee_selectionnee = AnneeScolaire.objects.first()

    if not annee_selectionnee:
        messages.error(request, "Aucune année scolaire disponible.")
        return redirect('lycee:rapports_comptables')

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
        except (ValueError, TypeError):
            mois_int = None

    # Filtres
    depenses_qs = Depense.objects.filter(anneeScolaire=annee_selectionnee)
    recettes_qs = Recette.objects.filter(anneeScolaire=annee_selectionnee)
    paiements_qs = PaiementLycee.objects.filter(
        inscription__annee_scolaire=annee_selectionnee
    )

    if mois_int and annee_reelle_mois:
        depenses_qs = depenses_qs.filter(
            date_depense__month=mois_int, date_depense__year=annee_reelle_mois
        )
        recettes_qs = recettes_qs.filter(
            date_recette__month=mois_int, date_recette__year=annee_reelle_mois
        )
        paiements_qs = paiements_qs.filter(
            date_paiement__month=mois_int, date_paiement__year=annee_reelle_mois
        )

    # Calculs
    recettes_paiements = paiements_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    recettes_autres = recettes_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    total_recettes = recettes_paiements + recettes_autres
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

    # Génération du PDF
    response = HttpResponse(content_type='application/pdf')
    filename = f"rapport_comptable_lycee_{annee_selectionnee.anneeScolaire}"
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
    title_style = ParagraphStyle('Title', parent=styles['Heading1'],
                                 alignment=TA_CENTER, fontSize=16, spaceAfter=10)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Heading2'],
                                    alignment=TA_CENTER, fontSize=12, spaceAfter=20,
                                    textColor=colors.grey)
    section_style = ParagraphStyle('Section', parent=styles['Heading2'],
                                   fontSize=12, spaceAfter=10,
                                   textColor=colors.HexColor('#2c3e50'))

    story = []
    ecole = EcoleInfo.get_solo()
    story.append(Paragraph(f"<b>{ecole.nom}</b>", title_style))
    if ecole.ville:
        story.append(Paragraph(f"{ecole.ville}, {ecole.pays or 'Mali'}", subtitle_style))

    story.append(Paragraph("RAPPORT COMPTABLE — LYCÉE", title_style))
    periode = f"Année scolaire {annee_selectionnee.anneeScolaire}"
    if mois_label:
        periode += f" — {mois_label}"
    story.append(Paragraph(periode, subtitle_style))
    story.append(Spacer(1, 15))

    # Synthèse
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

    # Recettes
    story.append(Paragraph("2. DÉTAIL DES RECETTES", section_style))
    recettes_data = [
        ['Type', 'Montant (FCFA)'],
        ['Paiements des élèves (lycée)', f"{recettes_paiements:,.0f}"],
    ]
    if recettes_autres > 0:
        recettes_data.append(['Autres recettes', f"{recettes_autres:,.0f}"])
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

    # Dépenses par catégorie
    story.append(Paragraph("3. DÉPENSES PAR CATÉGORIE", section_style))
    if depenses_par_categorie:
        depenses_data = [['Catégorie', 'Nb', 'Montant (FCFA)', '%']]
        for item in depenses_par_categorie:
            pct = round(float(item['total']) / float(total_depenses) * 100, 1) \
                if total_depenses > 0 else 0
            depenses_data.append([
                item['categorie__nom'], str(item['nb']),
                f"{float(item['total']):,.0f}", f"{pct}%",
            ])
        depenses_data.append(['TOTAL', '', f"{total_depenses:,.0f}", '100%'])
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
        story.append(Paragraph("<i>Aucune dépense enregistrée.</i>", styles['Normal']))

    # Pied
    story.append(Spacer(1, 30))
    story.append(Paragraph(
        f"<i>Document généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}</i>",
        ParagraphStyle('Footer', parent=styles['Normal'],
                       alignment=TA_RIGHT, textColor=colors.grey, fontSize=9)
    ))

    doc.build(story)
    return response


@login_required
@permission_required('ecole.voir_comptabilite', raise_exception=True)
def lycee_rapport_csv(request):
    """Génère le rapport comptable CSV du lycée."""
    annee_id = request.GET.get('annee')
    mois = request.GET.get('mois')

    if annee_id:
        annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
    else:
        annee_selectionnee = AnneeScolaire.objects.first()

    if not annee_selectionnee:
        messages.error(request, "Aucune année scolaire disponible.")
        return redirect('lycee:rapports_comptables')

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
        except (ValueError, TypeError):
            mois_int = None

    # Filtres
    depenses_qs = Depense.objects.filter(anneeScolaire=annee_selectionnee)
    recettes_qs = Recette.objects.filter(anneeScolaire=annee_selectionnee)
    paiements_qs = PaiementLycee.objects.filter(
        inscription__annee_scolaire=annee_selectionnee
    )
    if mois_int and annee_reelle_mois:
        depenses_qs = depenses_qs.filter(
            date_depense__month=mois_int, date_depense__year=annee_reelle_mois
        )
        recettes_qs = recettes_qs.filter(
            date_recette__month=mois_int, date_recette__year=annee_reelle_mois
        )
        paiements_qs = paiements_qs.filter(
            date_paiement__month=mois_int, date_paiement__year=annee_reelle_mois
        )

    recettes_paiements = paiements_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    recettes_autres = recettes_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    total_recettes = recettes_paiements + recettes_autres
    total_depenses = depenses_qs.aggregate(Sum('montant'))['montant__sum'] or 0
    resultat = total_recettes - total_depenses

    # Réponse CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f"rapport_comptable_lycee_{annee_selectionnee.anneeScolaire}"
    if mois_int:
        filename += f"_{mois_int:02d}"
    filename += ".csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')  # BOM pour Excel

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['RAPPORT COMPTABLE — LYCÉE'])
    writer.writerow([f"Année scolaire : {annee_selectionnee.anneeScolaire}"])
    if mois_label:
        writer.writerow([f"Mois : {mois_label}"])
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
    writer.writerow(['Paiements élèves', f'{recettes_paiements:.0f}'])
    if recettes_autres > 0:
        writer.writerow(['Autres recettes', f'{recettes_autres:.0f}'])
    writer.writerow(['TOTAL', f'{total_recettes:.0f}'])
    writer.writerow([])

    # Détail paiements
    writer.writerow(['DÉTAIL DES PAIEMENTS'])
    writer.writerow(['Date', 'Élève', 'Classe', 'Type', 'Mois scolaire', 'Montant (FCFA)'])
    for p in paiements_qs.select_related(
        'inscription__eleve', 'inscription__classe'
    ).order_by('date_paiement'):
        type_paiement = "Inscription" if p.est_inscription else "Scolarité"
        mois_sco = p.get_mois_display() if p.mois else '—'
        writer.writerow([
            p.date_paiement.strftime('%d/%m/%Y'),
            str(p.inscription.eleve),
            p.inscription.classe.nom,
            type_paiement,
            mois_sco,
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
        pct = round(float(item['total']) / float(total_depenses) * 100, 1) \
            if total_depenses > 0 else 0
        writer.writerow([
            item['categorie__nom'], item['nb'],
            f"{float(item['total']):.0f}", f'{pct}%',
        ])
    writer.writerow(['TOTAL', '', f'{total_depenses:.0f}', '100%'])

    return response

# =====================================================================
# 13. RÉSULTATS SCOLAIRES — LYCÉE (bulletin élève + classement par période)
# =====================================================================
@login_required
@permission_required('ecole.view_note', raise_exception=True)
def resultats_lycee_index(request):
    """
    Vue unique des résultats du lycée.

    Fusionne le bulletin individuel d'élève et le classement par période
    dans un seul écran : on choisit une classe + une période, et on voit
    à la fois les bulletins des élèves et le classement de la classe.
    """
    annee_id = request.GET.get('annee')
    classe_id = request.GET.get('classe')
    trimestre = request.GET.get('trimestre')

    annees_scolaires = AnneeScolaire.objects.all().order_by('-anneeScolaire')
    annee_selectionnee = None
    if annee_id:
        annee_selectionnee = AnneeScolaire.objects.filter(idAnneeScolaire=annee_id).first()
    if not annee_selectionnee:
        annee_selectionnee = annees_scolaires.first()

    # Classes de l'année sélectionnée (pour le filtre)
    classes = ClasseLycee.objects.all()
    if annee_selectionnee:
        classes = classes.filter(annee_scolaire=annee_selectionnee)
    classes = classes.order_by('niveau', 'serie', 'nom')

    trimestres = [
        'Premier trimestre',
        'Deuxieme trimestre',
        'Troisieme trimestre',
    ]

    classe = None
    resultats = []
    stats = None
    classe_nom = None

    if classe_id:
        classe = ClasseLycee.objects.filter(id_classe=classe_id).first()
        if classe:
            classe_nom = str(classe)

    if classe and trimestre and annee_selectionnee:
        qs = ResultatTrimestreLycee.objects.filter(
            inscription__classe=classe,
            inscription__annee_scolaire=annee_selectionnee,
            trimestre=trimestre,
        ).select_related('inscription__eleve').order_by('rang', 'inscription__eleve__nom')
        resultats = list(qs)
        if resultats:
            stats = _stats_resultats(resultats)

    context = {
        'annees_scolaires': annees_scolaires,
        'annee_selectionnee': annee_selectionnee,
        'annee_encours': annee_selectionnee.anneeScolaire if annee_selectionnee else None,
        'classes': classes,
        'trimestres': trimestres,
        'classe_id': classe_id,
        'trimestre': trimestre,
        'classe_nom': classe_nom,
        'resultats': resultats,
        'stats': stats,
    }
    return render(request, 'lycee/resultats/index.html', context)
