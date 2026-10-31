# ecole/migrations/0004_associer_matieres_classes.py
"""
Migration de données : association des matières aux classes.

- Chaque classe du 1er cycle a sa propre liste de matières
- Toutes les classes du 2e cycle (7ème A, 8ème A, 9ème A) ont les mêmes matières
"""
from django.db import migrations


# =====================================================================
# ASSOCIATIONS PAR CLASSE
# =====================================================================

# ✅ 1er cycle : chaque classe a ses propres matières
MATIERES_PAR_CLASSE_1ER = {
    '1ère Année A': [
        'Le saint coran',
        'Jurisprudence',
        'Théologie',
        'Hadiths',
        'Vie du prophète',
        'Éducation Civique',
        'Calcul',
        'Écriture',
        'Dessin',
        'Chant',
        'Lecture',
        'Histoire - Géographie',
        'Français',
    ],
    '2ème Année A': [
        'Coran',
        'Jurisprudence',
        'Théologie',
        'Hadith',
        'Langage',
        'Dictée',
        'Calcul',
        'Écriture',
        'Dessin',
        'Chant',
        'Lecture',
        'B. prophète psl',
        'Grammaire',
        'Conjugaison',
        'Français',
    ],
    '3ème Année A': [
        'Coran',
        'Jurisprudence',
        'Théologie',
        'Hadith',
        'Langage',
        'Dictée',
        'Calcul',
        'Écriture',
        'Dessin',
        'Chant',
        'Lecture',
        'B. prophète psl',
        'Grammaire',
        'Conjugaison',
        'Construction de Phrases',
        'Français',
    ],
    '4ème Année A': [
        'Coran',
        'Jurisprudence',
        'Théologie',
        'Hadith',
        'Langage',
        'Dictée',
        'Calcul',
        'Écriture',
        'Dessin',
        'Chant',
        'Lecture',
        'B. prophète psl',
        'Grammaire',
        'Conjugaison',
        'Construction de Phrases',
        'Français',
    ],
    '5ème Année A': [
        'Coran',
        'Jurisprudence',
        'Théologie',
        'Hadith',
        'Rédaction',
        'Dictée',
        'Calcul',
        'Géométrie',
        'Histoire',
        'Géographie',
        'Lecture',
        'B. prophète psl',
        'Grammaire',
        'Conjugaison',
        'Système métrique',
        'Bio',
        'Français',
    ],
    '6ème Année A': [
        'Rédaction',
        'Calcul',
        'Éducation Islamique',
        'Dictée - Question',
        'Question de Cours',
        'Lecture',
        'Coran',
        'Chant',
        'Écriture',
        'Français',
        'Conduite',
    ],
}

# ✅ 2e cycle : mêmes matières pour toutes les classes
MATIERES_2E_CYCLE = [
    'Rédaction',
    'Dictée - Question',
    'Mathématiques',
    'Physique - Chimie',
    'Français',
    'Anglais',
    'Sciences Naturelles',
    'Histoire - Géographie',
    'Éducation Civique',
    'Éducation Physique',
    'Éducation Islamique',
    'Dessin',
    'Lecture',
    'Conduite',
]

CLASSES_2E = ['7ème Année A', '8ème Année A', '9ème Année A']


# =====================================================================
# FONCTION D'ASSOCIATION
# =====================================================================
def associer_matieres(apps, schema_editor):
    """Associe les matières aux classes."""
    Matiere = apps.get_model('ecole', 'Matiere')
    Classe = apps.get_model('ecole', 'Classe')
    MatiereClasse = apps.get_model('ecole', 'MatiereClasse')

    stats = {'crees': 0, 'existants': 0, 'absentes': 0}

    # --- 1er cycle ---
    for nom_classe, liste_matieres in MATIERES_PAR_CLASSE_1ER.items():
        try:
            classe = Classe.objects.get(nomClasse=nom_classe)
        except Classe.DoesNotExist:
            print(f"  ⚠️  Classe '{nom_classe}' introuvable")
            continue

        for ordre, nom_matiere in enumerate(liste_matieres, start=1):
            try:
                matiere = Matiere.objects.get(
                    nomMatiere=nom_matiere, cycle='1er'
                )
            except Matiere.DoesNotExist:
                stats['absentes'] += 1
                print(f"  ⚠️  Matière '{nom_matiere}' absente du catalogue 1er cycle")
                continue

            _, created = MatiereClasse.objects.get_or_create(
                classe=classe,
                matiere=matiere,
                defaults={
                    'ordre_affichage': ordre,
                    'obligatoire': True,
                }
            )
            if created:
                stats['crees'] += 1
            else:
                stats['existants'] += 1

    # --- 2e cycle ---
    for nom_classe in CLASSES_2E:
        try:
            classe = Classe.objects.get(nomClasse=nom_classe)
        except Classe.DoesNotExist:
            print(f"  ⚠️  Classe '{nom_classe}' introuvable")
            continue

        for ordre, nom_matiere in enumerate(MATIERES_2E_CYCLE, start=1):
            try:
                matiere = Matiere.objects.get(
                    nomMatiere=nom_matiere, cycle='2e'
                )
            except Matiere.DoesNotExist:
                stats['absentes'] += 1
                print(f"  ⚠️  Matière '{nom_matiere}' absente du catalogue 2e cycle")
                continue

            _, created = MatiereClasse.objects.get_or_create(
                classe=classe,
                matiere=matiere,
                defaults={
                    'ordre_affichage': ordre,
                    'obligatoire': True,
                }
            )
            if created:
                stats['crees'] += 1
            else:
                stats['existants'] += 1

    print(f"  → {stats['crees']} association(s) créée(s)")
    print(f"  → {stats['existants']} déjà existante(s)")
    if stats['absentes']:
        print(f"  ⚠️  {stats['absentes']} matière(s) absente(s) du catalogue")


def supprimer_associations(apps, schema_editor):
    """Supprime toutes les associations."""
    MatiereClasse = apps.get_model('ecole', 'MatiereClasse')
    MatiereClasse.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ecole', '0003_inserer_matieres'),
    ]

    operations = [
        migrations.RunPython(associer_matieres, supprimer_associations),
    ]