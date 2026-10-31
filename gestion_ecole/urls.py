# gestion_ecole/urls.py
import sys
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from ecole import views
from ecole import views_utilisateurs

# =====================================================================
# URLs COMMUNES (toujours actives)
# =====================================================================
urlpatterns = [
    # Setup & Admin
    path('setup/cle/', views.afficher_cle_setup_view, name='setup_cle'),
    path('setup/step1/', views.setup_step1, name='setup_step1'),
    path('setup/step2/', views.setup_step2, name='setup_step2'),
    path('setup/step3/', views.setup_step3, name='setup_step3'),
    path('admin/', admin.site.urls),

     # Authentification
    path('login/', views.CustomLoginView.as_view(
        template_name='core/registration/login.html'), name='login'),
    
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # ✅ Changement de mot de passe
    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='core/registration/password_change_form.html',success_url='/password-change/done/'), name='password_change'),
    
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='core/registration/password_change_done.html'), name='password_change_done'),

    # Gestion commune des utilisateurs
    path('utilisateurs/', include('ecole.urls_utilisateurs')),

    # Paramètres école (commun)
    path('parametres/ecole/', views.parametres_ecole, name='parametres_ecole'),
    path('ouvrir-dossier-donnees/', views.ouvrir_dossier_donnees, name='ouvrir_dossier_donnees'),

    # Licence
    path('licence/expiree/', views.licence_expiree, name='licence_expiree'),
    path('licence/machine-invalide/', views.licence_machine_invalide, name='licence_machine_invalide'),
    path('licence/activer/', views.licence_activer, name='licence_activer')
]

# =====================================================================
# URLs SPÉCIFIQUES AUX SECTIONS (conditionnelles)
# =====================================================================
if getattr(settings, 'ACTIVER_FONDAMENTAL', True):
    urlpatterns += [
        path('fondamental/', include('ecole.fondamental_urls')),
    ]

if getattr(settings, 'ACTIVER_LYCEE', True):
    urlpatterns += [
        path('lycee/', include('ecole.lycee_urls')),
    ]

# =====================================================================
# PAGE D'ACCUEIL (Racine /)
# =====================================================================
def accueil_redirect(request):
    if getattr(settings, 'ACTIVER_FONDAMENTAL', True):
        return redirect('fondamental:dashboard')
    elif getattr(settings, 'ACTIVER_LYCEE', True):
        return redirect('lycee:dashboard')
    else:
        return redirect('login')

urlpatterns += [
    path('', accueil_redirect, name='accueil'),
]

# Fichiers media
if settings.DEBUG or getattr(sys, 'frozen', False):
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [re_path(r'^media/(?P<path>.*)$', views.serve_media, name='serve_media')]

# =====================================================================
# GESTIONNAIRES D'ERREUR GLOBAUX (À METTRE TOUT EN BAS, HORS DES CROCHETS)
# =====================================================================
handler404 = 'ecole.views_erreurs.custom_404'
handler500 = 'ecole.views_erreurs.custom_500'
handler403 = 'ecole.views_erreurs.custom_403'