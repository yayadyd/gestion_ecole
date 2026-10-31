# ecole/migrations/0005_inserer_categories_comptables.py
"""
Migration de données : insertion des catégories de dépenses et de recettes.

- Catégories de dépenses : salaires, loyer, électricité, fournitures, etc.
- Catégories de recettes : subventions, dons, locations, etc.
"""
from django.db import migrations


# =====================================================================
# CATÉGORIES DE DÉPENSES
# =====================================================================
CATEGORIES_DEPENSES = [
    # (nom, description, ordre_affichage)
    ('Salaires', "Salaires et rémunérations du personnel enseignant et administratif", 1),
    ('Loyer', "Loyer des locaux de l'école", 2),
    ('Électricité', "Factures d'électricité (EDM, etc.)", 3),
    ('Eau', "Factures d'eau (SOMAGEP, etc.)", 4),
    ('Fournitures scolaires', "Craies, cahiers, stylos, manuels scolaires...", 5),
    ('Fournitures de bureau', "Papier, encre, agrafeuses, etc.", 6),
    ('Entretien et réparations', "Travaux d'entretien des locaux et équipements", 7),
    ('Carburant et transport', "Carburant des véhicules, déplacements", 8),
    ('Téléphone et Internet', "Factures de téléphone, forfaits Internet", 9),
    ('Frais bancaires', "Frais de tenue de compte, commissions", 10),
    ('Assurances', "Assurances (locaux, personnel, élèves)", 11),
    ('Formation du personnel', "Séminaires, formations, ateliers", 12),
    ('Frais de scolarité externes', "Frais payés à d'autres établissements", 13),
    ('Équipements', "Achat de matériel durable (mobilier, informatique...)", 14),
    ('Sécurité', "Gardiennage, surveillance", 15),
    ('Nettoyage', "Produits et services de nettoyage", 16),
    ('Frais administratifs', "Timbres, légalisations, démarches administratives", 17),
    ('Cérémonies et événements', "Fêtes scolaires, remises de prix, sorties", 18),
    ('Aide sociale', "Aides aux élèves défavorisés, bourses internes", 19),
    ('Impôts et taxes', "Impôts, patentes, taxes diverses", 20),
    ('Divers', "Autres dépenses non classées", 99),
]


# =====================================================================
# CATÉGORIES DE RECETTES
# =====================================================================
CATEGORIES_RECETTES = [
    # (nom, description, ordre_affichage)
    ('Subventions publiques', "Subventions de l'État, de la commune, du CAP...", 1),
    ('Subventions privées', "Subventions d'ONG, d'associations, de fondations", 2),
    ('Dons et legs', "Dons d'anciens élèves, de parents, de bienfaiteurs", 3),
    ('Location de locaux', "Location de salles, terrains, équipements", 4),
    ('Cotisations des associations', "Cotisations d'associations de parents d'élèves", 5),
    ('Vente de fournitures', "Revente de fournitures scolaires aux élèves", 6),
    ('Vente de productions', "Ventes de produits issus d'activités scolaires", 7),
    ('Prestations de services', "Services rendus à des tiers (formations, etc.)", 8),
    ('Revenus financiers', "Intérêts bancaires, placements", 9),
    ('Remboursements', "Remboursements d'avances, trop-perçus", 10),
    ('Frais de dossier', "Frais administratifs facturés aux familles", 11),
    ('Activités génératrices', "Recettes d'activités génératrices de revenus", 12),
    ('Cérémonies', "Recettes liées aux cérémonies (kermesses, etc.)", 13),
    ('Divers', "Autres recettes non classées", 99),
]


# =====================================================================
# FONCTION D'INSERTION
# =====================================================================
def inserer_categories(apps, schema_editor):
    """Insère les catégories de dépenses et de recettes."""
    CategorieDepense = apps.get_model('ecole', 'CategorieDepense')
    CategorieRecette = apps.get_model('ecole', 'CategorieRecette')

    stats = {
        'depenses_crees': 0, 'depenses_existants': 0,
        'recettes_crees': 0, 'recettes_existants': 0,
    }

    # --- Catégories de dépenses ---
    print("\n  📉 Catégories de dépenses :")
    for nom, description, ordre in CATEGORIES_DEPENSES:
        _, created = CategorieDepense.objects.get_or_create(
            nom=nom,
            defaults={
                'description': description,
                'ordre_affichage': ordre,
                'active': True,
            }
        )
        if created:
            stats['depenses_crees'] += 1
            print(f"    ✅ {nom}")
        else:
            stats['depenses_existants'] += 1

    # --- Catégories de recettes ---
    print("\n  📈 Catégories de recettes :")
    for nom, description, ordre in CATEGORIES_RECETTES:
        _, created = CategorieRecette.objects.get_or_create(
            nom=nom,
            defaults={
                'description': description,
                'ordre_affichage': ordre,
                'active': True,
            }
        )
        if created:
            stats['recettes_crees'] += 1
            print(f"    ✅ {nom}")
        else:
            stats['recettes_existants'] += 1

    print(f"\n  → {stats['depenses_crees']} catégorie(s) de dépense créée(s)")
    print(f"  → {stats['recettes_crees']} catégorie(s) de recette créée(s)")
    print(f"  → {stats['depenses_existants'] + stats['recettes_existants']} déjà existante(s)")


# =====================================================================
# FONCTION INVERSE
# =====================================================================
def supprimer_categories(apps, schema_editor):
    """Supprime les catégories insérées."""
    CategorieDepense = apps.get_model('ecole', 'CategorieDepense')
    CategorieRecette = apps.get_model('ecole', 'CategorieRecette')

    noms_depenses = [c[0] for c in CATEGORIES_DEPENSES]
    noms_recettes = [c[0] for c in CATEGORIES_RECETTES]

    CategorieDepense.objects.filter(nom__in=noms_depenses).delete()
    CategorieRecette.objects.filter(nom__in=noms_recettes).delete()


# =====================================================================
# MIGRATION
# =====================================================================
class Migration(migrations.Migration):

    dependencies = [
        ('ecole', '0004_associer_matieres_classes'),
    ]

    operations = [
        migrations.RunPython(inserer_categories, supprimer_categories),
    ]