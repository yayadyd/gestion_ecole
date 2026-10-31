# ecole/migrations/0003_inserer_matieres.py
"""
Migration de données : insertion initiale des matières.

Liste unique de toutes les matières (extraites des bulletins).
Les associations aux classes se font dans la migration suivante.
"""
from django.db import migrations


# =====================================================================
# 1ER CYCLE — liste complète (union de toutes les matières du 1er cycle)
# =====================================================================
MATIERES_1ER_CYCLE = [
    # (nom, nom_arabe, coef)
    ('Saint coran',              'القرآن الكريم',           1),
    ('Jurisprudence',               'الفقه',                   1),
    ('Théologie',                   'التوحيد',                 1),
    ('Hadiths',                     'الحديث',                  1),
    ('Vie du prophète',             'السيرة',                  1),
    ('B. prophète psl',             'السيرة',                  1),
    ('Éducation Civique',           'التربية المدنية',         1),
    ('Éducation Islamique',         'التربية الإسلامية',       1),
    ('Langage',                     'المحادثة',                1),
    ('Dictée',                      'الإملاء',                 1),
    ('Dictée-Questions',           'الإملاء والأسئلة',        1),
    ('Question de Cours',           'الأسئلة حول الدروس',      1),
    ('Rédaction',                   'الإنشاء',                 1),
    ('Calcul',                      'الحساب',                  1),
    ('Géométrie',                   'الهندسة',                 1),
    ('Système métrique',            'النظام المتري',           1),
    ('Bio',                         'العلوم',                  1),
    ('Écriture',                    'الخط',                    1),
    ('Dessin',                      'الرسم',                   1),
    ('Chant',                       'النشيد',                  1),
    ('Lecture',                     'القراءة',                 1),
    ('Grammaire',                   'النحو',                   1),
    ('Conjugaison',                 'الصرف',                   1),
    ('Construction de Phrases',     'التركيب الجمل',           1),
    ('Histoire',                    'التاريخ',                 1),
    ('Géographie',                  'الجغرافيا',               1),
    ('Histoire-Géographie',       'التاريخ والجغرافيا',      1),
    ('Français',                    'الفرنسية',                1),
    ('Conduite',                    'السلوك',                  1),
]


# =====================================================================
# 2E CYCLE — liste commune (7ème A, 8ème A, 9ème A)
# =====================================================================
MATIERES_2E_CYCLE = [
    # (nom, nom_arabe, coef, tendance)
    ('Rédaction',              'الإنشاء',              3, 'litteraire'),
    ('Dictée-Questions',      'الإملاء والأسئلة',     2, 'litteraire'),
    ('Mathématiques',          'الحساب',               3, 'scientifique'),
    ('Physique-Chimie',      'الفيزياء والكيمياء',   3, 'scientifique'),
    ('Français',               'الفرنسية',             2, 'litteraire'),
    ('Anglais',                'الإنجليزية',           2, 'litteraire'),
    ('Sciences Naturelles',    'علوم الأحياء',         2, 'scientifique'),
    ('Histoire - Géographie',  'التاريخ والجغرافيا',   2, 'litteraire'),
    ('Éducation Civique',      'التربية المدنية',      1, 'litteraire'),
    ('Éducation Physique',     'التربية البدنية',      1, None),
    ('Éducation Islamique',    'التربية الإسلامية',    2, None),
    ('Dessin',                 'الرسم',                1, None),
    ('Lecture',                'القراءة',              1, None),
    ('Conduite',               'السلوك',               1, None),
]


# =====================================================================
# FONCTION D'INSERTION
# =====================================================================
def inserer_matieres(apps, schema_editor):
    """Insère les matières dans le catalogue."""
    Matiere = apps.get_model('ecole', 'Matiere')

    stats = {'crees': 0, 'existants': 0}

    # --- 1er cycle ---
    for nom, nom_arabe, coef in MATIERES_1ER_CYCLE:
        _, created = Matiere.objects.get_or_create(
            nomMatiere=nom,
            cycle='1er',
            defaults={
                'nomArabe': nom_arabe,
                'coef': coef,
                'tendance': None,
            }
        )
        if created:
            stats['crees'] += 1
        else:
            stats['existants'] += 1

    # --- 2e cycle ---
    for nom, nom_arabe, coef, tendance in MATIERES_2E_CYCLE:
        _, created = Matiere.objects.get_or_create(
            nomMatiere=nom,
            cycle='2e',
            defaults={
                'nomArabe': nom_arabe,
                'coef': coef,
                'tendance': tendance,
            }
        )
        if created:
            stats['crees'] += 1
        else:
            stats['existants'] += 1

    print(f"  → {stats['crees']} matière(s) créée(s)")
    print(f"  → {stats['existants']} déjà existante(s)")


def supprimer_matieres(apps, schema_editor):
    """Supprime les matières insérées."""
    Matiere = apps.get_model('ecole', 'Matiere')

    noms_1er = [m[0] for m in MATIERES_1ER_CYCLE]
    noms_2e = [m[0] for m in MATIERES_2E_CYCLE]

    Matiere.objects.filter(nomMatiere__in=noms_1er, cycle='1er').delete()
    Matiere.objects.filter(nomMatiere__in=noms_2e, cycle='2e').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ecole', '0002_inserer_classes'),
    ]

    operations = [
        migrations.RunPython(inserer_matieres, supprimer_matieres),
    ]
