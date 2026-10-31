from django.contrib import admin
from .models import CategorieDepense, Depense
from .models import PlageHoraire, EmploiTemps, CreneauEmploiTemps
from .models import Licence
from django.utils import timezone
from django.shortcuts import redirect

@admin.register(CategorieDepense)
class CategorieDepenseAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ordre_affichage', 'active')
    list_editable = ('ordre_affichage', 'active')
    search_fields = ('nom',)


@admin.register(Depense)
class DepenseAdmin(admin.ModelAdmin):
    list_display = ('date_depense', 'libelle', 'categorie', 'montant', 'mode_paiement', 'anneeScolaire')
    list_filter = ('categorie', 'mode_paiement', 'anneeScolaire', 'date_depense')
    search_fields = ('libelle', 'beneficiaire', 'numero_piece')
    date_hierarchy = 'date_depense'
    readonly_fields = ('date_saisie', 'saisi_par')

from .models import CategorieRecette, Recette


@admin.register(CategorieRecette)
class CategorieRecetteAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ordre_affichage', 'active')
    list_editable = ('ordre_affichage', 'active')
    search_fields = ('nom',)


@admin.register(Recette)
class RecetteAdmin(admin.ModelAdmin):
    list_display = ('date_recette', 'libelle', 'categorie', 'montant', 'mode_paiement', 'anneeScolaire')
    list_filter = ('categorie', 'mode_paiement', 'anneeScolaire', 'date_recette')
    search_fields = ('libelle', 'source', 'numero_piece')
    date_hierarchy = 'date_recette'
    readonly_fields = ('date_saisie', 'saisi_par')

@admin.register(PlageHoraire)
class PlageHoraireAdmin(admin.ModelAdmin):
    list_display = ('heure_debut', 'heure_fin', 'ordre', 'libelle', 'est_pause')
    list_editable = ('ordre', 'libelle', 'est_pause')
    list_display_links = ('heure_debut',)
    ordering = ('ordre', 'heure_debut')


class CreneauInline(admin.TabularInline):
    model = CreneauEmploiTemps
    extra = 0
    fields = ('jour', 'plage', 'matiere', 'salle', 'observation')
    ordering = ('jour', 'plage__ordre')


@admin.register(EmploiTemps)
class EmploiTempsAdmin(admin.ModelAdmin):
    list_display = ('classe', 'anneeScolaire', 'nb_creneaux_remplis', 'date_modification')
    list_filter = ('anneeScolaire', 'classe__cycle')
    search_fields = ('classe__nomClasse',)
    inlines = [CreneauInline]


@admin.register(CreneauEmploiTemps)
class CreneauEmploiTempsAdmin(admin.ModelAdmin):
    list_display = ('emploi_temps', 'jour', 'plage', 'matiere', 'salle')
    list_filter = ('jour', 'emploi_temps__anneeScolaire')
    search_fields = ('emploi_temps__classe__nomClasse',) 

from django.contrib import admin
from .models import EcoleInfo

@admin.register(EcoleInfo)
class EcoleInfoAdmin(admin.ModelAdmin):
    
    def has_module_permission(self, request):
        """✅ Seul le support voit la table EcoleInfo dans le menu."""
        return request.user.is_authenticated and request.user.is_superuser and request.user.username == 'systeme'

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        """✅ Seul le support peut modifier les paramètres de l'école."""
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False # L'école est créée automatiquement avec get_solo()

    def has_delete_permission(self, request, obj=None):
        return False # Interdire la suppression de l'école

    def changelist_view(self, request, extra_context=None):
        """✅ Redirige directement vers la fiche de modification (car il n'y a qu'une école)."""
        ecole = EcoleInfo.get_solo()
        return redirect(f'../ecoleinfo/{ecole.pk}/change/')

    fieldsets = (
        ('Identité', {
            'fields': ('nom', 'sigle', 'type_ecole')
        }),
        ('Modules actifs', {
            'fields': ('activer_fondamental', 'activer_lycee'),
            'description': "Décochez un module pour le désactiver pour cet établissement."
        }),
    )

####### Licence application #######
SUPPORT_USERNAME = 'systeme'


def _est_support(request):
    """Seul le compte support (caché au client) gère la licence."""
    u = request.user
    return u.is_authenticated and u.is_superuser and u.username == SUPPORT_USERNAME


@admin.register(Licence)
class LicenceAdmin(admin.ModelAdmin):
    list_display = (
    'cle_licence', 'mode', 'date_fin_essai',
    'empreinte_courte', 'nom_client', 'montant_paye'
)

    def empreinte_courte(self, obj):
        """Affiche les 8 premiers caractères de l'empreinte."""
        if obj.empreinte_machine:
            return f"{obj.empreinte_machine[:8].upper()}..."
        return "—"
    empreinte_courte.short_description = "Empreinte machine"
    list_filter = ('mode',)
    search_fields = ('cle_licence', 'nom_client', 'contact_client')

    readonly_fields = (
        'cle_licence',
        'date_debut_essai',
        'empreinte_machine',
        'date_creation',
        'date_modification',
    )

    fieldsets = (
        ('Identification', {
            'fields': ('cle_licence', 'mode', 'empreinte_machine')
        }),
        ("Période d'essai", {
            'fields': ('date_debut_essai', 'date_fin_essai')
        }),
        ('Licence payée', {
            'fields': ('date_paiement', 'montant_paye', 'nom_client', 'contact_client')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Historique', {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )

    # ============================================================
    # ACTIONS PERSONNALISÉES
    # ============================================================
    actions = [
        'activer_licence_payee',
        'marquer_comme_payee',
        'reinitialiser_empreinte_machine',
        'afficher_empreinte_machine',
        'prolonger_essai_7_jours',
        'prolonger_essai_30_jours',
    ]

    # ------------------------------------------------------------
    # 1. ACTIVER LA LICENCE APRÈS PAIEMENT
    # ------------------------------------------------------------
    @admin.action(description="🔓 Activer la licence (après paiement)")
    def activer_licence_payee(self, request, queryset):
        """Active la licence payée (mode → 'payee')."""
        count = 0
        for licence in queryset:
            licence.activer_licence(
                notes="Activée manuellement via l'admin"
            )
            count += 1

        self.message_user(
            request,
            f"✅ {count} licence(s) activée(s) avec succès. "
            f"L'accès est débloqué immédiatement."
        )

    # ------------------------------------------------------------
    # 2. MARQUER COMME PAYÉE (sans changer la date de paiement)
    # ------------------------------------------------------------
    @admin.action(description="💰 Marquer comme payée (récupération après panne)")
    def marquer_comme_payee(self, request, queryset):
        """
        Marque la licence comme payée sans réinitialiser la date.
        Utile en cas de réinstallation après panne.
        """
        from django.utils import timezone

        count = 0
        for licence in queryset:
            licence.mode = 'payee'
            if not licence.date_paiement:
                licence.date_paiement = timezone.now().date()
            licence.notes = (licence.notes or '') + (
                f"\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] "
                f"Marquée comme payée (récupération après panne)"
            )
            licence.save()
            count += 1

        self.message_user(
            request,
            f"💰 {count} licence(s) marquée(s) comme payée(s). "
            f"Toutes les données existantes sont préservées."
        )

        # ------------------------------------------------------------
    # 3. RÉINITIALISER L'EMPREINTE MACHINE
    # ------------------------------------------------------------
    @admin.action(description="🔧 Réinitialiser l'empreinte machine (nouvelle machine)")
    def reinitialiser_empreinte_machine(self, request, queryset):
        """
        Recalcule l'empreinte pour la machine actuelle.
        À utiliser lors d'un changement de machine ou d'une réinstallation.
        """
        from .utils.licence import get_machine_fingerprint
        from django.utils import timezone

        # ✅ FIX: calculer UNE SEULE FOIS avant la boucle
        nouvelle_empreinte = get_machine_fingerprint()
        count = 0

        for licence in queryset:
            ancienne = (licence.empreinte_machine or '')[:16] or "aucune"
            licence.empreinte_machine = nouvelle_empreinte
            licence.notes = (licence.notes or '') + (
                f"\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] "
                f"🔧 Empreinte réinitialisée (ancienne : {ancienne}...)"
            )
            licence.save()
            count += 1

        self.message_user(
            request,
            f"🔧 Empreinte réinitialisée pour {count} licence(s). "
            f"Nouvelle empreinte : {nouvelle_empreinte[:16]}... "
            f"L'application est maintenant débloquée sur cette machine."
        )

    # ------------------------------------------------------------
    # 4. AFFICHER L'EMPREINTE DE LA MACHINE ACTUELLE
    # ------------------------------------------------------------
    @admin.action(description="📋 Afficher l'empreinte de cette machine")
    def afficher_empreinte_machine(self, request, queryset):
        """
        Affiche l'empreinte de la machine actuelle dans un message.
        Utile pour transmettre l'info au fournisseur.
        """
        from .utils.licence import get_machine_fingerprint

        empreinte = get_machine_fingerprint()
        empreinte_courte = empreinte[:16].upper()

        self.message_user(
            request,
            f"📋 Empreinte de cette machine : {empreinte_courte}... "
            f"(complète : {empreinte})"
        )

    # ------------------------------------------------------------
    # 5. PROLONGER L'ESSAI DE 7 JOURS
    # ------------------------------------------------------------
    @admin.action(description="⏱️ Prolonger l'essai de 7 jours (dépannage)")
    def prolonger_essai_7_jours(self, request, queryset):
        """Prolonge l'essai de 7 jours pour les clients en difficulté."""
        from django.utils import timezone
        from datetime import timedelta

        count = 0
        for licence in queryset:
            if licence.mode == 'payee':
                continue

            # Repartir d'aujourd'hui si déjà expiré
            if licence.date_fin_essai < Licence.aujourdhui():
                licence.date_fin_essai = Licence.aujourdhui() + timedelta(days=7)
            else:
                licence.date_fin_essai = licence.date_fin_essai + timedelta(days=7)

            licence.notes = (licence.notes or '') + (
                f"\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] "
                f"⏱️ Essai prolongé de 7 jours"
            )
            licence.save()
            count += 1

        self.message_user(
            request,
            f"⏱️ Essai prolongé de 7 jours pour {count} licence(s)."
        )

    # ------------------------------------------------------------
    # 6. PROLONGER L'ESSAI DE 30 JOURS
    # ------------------------------------------------------------
    @admin.action(description="⏱️ Prolonger l'essai de 30 jours (dépannage)")
    def prolonger_essai_30_jours(self, request, queryset):
        """Prolonge l'essai de 30 jours."""
        from django.utils import timezone
        from datetime import timedelta

        count = 0
        for licence in queryset:
            if licence.mode == 'payee':
                continue

            if licence.date_fin_essai < Licence.aujourdhui():
                licence.date_fin_essai = Licence.aujourdhui() + timedelta(days=30)
            else:
                licence.date_fin_essai = licence.date_fin_essai + timedelta(days=30)

            licence.notes = (licence.notes or '') + (
                f"\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] "
                f"⏱️ Essai prolongé de 30 jours"
            )
            licence.save()
            count += 1

        self.message_user(
            request,
            f"⏱️ Essai prolongé de 30 jours pour {count} licence(s)."
        )

    # ------------------------------------------------------------
    # PERMISSIONS
    # ------------------------------------------------------------
    def has_module_permission(self, request):
        """✅ La licence n'apparaît dans l'admin que pour le compte support."""
        return _est_support(request)

    def has_view_permission(self, request, obj=None):
        return _est_support(request)

    def has_change_permission(self, request, obj=None):
        """✅ Un superuser du client ne peut plus s'activer lui-même la licence."""
        return _est_support(request)

    def has_add_permission(self, request):
        """Une seule licence, créée automatiquement."""
        return _est_support(request) and not Licence.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Empêcher la suppression de la licence."""
        return False

    def get_actions(self, request):
        """Les actions (activer, prolonger...) ne sont offertes qu'au support."""
        if not _est_support(request):
            return {}
        return super().get_actions(request)

# ============================================================
# MASQUER LE COMPTE SUPPORT DANS L'ADMIN
# ============================================================
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

# Désenregistrer le UserAdmin par défaut
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """UserAdmin personnalisé qui masque le compte support."""

    def get_queryset(self, request):
        """Exclure le compte support de la liste."""
        qs = super().get_queryset(request)
        return qs.exclude(username='systeme')

    def has_delete_permission(self, request, obj=None):
        """Empêcher la suppression du compte support."""
        if obj and obj.username == 'systeme':
            return False
        return super().has_delete_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        """Empêcher la modification du compte support."""
        if obj and obj.username == 'systeme':
            return False
        return super().has_change_permission(request, obj)

from .models import MatiereClasse


@admin.register(MatiereClasse)
class MatiereClasseAdmin(admin.ModelAdmin):
    list_display = ('classe', 'matiere', 'ordre_affichage', 'obligatoire')
    list_filter = ('classe', 'matiere__cycle', 'obligatoire')
    search_fields = ('classe__nomClasse', 'matiere__nomMatiere')
    list_editable = ('ordre_affichage', 'obligatoire')
    ordering = ('classe__nomClasse', 'ordre_affichage')

    fieldsets = (
        ('Liaison', {
            'fields': ('classe', 'matiere')
        }),
        ('Configuration', {
            'fields': ('ordre_affichage', 'obligatoire')
        }),
    )

# =====================================================================
# ✅ ADMIN DU LYCÉE (séparé)
# =====================================================================
from . import lycee_admin