# ecole/migrations/0002_inserer_classes.py
"""
Migration de données : insertion initiale des classes.

- 1er cycle : 1ère à 6ème Année
- 2e cycle  : 7ème A, 8ème A, 9ème A
"""
from django.db import migrations


# =====================================================================
# CONFIGURATION DES CLASSES
# =====================================================================

CLASSES = [
    # (nom, cycle, frais_inscription, mensualite)
    # --- 1er cycle ---
    ('1ère Année A', '1er', 0, 0),
    ('2ème Année A', '1er', 0, 0),
    ('3ème Année A', '1er', 0, 0),
    ('4ème Année A', '1er', 0, 0),
    ('5ème Année A', '1er', 0, 0),
    ('6ème Année A', '1er', 0, 0),
    # --- 2e cycle ---
    ('7ème Année A', '2e', 0, 0),
    ('8ème Année A', '2e', 0, 0),
    ('9ème Année A', '2e', 0, 0),
]


# =====================================================================
# FONCTION D'INSERTION
# =====================================================================

def inserer_classes(apps, schema_editor):
    """Insère les 9 classes dans la base."""
    Classe = apps.get_model('ecole', 'Classe')

    stats = {'crees': 0, 'existants': 0}

    for nom, cycle, frais, mensualite in CLASSES:
        _, created = Classe.objects.get_or_create(
            nomClasse=nom,
            defaults={
                'cycle': cycle,
                'frais_inscription': frais,
                'mensualite': mensualite,
            }
        )
        if created:
            stats['crees'] += 1
            print(f"  ✅ Créée : {nom} ({cycle})")
        else:
            stats['existants'] += 1
            print(f"  ⚠️  Existe déjà : {nom}")

    print(f"\n  → {stats['crees']} classe(s) créée(s)")
    print(f"  → {stats['existants']} déjà existante(s)")


# =====================================================================
# FONCTION INVERSE
# =====================================================================

def supprimer_classes(apps, schema_editor):
    """Supprime les classes insérées."""
    Classe = apps.get_model('ecole', 'Classe')
    noms = [c[0] for c in CLASSES]
    Classe.objects.filter(nomClasse__in=noms).delete()


# =====================================================================
# MIGRATION
# =====================================================================

class Migration(migrations.Migration):

    dependencies = [
        ('ecole', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(inserer_classes, supprimer_classes),
    ]