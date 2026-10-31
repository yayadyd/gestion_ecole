# ecole/migrations/0023_inserer_plages_lycee.py
"""
Migration de données : insertion des plages horaires du lycée.

Réutilise les horaires du 2e cycle (journée continue avec pauses) pour le lycée.
"""
from django.db import migrations

# =====================================================================
# PLAGES HORAIRES — LYCÉE (basées sur le 2e cycle)
# =====================================================================
PLAGES_LYCEE = [
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


def inserer_plages_lycee(apps, schema_editor):
    """Insère les plages horaires du lycée."""
    PlageHoraireLycee = apps.get_model('ecole', 'PlageHoraireLycee')

    stats = {'crees': 0, 'existants': 0}

    print("\n  📅 Plages horaires Lycée :")
    for ordre, debut, fin, libelle, est_pause in PLAGES_LYCEE:
        _, created = PlageHoraireLycee.objects.get_or_create(
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


def supprimer_plages_lycee(apps, schema_editor):
    """Supprime les plages insérées."""
    PlageHoraireLycee = apps.get_model('ecole', 'PlageHoraireLycee')
    PlageHoraireLycee.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ecole', '0022_sections_comptables'),
    ]

    operations = [
        migrations.RunPython(inserer_plages_lycee, supprimer_plages_lycee),
    ]
