# ecole/views_utilisateurs.py
"""
Gestion unifiée des utilisateurs (accessible depuis le Fondamental et le Lycée).
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group, Permission
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django import forms
import logging

logger = logging.getLogger(__name__)


# =====================================================================
# RÔLES PRÉDÉFINIS
# =====================================================================
ROLES_PREDEFINIS = {
    'directeur': {'label': 'Directeur', 'description': 'Accès complet', 'permissions': 'ALL'},
    'censeur': {
        'label': 'Censeur',
        'description': 'Notes, bulletins, emploi du temps',
        'permissions': [
            'view_note', 'add_note', 'change_note',
            'view_resultattrimestre', 'add_resultattrimestre',
            # ✅ FIX: les codenames « emploidutemps » n'existent pas ; le modèle
            # EmploiTemps génère « emploitemps ». Plages et créneaux ajoutés,
            # car les vues d'emploi du temps les exigent.
            'view_emploitemps', 'add_emploitemps', 'change_emploitemps',
            'view_creneauemploitemps', 'add_creneauemploitemps', 'change_creneauemploitemps',
            'view_plagehoraire', 'add_plagehoraire', 'change_plagehoraire', 'delete_plagehoraire',
            'view_classe', 'view_eleve',
        ],
    },
    'secretaire': {
        'label': 'Secrétaire',
        'description': 'Inscriptions, élèves, paiements',
        'permissions': [
            'add_eleve', 'change_eleve', 'view_eleve',
            'add_inscription', 'change_inscription', 'view_inscription',
            'add_paiement', 'change_paiement', 'view_paiement',
            # ✅ FIX: requis par la liste globale des paiements et le suivi
            'view_paiement_global',
        ],
    },
    'comptable': {
        'label': 'Comptable',
        'description': 'Gestion financière',
        'permissions': [
            'view_paiement', 'add_paiement', 'view_paiement_global',
            # ✅ FIX: les vues dépenses/recettes exigent gerer_depenses /
            # gerer_recettes, pas seulement add_depense / add_recette.
            'voir_comptabilite', 'gerer_depenses', 'gerer_recettes',
            'view_depense', 'add_depense', 'view_recette', 'add_recette',
        ],
    },
    'enseignant': {
        'label': 'Enseignant',
        'description': 'Saisie des notes',
        'permissions': ['add_note', 'change_note', 'view_note', 'view_eleve', 'view_classe'],
    },
    'lecteur': {
        'label': 'Lecteur',
        'description': 'Consultation seule',
        'permissions': ['view_eleve', 'view_note', 'view_paiement'],
    },
}

# =====================================================================
# FORMULAIRES
# =====================================================================
class UtilisateurCreateForm(forms.ModelForm):
    role = forms.ChoiceField(choices=[(k, v['label']) for k, v in ROLES_PREDEFINIS.items()], widget=forms.Select(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), min_length=8)
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label="Confirmer")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('password_confirm'):
            self.add_error('password_confirm', "Les mots de passe ne correspondent pas.")
        if cleaned.get('username') == 'systeme':
            self.add_error('username', "Ce nom est réservé.")
        return cleaned

class UtilisateurUpdateForm(forms.ModelForm):
    role = forms.ChoiceField(choices=[(k, v['label']) for k, v in ROLES_PREDEFINIS.items()], widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ResetPasswordForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), min_length=8)
    new_password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label="Confirmer")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('new_password') != cleaned.get('new_password_confirm'):
            self.add_error('new_password_confirm', "Les mots de passe ne correspondent pas.")
        return cleaned


# =====================================================================
# HELPERS
# =====================================================================
def est_administrateur(user):
    return user.is_superuser or user.groups.filter(name='directeur').exists()

def _get_role_principal(user):
    for role_key, role_data in ROLES_PREDEFINIS.items():
        if user.groups.filter(name=role_key).exists():
            return role_data['label']
    return "—"

def synchroniser_permissions_role(role_key):
    """
    Aligne les permissions du groupe sur la définition de ROLES_PREDEFINIS.

    ✅ FIX: auparavant les permissions n'étaient posées qu'à la création du
    groupe (« if not group.permissions.exists() ») : toute correction ou
    ajout de permission ne parvenait jamais aux groupes existants.

    Note : les permissions ajoutées à la main à un groupe prédéfini (via
    l'admin) sont remplacées à chaque synchronisation.
    """
    group, _ = Group.objects.get_or_create(name=role_key)
    perms = ROLES_PREDEFINIS[role_key]['permissions']

    # Limité à l'application « ecole » : évite les collisions de codename
    # avec d'autres applications et les permissions d'admin/auth.
    base = Permission.objects.filter(content_type__app_label='ecole')

    if perms == 'ALL':
        group.permissions.set(base)
    else:
        trouvees = base.filter(codename__in=perms)
        manquantes = set(perms) - set(trouvees.values_list('codename', flat=True))
        if manquantes:
            logger.warning(
                "Rôle '%s' : permissions introuvables (ignorées) : %s",
                role_key, ', '.join(sorted(manquantes)),
            )
        group.permissions.set(trouvees)
    return group


def synchroniser_tous_les_roles():
    """À appeler après une migration ou une mise à jour de l'application."""
    for role_key in ROLES_PREDEFINIS:
        synchroniser_permissions_role(role_key)


def _attribuer_role(user, role_key):
    user.groups.remove(*Group.objects.filter(name__in=ROLES_PREDEFINIS.keys()))
    group = synchroniser_permissions_role(role_key)
    user.groups.add(group)


# =====================================================================
# VUES
# =====================================================================
@login_required
def utilisateur_list(request):
    if not est_administrateur(request.user):
        messages.error(request, "Accès refusé.")
        return redirect('dashboard') # Redirige vers l'accueil par défaut

    search = request.GET.get('search', '').strip()
    utilisateurs = User.objects.exclude(username='systeme').exclude(pk=request.user.pk).order_by('username')
    
    if search:
        utilisateurs = utilisateurs.filter(Q(username__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search))

    for u in utilisateurs:
        u.role_principal = _get_role_principal(u)

    paginator = Paginator(utilisateurs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'core/utilisateurs/list.html', {
        'utilisateurs': page_obj, 'page_obj': page_obj, 'is_paginated': page_obj.has_other_pages(),
        'search': search, 'total': utilisateurs.count()
    })

@login_required
def utilisateur_create(request):
    if not est_administrateur(request.user): return redirect('dashboard')

    if request.method == 'POST':
        form = UtilisateurCreateForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.is_staff = False
            user.save()
            _attribuer_role(user, form.cleaned_data['role'])
            messages.success(request, f"Utilisateur '{user.username}' créé.")
            return redirect('core:utilisateur_list')
    else:
        form = UtilisateurCreateForm(initial={'is_active': True})

    return render(request, 'core/utilisateurs/form.html', {'form': form, 'titre': "Nouvel utilisateur"})

@login_required
def utilisateur_update(request, user_id):
    if not est_administrateur(request.user): return redirect('dashboard')
    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        form = UtilisateurUpdateForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save(commit=False)
            user.save()
            _attribuer_role(user, form.cleaned_data['role'])
            messages.success(request, "Utilisateur mis à jour.")
            return redirect('core:utilisateur_list')
    else:
        # Pré-remplir le rôle
        current_role = next((k for k in ROLES_PREDEFINIS if user.groups.filter(name=k).exists()), '')
        form = UtilisateurUpdateForm(instance=user, initial={'role': current_role})

    return render(request, 'core/utilisateurs/form.html', {'form': form, 'utilisateur': user, 'titre': f"Modifier {user.username}"})

@login_required
def utilisateur_delete(request, user_id):
    if not est_administrateur(request.user): return redirect('dashboard')
    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        user.delete()
        messages.success(request, "Utilisateur supprimé.")
        return redirect('core:utilisateur_list')

    return render(request, 'core/utilisateurs/confirm_delete.html', {'utilisateur': user})

@login_required
def utilisateur_reset_password(request, user_id):
    if not est_administrateur(request.user): return redirect('dashboard')
    user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password'])
            user.save()
            messages.success(request, "Mot de passe réinitialisé.")
            return redirect('core:utilisateur_list')
    else:
        form = ResetPasswordForm()

    return render(request, 'core/utilisateurs/reset_password.html', {'form': form, 'utilisateur': user})

@login_required
def utilisateur_toggle_active(request, user_id):
    if not est_administrateur(request.user) or request.method != 'POST':
        return JsonResponse({'success': False})
    
    user = get_object_or_404(User, pk=user_id)
    if user.username == 'systeme' or user.pk == request.user.pk:
        return JsonResponse({'success': False, 'error': 'Action non autorisée'})
        
    user.is_active = not user.is_active
    user.save()
    return JsonResponse({'success': True, 'is_active': user.is_active})