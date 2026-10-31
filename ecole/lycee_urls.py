# ecole/lycee_urls.py
"""
URLs du Lycée - INDÉPENDANTES des cycles 1er et 2e.

Toutes les routes sont préfixées par /lycee/ dans urls.py principal.
Ex : /lycee/matieres/, /lycee/eleves/, /lycee/notes/saisie/, etc.
"""
from django.urls import path
from . import lycee_views as views

app_name = 'lycee'


urlpatterns = [
    # =================================================================
    # 1. TABLEAU DE BORD
    # =================================================================
    path('', views.dashboard_lycee, name='dashboard'),

    # =================================================================
    # 2. MATIÈRES DU LYCÉE
    # =================================================================
    path('matieres/', views.MatiereLyceeListView.as_view(), name='matiere_list'),
    path('matieres/ajouter/', views.MatiereLyceeCreateView.as_view(), name='matiere_create'),
    path('matieres/<int:pk>/modifier/', views.MatiereLyceeUpdateView.as_view(), name='matiere_update'),
    path('matieres/<int:pk>/supprimer/', views.MatiereLyceeDeleteView.as_view(), name='matiere_delete'),

    # =================================================================
    # 3. COEFFICIENTS
    # =================================================================
    path('coefficients/', views.coefficient_list, name='coefficient_list'),
    path('coefficients/ajouter/', views.CoefficientCreateView.as_view(), name='coefficient_create'),
    path('coefficients/<int:pk>/modifier/', views.CoefficientUpdateView.as_view(), name='coefficient_update'),
    path('coefficients/<int:pk>/supprimer/', views.CoefficientDeleteView.as_view(), name='coefficient_delete'),

    # =================================================================
    # 4. CLASSES DU LYCÉE
    # =================================================================
    path('classes/', views.ClasseLyceeListView.as_view(), name='classe_list'),
    path('classes/ajouter/', views.ClasseLyceeCreateView.as_view(), name='classe_create'),
    path('classes/dupliquer/<int:annee_source_id>/', views.classe_lycee_dupliquer_annee, name='classe_dupliquer'),
    path('classes/<int:pk>/modifier/', views.ClasseLyceeUpdateView.as_view(), name='classe_update'),
    path('classes/<int:pk>/supprimer/', views.ClasseLyceeDeleteView.as_view(), name='classe_delete'),

    # =================================================================
    # 5. ÉLÈVES DU LYCÉE
    # =================================================================
    path('eleves/', views.EleveLyceeListView.as_view(), name='eleve_list'),
    path('eleves/ajouter/', views.EleveLyceeCreateView.as_view(), name='eleve_create'),
    path('eleves/<int:pk>/', views.EleveLyceeDetailView.as_view(), name='eleve_detail'),
    path('eleves/<int:pk>/modifier/', views.EleveLyceeUpdateView.as_view(), name='eleve_update'),
    path('eleves/<int:pk>/supprimer/', views.EleveLyceeDeleteView.as_view(), name='eleve_delete'),

    # =================================================================
    # 13. LISTE FILTRÉE DES ÉLÈVES
    # =================================================================
    path('eleves/liste-filtree/', views.eleve_list_filtered_lycee, name='eleve_list_filtered'),
    path('eleves/liste-filtree/pdf/', views.eleve_list_filtered_pdf_lycee, name='eleve_list_filtered_pdf'),

    # =================================================================
    # 6. INSCRIPTIONS
    # =================================================================
    path('inscriptions/', views.InscriptionLyceeListView.as_view(), name='inscription_list'),
    path('inscriptions/ajouter/', views.InscriptionLyceeCreateView.as_view(), name='inscription_create'),
    path('inscriptions/<int:pk>/modifier/', views.InscriptionLyceeUpdateView.as_view(), name='inscription_update'),
    path('inscriptions/<int:pk>/supprimer/', views.InscriptionLyceeDeleteView.as_view(), name='inscription_delete'),

    # =================================================================
    # 7. SAISIE DES NOTES (PAR CLASSE)
    # =================================================================
    path('notes/saisie/', views.saisie_notes_par_classe, name='saisie_notes_par_classe'),
    path('notes/liste/', views.notes_list, name='notes_list'),

    # =================================================================
    # 8. CALCUL DES MOYENNES ET CLASSEMENT
    # =================================================================
    path(
        'moyennes/<int:classe_id>/<str:trimestre>/<int:annee_id>/',
        views.calculer_moyennes_trimestre,
        name='calculer_moyennes'
    ),
    path(
        'classer/<int:classe_id>/<str:trimestre>/<int:annee_id>/',
        views.classer_eleves_trimestre,
        name='classer_eleves'
    ),

    # =================================================================
    # 9. BULLETINS
    # =================================================================
    path('bulletins/', views.bulletins_index, name='bulletins_index'),
    path(
        'bulletins/classe/<int:classe_id>/<str:trimestre>/<int:annee_id>/',
        views.bulletins_classe,
        name='bulletins_classe'
    ),
    path(
        'bulletins/eleve/<int:inscription_id>/<str:trimestre>/',
        views.bulletin_eleve,
        name='bulletin_eleve'
    ),
    path('resultats/', views.resultats_lycee_index, name='resultats_lycee_index'),
    path(
        'bulletins/eleve/<int:inscription_id>/<str:trimestre>/pdf/',
        views.bulletin_eleve_pdf,
        name='bulletin_eleve_pdf'
    ),
    path(
    'bulletins/classe/<int:classe_id>/<str:trimestre>/<int:annee_id>/pdf/',
    views.bulletins_classe_pdf,
    name='bulletins_classe_pdf'
    ),

    # =================================================================
    # 10. APIs DE RECHERCHE
    # =================================================================
    path('api/recherche-eleves/', views.api_recherche_eleves_lycee, name='api_recherche_eleves'),
    path('api/recherche-inscriptions/', views.api_recherche_inscriptions_lycee, name='api_recherche_inscriptions'),
    path('api/classes-par-annee/<int:annee_id>/', views.api_classes_par_annee_lycee, name='api_classes_par_annee'),
    path('api/matieres-par-classe/<int:classe_id>/', views.api_matieres_par_classe_lycee, name='api_matieres_par_classe'),
    path('api/matieres-par-serie/', views.api_matieres_par_serie, name='api_matieres_par_serie'),
    path('api/notes-eleve/<int:eleve_id>/', views.api_notes_eleve_lycee, name='api_notes_eleve'),
    path('api/info-inscription/<int:inscription_id>/', views.api_info_inscription_lycee, name='api_info_inscription'),

    # =================================================================
    # 11. PAIEMENTS DU LYCÉE
    # =================================================================
    path('paiements/', views.paiement_lycee_list, name='paiement_list'),
    path('paiements/eleve/<int:inscription_id>/', views.paiement_lycee_detail, name='paiement_detail'),
    path('paiements/ajouter/', views.PaiementLyceeCreateView.as_view(), name='paiement_create'),
    path('paiements/<int:pk>/modifier/', views.PaiementLyceeUpdateView.as_view(), name='paiement_update'),
    path('paiements/<int:pk>/supprimer/', views.PaiementLyceeDeleteView.as_view(), name='paiement_delete'),

    # =================================================================
    # 12. EMPLOI DU TEMPS DU LYCÉE
    # =================================================================
    # 12.1 Plages horaires
    path('emploi-temps/plages/', views.plage_lycee_list, name='plage_lycee_list'),
    path('emploi-temps/plages/ajouter/', views.PlageLyceeCreateView.as_view(), name='plage_lycee_create'),
    path('emploi-temps/plages/<int:pk>/modifier/', views.PlageLyceeUpdateView.as_view(), name='plage_lycee_update'),
    path('emploi-temps/plages/<int:pk>/supprimer/', views.PlageLyceeDeleteView.as_view(), name='plage_lycee_delete'),
    # 12.2 Index
    path('emploi-temps/', views.emploi_temps_lycee_index, name='emploi_temps_lycee_index'),
    # 12.3 Gestion
    path('emploi-temps/classe/<int:classe_id>/<str:annee_scolaire>/', views.emploi_temps_lycee_gestion, name='emploi_temps_lycee_gestion'),
    # 12.4 Enregistrement AJAX
    path('emploi-temps/creneau/enregistrer/', views.emploi_temps_lycee_enregistrer_creneau, name='emploi_temps_lycee_enregistrer_creneau'),
    # 12.5 Reconduction
    path('emploi-temps/classe/<int:classe_id>/<str:annee_scolaire>/reconduire/', views.emploi_temps_lycee_reconduire, name='emploi_temps_lycee_reconduire'),
    # 12.6 PDF
    path('emploi-temps/classe/<int:classe_id>/<str:annee_scolaire>/pdf/', views.emploi_temps_lycee_pdf, name='emploi_temps_lycee_pdf'),
    path('emploi-temps/tous/<str:annee_scolaire>/pdf/', views.emploi_temps_lycee_tous_pdf, name='emploi_temps_lycee_tous_pdf'),

    # =================================================================
    # 13. MATIÈRES PAR CLASSE DU LYCÉE
    # =================================================================
    path('matieres-classes/', views.matiere_classe_lycee_list, name='matiere_classe_lycee_list'),
    path('matieres-classes/ajouter/', views.MatiereClasseLyceeCreateView.as_view(), name='matiere_classe_lycee_create'),
    path('matieres-classes/<int:pk>/modifier/', views.MatiereClasseLyceeUpdateView.as_view(), name='matiere_classe_lycee_update'),
    path('matieres-classes/<int:pk>/supprimer/', views.MatiereClasseLyceeDeleteView.as_view(), name='matiere_classe_lycee_delete'),
    path('matieres-classes/copier/<int:classe_source_id>/', views.matiere_classe_lycee_copier, name='matiere_classe_lycee_copier'),

    # API : matières par classe avec coefficients
    path('api/matieres-classe/<int:classe_id>/avec-coef/', views.api_matieres_par_classe_lycee_avec_coef, name='api_matieres_classe_avec_coef'),

    # =================================================================
    # 14. PARAMÈTRES PARTAGÉS
    # =================================================================
    # Année scolaire
    path('parametres/annees/', views.AnneeLyceeListView.as_view(), name='annee_list'),
    path('parametres/annees/ajouter/', views.AnneeLyceeCreateView.as_view(), name='annee_create'),
    path('parametres/annees/<int:pk>/modifier/', views.AnneeLyceeUpdateView.as_view(), name='annee_update'),
    path('parametres/annees/<int:pk>/supprimer/', views.AnneeLyceeDeleteView.as_view(), name='annee_delete'),

    # Paramètres école
    path('parametres/ecole/', views.parametres_ecole_lycee, name='parametres_ecole'),

    # Cartes scolaires
    path('inscriptions/<int:inscription_id>/carte/', views.carte_scolaire_lycee_preview, name='carte_lycee_preview'),
    path('inscriptions/<int:inscription_id>/carte/pdf/', views.carte_scolaire_lycee_pdf, name='carte_lycee_pdf'),
    path('classes/<int:classe_id>/<int:annee_id>/cartes-pdf/', views.carte_scolaire_lycee_classe_pdf, name='carte_lycee_classe_pdf'),

    # =================================================================
    # COMPTABILITÉ DU LYCÉE
    # =================================================================
    path('comptabilite/', views.lycee_comptabilite_dashboard, name='comptabilite_dashboard'),
    path('comptabilite/depenses/', views.lycee_depense_list, name='depense_list'),
    path('comptabilite/depenses/ajouter/', views.DepenseCreateView.as_view(), name='depense_create'),
    path('comptabilite/depenses/<int:pk>/modifier/', views.DepenseUpdateView.as_view(), name='depense_update'),
    path('comptabilite/depenses/<int:pk>/supprimer/', views.DepenseDeleteView.as_view(), name='depense_delete'),
    path('comptabilite/recettes/', views.lycee_recette_list, name='recette_list'),
    path('comptabilite/recettes/ajouter/', views.RecetteCreateView.as_view(), name='recette_create'),
    path('comptabilite/recettes/<int:pk>/modifier/', views.RecetteUpdateView.as_view(), name='recette_update'),
    path('comptabilite/recettes/<int:pk>/supprimer/', views.RecetteDeleteView.as_view(), name='recette_delete'),
    # Rapports comptables du lycée
    path('comptabilite/rapports/', views.lycee_rapports_comptables, name='rapports_comptables'),
    path('comptabilite/rapports/pdf/', views.lycee_rapport_pdf, name='rapport_pdf'),
    path('comptabilite/rapports/csv/', views.lycee_rapport_csv, name='rapport_csv'),
        
]