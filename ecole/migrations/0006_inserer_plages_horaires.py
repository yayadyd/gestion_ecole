# ecole/migrations/0006_inserer_plages_horaires.py
"""
Migration de données : insertion des plages horaires.

- 1er cycle : horaires du matin + après-midi (pause déjeuner entre les deux)
- 2e cycle  : horaires plus longs, journée continue avec pauses
"""
from django.db import migrations


# =====================================================================
# PLAGES HORAIRES — 1ER CYCLE
# =====================================================================
# (ordre, heure_debut, heure_fin, libelle, est_pause)
PLAGES_1ER_CYCLE = [
    # --- Matin ---
    (1, '08:00', '08:30', None, False),
    (2, '08:30', '09:00', None, False),
    (3, '09:00', '09:30', None, False),
    (4, '09:30', '10:00', None, False),
    (5, '10:00', '10:15', 'Récréation', True),
    (6, '10:15', '10:45', None, False),
    (7, '10:45', '11:15', None, False),
    (8, '11:15', '12:00', None, False),
    # --- Pause déjeuner ---
    (9, '12:00', '15:00', 'Pause déjeuner', True),
    # --- Après-midi ---
    (10, '15:00', '16:00', None, False),
    (11, '16:00', '17:00', None, False),
]


# =====================================================================
# PLAGES HORAIRES — 2E CYCLE
# =====================================================================
PLAGES_2E_CYCLE = [
    # --- Matin ---
    (1, '07:45', '08:45', None, False),
    (2, '08:45', '09:45', None, False),
    (3, '09:45', '10:00', 'Récréation', True),
    (4, '10:00', '11:00', None, False),
    (5, '11:00', '12:00', None, False),
    # --- Pause déjeuner ---
    (6, '12:00', '15:00', 'Pause déjeuner', True),
    # --- Après-midi ---
    (7, '15:00', '16:00', None, False),
    (8, '16:00', '17:00', None, False),
]


# =====================================================================
# FONCTION D'INSERTION
# =====================================================================
def inserer_plages(apps, schema_editor):
    """Insère les plages horaires pour les 2 cycles."""
    PlageHoraire = apps.get_model('ecole', 'PlageHoraire')

    stats = {'crees': 0, 'existants': 0}

    # --- 1er cycle ---
    print("\n  📅 Plages horaires 1er cycle :")
    for ordre, debut, fin, libelle, est_pause in PLAGES_1ER_CYCLE:
        _, created = PlageHoraire.objects.get_or_create(
            cycle='1er',
            heure_debut=debut,
            heure_fin=fin,
            defaults={
                'ordre': ordre,
                'libelle': libelle,
                'est_pause': est_pause,
            }
        )
        if created:
            stats['crees'] += 1
            label = f"{debut} - {fin}"
            if libelle:
                label += f" ({libelle})"
            print(f"    ✅ {label}")
        else:
            stats['existants'] += 1

    # --- 2e cycle ---
    print("\n  📅 Plages horaires 2e cycle :")
    for ordre, debut, fin, libelle, est_pause in PLAGES_2E_CYCLE:
        _, created = PlageHoraire.objects.get_or_create(
            cycle='2e',
            heure_debut=debut,
            heure_fin=fin,
            defaults={
                'ordre': ordre,
                'libelle': libelle,
                'est_pause': est_pause,
            }
        )
        if created:
            stats['crees'] += 1
            label = f"{debut} - {fin}"
            if libelle:
                label += f" ({libelle})"
            print(f"    ✅ {label}")
        else:
            stats['existants'] += 1

    print(f"\n  → {stats['crees']} plage(s) créée(s)")
    print(f"  → {stats['existants']} déjà existante(s)")


# =====================================================================
# FONCTION INVERSE
# =====================================================================
def supprimer_plages(apps, schema_editor):
    """Supprime les plages insérées."""
    PlageHoraire = apps.get_model('ecole', 'PlageHoraire')
    PlageHoraire.objects.all().delete()


# =====================================================================
# MIGRATION
# =====================================================================
class Migration(migrations.Migration):

    dependencies = [
        ('ecole', '0005_inserer_categories_comptables'),
    ]

    operations = [
        migrations.RunPython(inserer_plages, supprimer_plages),
    ]