# ecole/lycee_admin.py
"""
Configuration Django Admin pour le Lycée.
Indépendant de l'admin des cycles 1er et 2e.

Contient :
- MatiereLyceeAdmin
- CoefficientLyceeAdmin
- ClasseLyceeAdmin
- EleveLyceeAdmin (matricule SAISI MANUELLEMENT)
- InscriptionLyceeAdmin
- NoteLyceeAdmin (avec calcul de moyenne)
- ResultatTrimestreLyceeAdmin
- DetailResultatLyceeAdmin
- PaiementLyceeAdmin
- PlageHoraireLyceeAdmin
- EmploiTempsLyceeAdmin
- CreneauEmploiTempsLyceeAdmin
- MatiereClasseLyceeAdmin
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count

from .lycee_models import (
    MatiereLycee, CoefficientLycee, ClasseLycee,
    EleveLycee, InscriptionLycee, NoteLycee,
    ResultatTrimestreLycee, DetailResultatLycee, PaiementLycee,
    PlageHoraireLycee, EmploiTempsLycee,
    CreneauEmploiTempsLycee, MatiereClasseLycee,
)


# =====================================================================
# 1. MATIÈRES DU LYCÉE
# =====================================================================
@admin.register(MatiereLycee)
class MatiereLyceeAdmin(admin.ModelAdmin):
    list_display = ('nom', 'nom_arabe', 'domaine', 'obligatoire', 'ordre_affichage', 'active', 'nb_coefficients')
    list_filter = ('domaine', 'obligatoire', 'active')
    search_fields = ('nom', 'nom_arabe')
    list_editable = ('ordre_affichage', 'active', 'obligatoire')
    ordering = ('ordre_affichage', 'nom')

    fieldsets = (
        ('Identification', {
            'fields': ('nom', 'nom_arabe', 'domaine')
        }),
        ('Configuration', {
            'fields': ('obligatoire', 'ordre_affichage', 'active')
        }),
    )

    def nb_coefficients(self, obj):
        """Nombre de coefficients associés à cette matière."""
        count = obj.coefficients.count()
        if count > 0:
            # ✅ FIX: lien admin simplifié et robuste
            url = (
                reverse('admin:ecole_coefficientlycee_changelist')
                + f'?matiere__id_matiere__exact={obj.pk}'
            )
            return format_html('<a href="{}">{} coefficient(s)</a>', url, count)
        return format_html('<span style="color: #e74c3c;">Aucun</span>')
    nb_coefficients.short_description = "Coefficients"


# =====================================================================
# 2. COEFFICIENTS
# =====================================================================
@admin.register(CoefficientLycee)
class CoefficientLyceeAdmin(admin.ModelAdmin):
    list_display = ('matiere', 'niveau', 'serie_affichee', 'coefficient')
    list_filter = ('niveau', 'serie', 'matiere__domaine')
    search_fields = ('matiere__nom',)
    list_editable = ('coefficient',)
    ordering = ('niveau', 'serie', 'matiere__ordre_affichage')

    fieldsets = (
        ('Matière et Niveau', {
            'fields': ('matiere', 'niveau', 'serie')
        }),
        ('Coefficient', {
            'fields': ('coefficient',),
            'description': "Le coefficient varie selon le niveau et la série. "
                           "En 10ème CG, laissez la série vide."
        }),
    )

    def serie_affichee(self, obj):
        if obj.serie:
            return obj.get_serie_display()
        return format_html('<em style="color: #7f8c8d;">Aucune (10ème CG)</em>')
    serie_affichee.short_description = "Série"


# =====================================================================
# 3. CLASSES DU LYCÉE
# =====================================================================
@admin.register(ClasseLycee)
class ClasseLyceeAdmin(admin.ModelAdmin):
    list_display = ('nom', 'niveau', 'serie_affichee', 'annee_scolaire', 'frais_inscription', 'frais_scolarite', 'nb_eleves')
    list_filter = ('niveau', 'serie', 'annee_scolaire')
    search_fields = ('nom',)
    list_editable = ('frais_inscription', 'frais_scolarite')
    ordering = ('niveau', 'serie', 'nom')

    fieldsets = (
        ('Identification', {
            'fields': ('nom', 'niveau', 'serie', 'annee_scolaire')
        }),
        ('Frais (FCFA)', {
            'fields': ('frais_inscription', 'frais_scolarite'),
            'description': "Le montant annuel de la scolarité sera divisé selon le mode "
                           "défini dans les paramètres de l'école."
        }),
    )

    def serie_affichee(self, obj):
        if obj.serie:
            return obj.get_serie_display()
        return format_html('<em style="color: #7f8c8d;">CG</em>')
    serie_affichee.short_description = "Série"

    def nb_eleves(self, obj):
        # ✅ FIX: utiliser l'API Django officielle (robuste au related_name)
        count = obj.inscriptionlycee_set.count()
        return format_html('<b>{}</b>', count)
    nb_eleves.short_description = "Élèves"


# =====================================================================
# 4. ÉLÈVES DU LYCÉE (MATRICULE SAISI)
# =====================================================================
@admin.register(EleveLycee)
class EleveLyceeAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'nom', 'prenom', 'sexe', 'date_naissance', 'get_age_display', 'contact_tuteur', 'statut')
    list_filter = ('sexe', 'statut')
    search_fields = ('matricule', 'nom', 'prenom')
    ordering = ('nom', 'prenom')
    readonly_fields = ('date_inscription',)

    fieldsets = (
        ('Identité', {
            'fields': ('matricule', 'prenom', 'nom', 'sexe', 'date_naissance', 'lieu_naissance', 'photo')
        }),
        ('Filiation', {
            'fields': ('pere', 'mere', 'contact_tuteur', 'adresse')
        }),
        ('Acte de naissance', {
            'fields': ('numero_acte_naissance', 'date_delivrance_acte')
        }),
        ('Provenance (DEF)', {
            'fields': ('ecole_provenance', 'annee_def'),
            'description': "Informations sur l'école où l'élève a obtenu son DEF."
        }),
        ('Statut', {
            'fields': ('statut',),
            'description': "Orienté = l'État paie les frais. Payant = les parents paient."
        }),
        ('Métadonnées', {
            'fields': ('date_inscription',),
            'classes': ('collapse',)
        }),
    )

    def get_age_display(self, obj):
        age = obj.get_age()
        return f"{age} ans"
    get_age_display.short_description = "Âge"

    def get_readonly_fields(self, request, obj=None):
        """Le matricule est en lecture seule en modification."""
        if obj:
            return self.readonly_fields + ('matricule',)
        return self.readonly_fields


# =====================================================================
# 5. INSCRIPTIONS
# =====================================================================
@admin.register(InscriptionLycee)
class InscriptionLyceeAdmin(admin.ModelAdmin):
    list_display = ('eleve', 'classe', 'annee_scolaire', 'date_inscription', 'frais_historique')
    list_filter = ('classe__niveau', 'classe__serie', 'annee_scolaire', 'frais_inscription_historique')
    search_fields = ('eleve__matricule', 'eleve__nom', 'eleve__prenom')
    date_hierarchy = 'date_inscription'
    autocomplete_fields = ('eleve',)

    fieldsets = (
        ('Inscription', {
            'fields': ('eleve', 'classe', 'annee_scolaire')
        }),
        ('Cas particulier', {
            'fields': ('frais_inscription_historique',),
            'description': "Cocher si les frais d'inscription ont été payés "
                           "AVANT l'utilisation de l'application."
        }),
    )

    def frais_historique(self, obj):
        if obj.frais_inscription_historique:
            return format_html(
                '<span style="background: #3498db; color: white; padding: 2px 6px; border-radius: 3px;">'
                'Payé avant l\'app</span>'
            )
        return '—'
    frais_historique.short_description = "Frais hist."


# =====================================================================
# 6. NOTES DU LYCÉE
# =====================================================================
@admin.register(NoteLycee)
class NoteLyceeAdmin(admin.ModelAdmin):
    list_display = ('inscription', 'matiere', 'trimestre', 'note_classe', 'note_composition', 'moyenne_affichee')
    list_filter = ('trimestre', 'matiere', 'inscription__classe__niveau', 'inscription__classe__serie')
    search_fields = ('inscription__eleve__matricule', 'inscription__eleve__nom', 'matiere__nom')
    list_editable = ('note_classe', 'note_composition')
    ordering = ('-trimestre', 'inscription__eleve__nom', 'matiere__ordre_affichage')

    fieldsets = (
        ('Élève et Matière', {
            'fields': ('inscription', 'matiere', 'trimestre')
        }),
        ('Notes', {
            'fields': ('note_classe', 'note_composition'),
            'description': "Moyenne matière = (Composition × 2 + Note de classe) / 3"
        }),
    )

    def moyenne_affichee(self, obj):
        moyenne = obj.moyenne_matiere
        if moyenne >= 16:
            couleur = '#27ae60'
        elif moyenne >= 12:
            couleur = '#3498db'
        elif moyenne >= 10:
            couleur = '#f39c12'
        else:
            couleur = '#e74c3c'
        return format_html('<b style="color: {};">{}</b>', couleur, moyenne)
    moyenne_affichee.short_description = "Moyenne"


# =====================================================================
# 7. RÉSULTATS TRIMESTRIELS
# =====================================================================
@admin.register(ResultatTrimestreLycee)
class ResultatTrimestreLyceeAdmin(admin.ModelAdmin):
    list_display = ('inscription', 'trimestre', 'moyenne_generale', 'rang', 'effectif_classe', 'date_calcul')
    list_filter = ('trimestre', 'inscription__classe__niveau', 'inscription__classe__serie')
    search_fields = ('inscription__eleve__matricule', 'inscription__eleve__nom')
    readonly_fields = ('date_calcul', 'total_coefficients', 'total_notes_coefficientees')
    ordering = ('-trimestre', 'rang')

    fieldsets = (
        ('Élève', {
            'fields': ('inscription', 'trimestre')
        }),
        ('Moyenne', {
            'fields': ('moyenne_generale', 'rang', 'effectif_classe', 'appreciation')
        }),
        ('Détails', {
            'fields': ('total_coefficients', 'total_notes_coefficientees'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('date_calcul',),
            'classes': ('collapse',)
        }),
    )


# =====================================================================
# 8. DÉTAILS DES RÉSULTATS
# =====================================================================
@admin.register(DetailResultatLycee)
class DetailResultatLyceeAdmin(admin.ModelAdmin):
    list_display = ('resultat', 'matiere', 'note_classe', 'note_composition', 'moyenne_matiere', 'coefficient', 'moyenne_coefficientee')
    list_filter = ('matiere', 'resultat__trimestre')
    search_fields = ('resultat__inscription__eleve__matricule', 'resultat__inscription__eleve__nom')
    ordering = ('resultat', 'matiere__ordre_affichage')
    readonly_fields = ('moyenne_matiere', 'moyenne_coefficientee')


# =====================================================================
# 9. PAIEMENT DU LYCÉE
# =====================================================================
@admin.register(PaiementLycee)
class PaiementLyceeAdmin(admin.ModelAdmin):
    list_display = (
        'date_paiement',
        'get_eleve',
        'get_classe',
        'montant',
        'type_affiche',
        'mois',
        'annee_paiement',
    )
    list_filter = (
        'est_inscription',
        'annee_paiement',
        'mois',
        'inscription__classe__niveau',
        'inscription__classe__serie',
    )
    search_fields = (
        'inscription__eleve__matricule',
        'inscription__eleve__nom',
        'inscription__eleve__prenom',
        'observation',
    )
    date_hierarchy = 'date_paiement'
    ordering = ('-date_paiement', '-id_paiement')
    autocomplete_fields = ('inscription',)

    fieldsets = (
        ('Inscription', {
            'fields': ('inscription',)
        }),
        ('Paiement', {
            'fields': ('montant', 'est_inscription', 'mois', 'annee_paiement')
        }),
        ('Notes', {
            'fields': ('observation',),
            'classes': ('collapse',)
        }),
    )

    def get_eleve(self, obj):
        return f"{obj.inscription.eleve.nom} {obj.inscription.eleve.prenom}"
    get_eleve.short_description = "Élève"

    def get_classe(self, obj):
        return obj.inscription.classe.nom
    get_classe.short_description = "Classe"

    def type_affiche(self, obj):
        if obj.est_inscription:
            return format_html(
                '<span style="background: #3498db; color: white; padding: 2px 6px; '
                'border-radius: 3px;">Inscription</span>'
            )
        return format_html(
            '<span style="background: #27ae60; color: white; padding: 2px 6px; '
            'border-radius: 3px;">Scolarité</span>'
        )
    type_affiche.short_description = "Type"


# =====================================================================
# 10. EMPLOI DU TEMPS DU LYCÉE
# =====================================================================
@admin.register(PlageHoraireLycee)
class PlageHoraireLyceeAdmin(admin.ModelAdmin):
    list_display = ('heure_debut', 'heure_fin', 'ordre', 'libelle', 'est_pause')
    list_editable = ('ordre', 'libelle', 'est_pause')
    list_display_links = ('heure_debut',)
    ordering = ('ordre', 'heure_debut')

    fieldsets = (
        ('Horaire', {
            'fields': ('heure_debut', 'heure_fin')
        }),
        ('Configuration', {
            'fields': ('ordre', 'libelle', 'est_pause')
        }),
    )


class CreneauLyceeInline(admin.TabularInline):
    model = CreneauEmploiTempsLycee
    extra = 0
    fields = ('jour', 'plage', 'matiere', 'salle', 'observation')
    ordering = ('jour', 'plage__ordre')


@admin.register(EmploiTempsLycee)
class EmploiTempsLyceeAdmin(admin.ModelAdmin):
    list_display = ('classe', 'annee_scolaire', 'nb_creneaux_remplis', 'date_modification')
    list_filter = ('annee_scolaire', 'classe__niveau', 'classe__serie')
    search_fields = ('classe__nom',)
    inlines = [CreneauLyceeInline]
    readonly_fields = ('date_creation', 'date_modification')

    fieldsets = (
        ('Emploi du temps', {
            'fields': ('classe', 'annee_scolaire', 'reconduit_depuis')
        }),
        ('Historique', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CreneauEmploiTempsLycee)
class CreneauEmploiTempsLyceeAdmin(admin.ModelAdmin):
    list_display = ('emploi_temps', 'jour', 'plage', 'matiere', 'salle')
    list_filter = ('jour', 'emploi_temps__annee_scolaire', 'emploi_temps__classe__niveau')
    search_fields = ('emploi_temps__classe__nom', 'matiere__nom')
    autocomplete_fields = ('matiere',)


# =====================================================================
# 11. MATIÈRES PAR CLASSE DU LYCÉE
# =====================================================================
@admin.register(MatiereClasseLycee)
class MatiereClasseLyceeAdmin(admin.ModelAdmin):
    list_display = ('classe', 'matiere', 'ordre_affichage', 'obligatoire')
    list_filter = ('classe__niveau', 'classe__serie', 'obligatoire')
    search_fields = ('classe__nom', 'matiere__nom')
    list_editable = ('ordre_affichage', 'obligatoire')
    ordering = ('classe__niveau', 'classe__nom', 'ordre_affichage')
    autocomplete_fields = ('classe', 'matiere')

    fieldsets = (
        ('Liaison', {
            'fields': ('classe', 'matiere')
        }),
        ('Configuration', {
            'fields': ('ordre_affichage', 'obligatoire')
        }),
    )