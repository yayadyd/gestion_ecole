# ecole/fondamental_urls.py
from django.urls import path, re_path
from . import views

app_name = 'fondamental'

urlpatterns = [
    # Tableau de bord
    path('', views.dashboard, name='dashboard'),

    # Année scolaire
    path('annees/', views.AnneeScolaireListView.as_view(), name='annee_list'),
    path('annees/ajouter/', views.AnneeScolaireCreateView.as_view(), name='annee_create'),
    path('annees/<int:pk>/modifier/', views.AnneeScolaireUpdateView.as_view(), name='annee_update'),
    path('annees/<int:pk>/supprimer/', views.AnneeScolaireDeleteView.as_view(), name='annee_delete'),

    # Classes
    path('classes/', views.ClasseListView.as_view(), name='classe_list'),
    path('classes/ajouter/', views.ClasseCreateView.as_view(), name='classe_create'),
    path('classes/frais/', views.frais_classe_annee_edit, name='frais_classe_annee_edit'),
    path('classes/<int:pk>/modifier/', views.ClasseUpdateView.as_view(), name='classe_update'),
    path('classes/<int:pk>/supprimer/', views.ClasseDeleteView.as_view(), name='classe_delete'),
    path('classes/<int:classe_id>/<int:annee_id>/cartes-pdf/', views.carte_scolaire_classe_pdf, name='carte_scolaire_classe_pdf'),

    # =================================================================
    # ELEVE
    # =================================================================
    path('eleves/', views.EleveListView.as_view(), name='eleve_list'),
    path('eleves/ajouter/', views.EleveCreateView.as_view(), name='eleve_create'),
    path('eleves/<int:pk>/', views.EleveDetailView.as_view(), name='eleve_detail'),
    path('eleves/<int:pk>/modifier/', views.EleveUpdateView.as_view(), name='eleve_update'),
    path('eleves/<int:pk>/supprimer/', views.EleveDeleteView.as_view(), name='eleve_delete'),
    path('eleves/<int:pk>/matricule/', views.eleve_regenerer_matricule, name='eleve_regenerer_matricule'),
    path('eleves/liste-filtree/', views.eleve_list_filtered, name='eleve_list_filtered'),
    path('eleves/liste-filtree/pdf/', views.eleve_list_filtered_pdf, name='eleve_list_filtered_pdf'),
    path('eleves/resultats/', views.eleve_resultats, name='eleve_resultats'),
    path('eleves/<int:eleve_id>/statistiques/', views.statistiques_eleve, name='statistiques_eleve'),
    path('eleves/carte/<int:inscription_id>/preview/', views.carte_scolaire_preview, name='carte_scolaire_preview'),
    path('eleves/carte/<int:inscription_id>/pdf/', views.carte_scolaire_pdf, name='carte_scolaire_pdf'),

    # =================================================================
    # MATIERE
    # =================================================================
    path('matieres/', views.MatiereListView.as_view(), name='matiere_list'),
    path('matieres/ajouter/', views.MatiereCreateView.as_view(), name='matiere_create'),
    path('matieres/<int:pk>/modifier/', views.MatiereUpdateView.as_view(), name='matiere_update'),
    path('matieres/<int:pk>/supprimer/', views.MatiereDeleteView.as_view(), name='matiere_delete'),
    path('matieres-classes/copier/<int:annee_source_id>/', views.matiere_classe_copier_annee, name='matiere_classe_copier_annee'),

    # Matières par classe
    path('matieres-classes/', views.matiere_classe_list, name='matiere_classe_list'),
    path('matieres-classes/ajouter/', views.MatiereClasseCreateView.as_view(), name='matiere_classe_create'),
    path('matieres-classes/<int:pk>/modifier/', views.MatiereClasseUpdateView.as_view(), name='matiere_classe_update'),
    path('matieres-classes/<int:pk>/supprimer/', views.MatiereClasseDeleteView.as_view(), name='matiere_classe_delete'),
    path('matieres-classes/copier-pour-classe/<int:classe_id>/<int:annee_source_id>/', 
         views.matiere_classe_copier_pour_classe, 
         name='matiere_classe_copier_pour_classe'),    
    path(
        'matieres-classes/copier-depuis/<int:classe_cible_id>/',
        views.matiere_classe_copier_depuis_classe,
        name='matiere_classe_copier_depuis_classe'
    ),

    # =================================================================
    # INSCRIPTION
    # =================================================================
    path('inscriptions/', views.InscriptionListView.as_view(), name='inscription_list'),
    path('inscriptions/ajouter/', views.InscriptionCreateView.as_view(), name='inscription_create'),
    path('inscriptions/<int:pk>/modifier/', views.InscriptionUpdateView.as_view(), name='inscription_update'),
    path('inscriptions/<int:pk>/supprimer/', views.InscriptionDeleteView.as_view(), name='inscription_delete'),

    # =================================================================
    # PAIEMENT
    # =================================================================
    path('paiements/', views.PaiementListView, name='paiement_list'),
    path('paiements/ajouter/', views.PaiementCreateView.as_view(), name='paiement_create'),
    path('paiements/<int:pk>/modifier/', views.PaiementUpdateView.as_view(), name='paiement_update'),
    path('paiements/<int:pk>/supprimer/', views.PaiementDeleteView.as_view(), name='paiement_delete'),
    path('paiements/mois/<str:annee_scolaire>/<int:mois>/', views.paiements_par_mois_scolaire, name='paiements_par_mois_scolaire'),
    path('paiements/annee/<str:annee_scolaire>/', views.paiements_annee_scolaire, name='paiements_annee_scolaire'),
    path('paiements/eleve/<int:eleve_id>/<str:annee_scolaire>/', views.paiements_eleve_annee, name='paiement_eleve_annee'),
    path('paiements/suivi-par-classe/', views.suivi_paiements_par_classe, name='suivi_paiements_par_classe'),
    path('api/detail-paiements-mois/', views.api_detail_paiements_mois, name='api_detail_paiements_mois'),

    # =================================================================
    # EVALUATION & NOTES
    # =================================================================
    path('evaluations/', views.EvaluationListView.as_view(), name='evaluation_list'),
    path('evaluations/ajouter/', views.EvaluationCreateView.as_view(), name='evaluation_create'),
    path('evaluations/<int:pk>/modifier/', views.EvaluationUpdateView.as_view(), name='evaluation_update'),
    path('evaluations/<int:pk>/supprimer/', views.EvaluationDeleteView.as_view(), name='evaluation_delete'),

    path('notes/liste/', views.NoteListView.as_view(), name='note_list'),
    path('cycle2/notes/liste/', views.NoteListView.as_view(), name='cycle2_note_list'),
    path('notes/ajouter/', views.NoteCreateView.as_view(), name='note_create'),
    path('notes/<int:pk>/modifier/', views.NoteUpdateView.as_view(), name='note_update'),
    path('notes/<int:pk>/supprimer/', views.NoteDeleteView.as_view(), name='note_delete'),

    # =================================================================
    # 1er CYCLE
    # =================================================================
    path('cycle1/notes/saisie/', views.cycle1_saisie_notes, name='cycle1_saisie_notes'),
    path('cycle1/notes/enregistrer/', views.cycle1_enregistrer_notes, name='cycle1_enregistrer_notes'),
    path('cycle1/moyennes/<int:classe_id>/<str:annee_scolaire>/<int:mois>/', views.cycle1_calculer_moyennes, name='cycle1_calculer_moyennes'),
    path('cycle1/classer/<int:classe_id>/<str:annee_scolaire>/<int:mois>/', views.cycle1_classer_eleves, name='cycle1_classer_eleves'),
    path('cycle1/notes/', views.cycle1_notes_list, name='cycle1_notes_list'),
    path('cycle1/notes/<int:pk>/supprimer/', views.cycle1_supprimer_note, name='cycle1_supprimer_note'),

    path('cycle1/bulletins/', views.cycle1_bulletins_index, name='cycle1_bulletins_index'),
    path('cycle1/bulletins/classe/<int:classe_id>/<str:annee_scolaire>/<int:mois>/', views.cycle1_bulletin_classe, name='cycle1_bulletin_classe'),
    path('cycle1/bulletins/eleve/<int:eleve_id>/<str:annee_scolaire>/<int:mois>/', views.cycle1_bulletin_eleve, name='cycle1_bulletin_eleve'),
    path('cycle1/bulletins/eleve/<int:eleve_id>/<str:annee_scolaire>/<int:mois>/pdf/', views.cycle1_bulletin_eleve_pdf, name='cycle1_bulletin_eleve_pdf'),
    path('cycle1/bulletins/eleve/<int:eleve_id>/annees/', views.cycle1_bulletins_eleve_annee, name='cycle1_bulletins_eleve_annee'),
    path('cycle1/bulletins/classe/<int:classe_id>/<str:annee_scolaire>/<int:mois>/export-pdf/', views.cycle1_exporter_bulletins_pdf, name='cycle1_exporter_bulletins_pdf'),

    # =================================================================
    # 2e CYCLE
    # =================================================================
    path('cycle2/notes/saisie/', views.cycle2_saisie_notes, name='cycle2_saisie_notes'),
    path('cycle2/notes/enregistrer/', views.cycle2_enregistrer_notes, name='cycle2_enregistrer_notes'),
    path('cycle2/moyennes/<str:annee_scolaire>/<str:trimestre>/', views.cycle2_calculer_moyennes, name='cycle2_calculer_moyennes'),
    path('cycle2/classer/<str:annee_scolaire>/<str:trimestre>/', views.cycle2_classer_eleves, name='cycle2_classer_eleves'),

    path('cycle2/bulletins/', views.cycle2_bulletins_index, name='cycle2_bulletins_index'),
    path('cycle2/bulletins/classe/<str:annee_scolaire>/<str:trimestre>/', views.cycle2_bulletins_classe, name='cycle2_bulletins_classe'),
    path('cycle2/bulletins/classe/<str:annee_scolaire>/<str:trimestre>/<int:classe_id>/', views.cycle2_bulletins_classe, name='cycle2_bulletins_classe_filtre'),
    path('cycle2/bulletins/eleve/<int:eleve_id>/<str:annee_scolaire>/<str:trimestre>/', views.cycle2_bulletin_eleve, name='cycle2_bulletin_eleve'),
    path('cycle2/bulletins/eleve/<int:eleve_id>/annees/', views.cycle2_bulletins_eleve_annee, name='cycle2_bulletins_eleve_annee'),
    path('cycle2/bulletins/exporter/<str:annee_scolaire>/<str:trimestre>/pdf/', views.cycle2_exporter_bulletins_pdf, name='cycle2_exporter_bulletins_pdf'),
    path('cycle2/bulletins/eleve/<int:eleve_id>/<str:annee_scolaire>/<str:trimestre>/pdf/', views.cycle2_bulletin_eleve_pdf, name='cycle2_bulletin_eleve_pdf'),

    # =================================================================
    # DOSSIER SCOLAIRE & DOCUMENTS
    # =================================================================
    path('dossiers/', views.dossiers_scolaires_index, name='dossiers_scolaires_index'),
    path('dossier/eleve/<int:eleve_id>/', views.dossier_scolaire_eleve, name='dossier_scolaire_eleve'),

    path('certificats/frequentation/<int:eleve_id>/<str:annee_scolaire>/', views.certificat_frequentation, name='certificat_frequentation'),
    path('certificats/frequentation/<int:eleve_id>/<str:annee_scolaire>/pdf/', views.certificat_frequentation_pdf, name='certificat_frequentation_pdf'),

    path('proposition-passage/', views.proposition_passage_index, name='proposition_passage_index'),
    path('proposition-passage/<int:classe_id>/<str:annee_scolaire>/', views.proposition_passage, name='proposition_passage'),
    path('proposition-passage/<int:classe_id>/<str:annee_scolaire>/pdf/', views.proposition_passage_pdf, name='proposition_passage_pdf'),

    path('certificats/transfert/form/<int:eleve_id>/<str:annee_scolaire>/', views.certificat_transfert_form, name='certificat_transfert_form'),
    path('certificats/transfert/<int:certificat_id>/', views.certificat_transfert_preview, name='certificat_transfert_preview'),
    path('certificats/transfert/<int:certificat_id>/pdf/', views.certificat_transfert_pdf, name='certificat_transfert_pdf'),
    path('certificats/transfert/<int:certificat_id>/dossier-complet/pdf/', views.certificat_transfert_dossier_complet_pdf, name='certificat_transfert_dossier_complet_pdf'),

    path('fiche-suivi/<int:eleve_id>/', views.fiche_suivi_second_cycle_preview, name='fiche_suivi_second_cycle_preview'),
    path('fiche-suivi/<int:eleve_id>/pdf/', views.fiche_suivi_second_cycle_pdf, name='fiche_suivi_second_cycle_pdf'),

    # =================================================================
    # API (AJAX)
    # =================================================================
    path('api/eleves-par-classe/<int:classe_id>/', views.api_eleves_par_classe, name='api_eleves_par_classe'),
    path('api/notes-eleve/<int:eleve_id>/', views.api_notes_eleve, name='api_notes_eleve'),
    path('api/recherche-inscriptions/', views.api_recherche_inscriptions, name='api_recherche_inscriptions'),
    path('api/recherche-eleves/', views.api_recherche_eleves, name='api_recherche_eleves'),
    path('api/classe-info/', views.api_classe_info, name='api_classe_info'),
    path('api/stats-globales/', views.api_stats_globales, name='api_stats_globales'),
    path('api/matieres-par-classe/<int:classe_id>/', views.api_matieres_par_classe, name='api_matieres_par_classe'),
    path('bulletins/', views.bulletins_choix, name='bulletins_choix'),
    path('notes/', views.notes_choix, name='notes_choix'),

    # =================================================================
    # RÉSULTATS (compositions 1er cycle, trimestres 2e cycle et lycée)
    # =================================================================
    path('resultats/', views.resultats_index, name='resultats_index'),

    # =================================================================
    # COMPTABILITÉ
    # =================================================================
    path('comptabilite/depenses/', views.depense_list, name='depense_list'),
    path('comptabilite/depenses/ajouter/', views.DepenseCreateView.as_view(), name='depense_create'),
    path('comptabilite/depenses/<int:pk>/modifier/', views.DepenseUpdateView.as_view(), name='depense_update'),
    path('comptabilite/depenses/<int:pk>/supprimer/', views.DepenseDeleteView.as_view(), name='depense_delete'),

    path('comptabilite/', views.comptabilite_dashboard, name='comptabilite_dashboard'),

    path('comptabilite/recettes/', views.recette_list, name='recette_list'),
    path('comptabilite/recettes/ajouter/', views.RecetteCreateView.as_view(), name='recette_create'),
    path('comptabilite/recettes/<int:pk>/modifier/', views.RecetteUpdateView.as_view(), name='recette_update'),
    path('comptabilite/recettes/<int:pk>/supprimer/', views.RecetteDeleteView.as_view(), name='recette_delete'),

    path('comptabilite/rapports/', views.rapports_comptables, name='rapports_comptables'),
    path('comptabilite/rapports/pdf/', views.rapport_pdf, name='rapport_pdf'),
    path('comptabilite/rapports/csv/', views.rapport_csv, name='rapport_csv'),

    # =================================================================
    # EMPLOI DU TEMPS
    # =================================================================
    path('emploi-temps/plages/', views.plage_horaire_list, name='plage_horaire_list'),
    path('emploi-temps/plages/ajouter/', views.PlageHoraireCreateView.as_view(), name='plage_horaire_create'),
    path('emploi-temps/plages/<int:pk>/modifier/', views.PlageHoraireUpdateView.as_view(), name='plage_horaire_update'),
    path('emploi-temps/plages/<int:pk>/supprimer/', views.PlageHoraireDeleteView.as_view(), name='plage_horaire_delete'),

    path('emploi-temps/', views.emploi_temps_index, name='emploi_temps_index'),
    path('emploi-temps/classe/<int:classe_id>/<str:annee_scolaire>/', views.emploi_temps_gestion, name='emploi_temps_gestion'),
    path('emploi-temps/creneau/enregistrer/', views.emploi_temps_enregistrer_creneau, name='emploi_temps_enregistrer_creneau'),
    path('emploi-temps/classe/<int:classe_id>/<str:annee_scolaire>/reconduire/', views.emploi_temps_reconduire, name='emploi_temps_reconduire'),
    path('emploi-temps/classe/<int:classe_id>/<str:annee_scolaire>/pdf/', views.emploi_temps_pdf, name='emploi_temps_pdf'),
    path('emploi-temps/tous/<str:annee_scolaire>/pdf/', views.emploi_temps_tous_pdf, name='emploi_temps_tous_pdf'),
]