# ecole/urls_utilisateurs.py
from django.urls import path
from . import views_utilisateurs

app_name = 'core'  # Un espace de noms pour éviter les conflits

urlpatterns = [
    path('', views_utilisateurs.utilisateur_list, name='utilisateur_list'),
    path('ajouter/', views_utilisateurs.utilisateur_create, name='utilisateur_create'),
    path('<int:user_id>/modifier/', views_utilisateurs.utilisateur_update, name='utilisateur_update'),
    path('<int:user_id>/supprimer/', views_utilisateurs.utilisateur_delete, name='utilisateur_delete'),
    path('<int:user_id>/mot-de-passe/', views_utilisateurs.utilisateur_reset_password, name='utilisateur_reset_password'),
    path('<int:user_id>/toggle-active/', views_utilisateurs.utilisateur_toggle_active, name='utilisateur_toggle_active'),
]