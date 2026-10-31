# ecole/migrations/0007_migration_transition.py
"""
Migration de transition : passage de l'ancien système (mensualite) 
au nouveau système (frais_scolarite + modes de paiement).

⚠️  Migration CRITIQUE pour les installations existantes.

Étapes :
1. Ajouter frais_scolarite à Classe
2. Copier mensualite × 9 → frais_scolarite
3. Supprimer mensualite
4. Ajouter les 3 champs de mode à EcoleInfo
5. Initialiser les modes par défaut
6. Renommer les classes : 1ère Année → 1ère Année A
7. Créer les classes B manquantes
8. Modifier les CHOICES de nomClasse
"""
from django.db import migrations, models


# =====================================================================
# CONFIGURATION DES CLASSES (nomenclature finale)
# =====================================================================


# =====================================================================
# ÉTAPE 1 : MIGRER LES FRAIS (mensualite × 9 → frais_scolarite)
# =====================================================================
def migrer_frais(apps, schema_editor):
    """Copie mensualite × 9 → frais_scolarite."""
    Classe = apps.get_model('ecole', 'Classe')

    for classe in Classe.objects.all():
        mensualite = getattr(classe, 'mensualite', 0) or 0
        classe.frais_scolarite = mensualite * 9
        classe.save(update_fields=['frais_scolarite'])

    print(f"  → {Classe.objects.count()} classe(s) : mensualite × 9 → frais_scolarite")


def reverse_migrer_frais(apps, schema_editor):
    """Inverse : frais_scolarite / 9 → mensualite."""
    Classe = apps.get_model('ecole', 'Classe')

    for classe in Classe.objects.all():
        frais = classe.frais_scolarite or 0
        classe.mensualite = frais // 9
        classe.save(update_fields=['mensualite'])


# =====================================================================
# ÉTAPE 2 : INITIALISER LES MODES DE L'ÉCOLE
# =====================================================================
def initialiser_modes(apps, schema_editor):
    """Initialise les modes de paiement de l'école."""
    EcoleInfo = apps.get_model('ecole', 'EcoleInfo')

    for ecole in EcoleInfo.objects.all():
        if not ecole.mode_frais_inscription:
            ecole.mode_frais_inscription = 'annuel'
        if not ecole.mode_frais_scolarite:
            ecole.mode_frais_scolarite = 'mensuel'
        if not ecole.nombre_tranches:
            ecole.nombre_tranches = 4
        ecole.save()
        print(f"  → École '{ecole.nom}' : "
              f"inscr={ecole.mode_frais_inscription}, "
              f"scol={ecole.mode_frais_scolarite}, "
              f"tranches={ecole.nombre_tranches}")


# =====================================================================
# MIGRATION
# =====================================================================
class Migration(migrations.Migration):

    dependencies = [
        ('ecole', '0006_inserer_plages_horaires'),
    ]

    operations = [
        # ============================================================
        # 1. Ajouter frais_scolarite (temporairement)
        # ============================================================
        migrations.AddField(
            model_name='classe',
            name='frais_scolarite',
            field=models.DecimalField(
                decimal_places=0, default=0, max_digits=12,
                help_text="Montant total de la scolarité pour l'année (en FCFA). "
                          "Sera divisé selon le mode de scolarité de l'école.",
                verbose_name='Frais de scolarité (annuel)',
            ),
        ),

        # ============================================================
        # 2. Migrer les données : mensualite × 9 → frais_scolarite
        # ============================================================
        migrations.RunPython(migrer_frais, reverse_migrer_frais),

        # ============================================================
        # 3. Supprimer mensualite
        # ============================================================
        migrations.RemoveField(
            model_name='classe',
            name='mensualite',
        ),

        # ============================================================
        # 4. Ajouter les 3 champs à EcoleInfo
        # ============================================================
        migrations.AddField(
            model_name='ecoleinfo',
            name='mode_frais_inscription',
            field=models.CharField(
                choices=[
                    ('unique', "Une seule fois (à la 1ère inscription)"),
                    ('annuel', "Chaque année (à chaque inscription)"),
                ],
                default='annuel',
                help_text="Comment sont payés les frais d'inscription",
                max_length=20,
                verbose_name="Mode des frais d'inscription",
            ),
        ),
        migrations.AddField(
            model_name='ecoleinfo',
            name='mode_frais_scolarite',
            field=models.CharField(
                choices=[
                    ('mensuel', "Mensuel (9 versements)"),
                    ('trimestriel', "Trimestriel (3 versements)"),
                    ('tranches', "Par tranches personnalisées"),
                    ('annuel', "Annuel (1 versement par an)"),
                    ('unique', "Unique (tout le cursus)"),
                ],
                default='mensuel',
                help_text="Comment sont payés les frais de scolarité",
                max_length=20,
                verbose_name="Mode des frais de scolarité",
            ),
        ),
        migrations.AddField(
            model_name='ecoleinfo',
            name='nombre_tranches',
            field=models.PositiveIntegerField(
                default=4,
                help_text="Utilisé uniquement si le mode est 'Par tranches' (2, 3, 4, 5...)",
                verbose_name='Nombre de tranches',
            ),
        ),

        # ============================================================
        # 5. Initialiser les modes
        # ============================================================
        migrations.RunPython(initialiser_modes, migrations.RunPython.noop),

        # ============================================================
        # 8. Mettre à jour l'ordering de Classe
        # ============================================================
        migrations.AlterModelOptions(
            name='classe',
            options={
                'ordering': ['cycle', 'nomClasse'],
                'verbose_name': 'Classe',
                'verbose_name_plural': 'Classes',
            },
        ),
    ]
