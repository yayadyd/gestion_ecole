# ecole/migrations/XXXX_initialiser_lycee.py
from django.db import migrations
from decimal import Decimal


def initialiser_lycee(apps, schema_editor):
    """
    Initialise les classes, matières, coefficients et associations du lycée
    selon le système éducatif malien.

    ⚠️ Les coefficients de la TLL sont OFFICIELS (Journal Officiel du Mali).
    Les autres sont des propositions basées sur les programmes officiels
    et la logique pédagogique. Ajustez dans l'admin si nécessaire.
    """
    ClasseLycee = apps.get_model('ecole', 'ClasseLycee')
    MatiereLycee = apps.get_model('ecole', 'MatiereLycee')
    CoefficientLycee = apps.get_model('ecole', 'CoefficientLycee')
    MatiereClasseLycee = apps.get_model('ecole', 'MatiereClasseLycee')
    AnneeScolaire = apps.get_model('ecole', 'AnneeScolaire')

    # ============================================================
    # 1. ANNÉE SCOLAIRE
    # ============================================================
    annee = AnneeScolaire.objects.order_by('-anneeScolaire').first()
    if not annee:
        print("❌ Aucune année scolaire trouvée. Créez-en une d'abord.")
        return
    print(f"✅ Année scolaire utilisée : {annee.anneeScolaire}")

    # ============================================================
    # 2. CLASSES (une par niveau / série)
    # ============================================================
    classes_data = [
        # 10ème : une seule classe (Commune Générale)
        {'nom': '10ème CG', 'niveau': '10', 'serie': ''},
        # 11ème : trois séries
        {'nom': '11ème L', 'niveau': '11', 'serie': 'L'},
        {'nom': '11ème SES', 'niveau': '11', 'serie': 'SES'},
        {'nom': '11ème S', 'niveau': '11', 'serie': 'S'},
        # Terminale : six séries
        {'nom': 'TLL', 'niveau': '12', 'serie': 'TLL'},
        {'nom': 'TAL', 'niveau': '12', 'serie': 'TAL'},
        {'nom': 'TSS', 'niveau': '12', 'serie': 'TSS'},
        {'nom': 'TSEco', 'niveau': '12', 'serie': 'TSEco'},
        {'nom': 'TSExp', 'niveau': '12', 'serie': 'TSExp'},
        {'nom': 'TSE', 'niveau': '12', 'serie': 'TSE'},
    ]

    classes_creees = {}
    for data in classes_data:
        classe, created = ClasseLycee.objects.get_or_create(
            nom=data['nom'],
            annee_scolaire=annee,
            defaults={
                'niveau': data['niveau'],
                'serie': data['serie'],
                'frais_inscription': 0,
                'frais_scolarite': 0,
            }
        )
        classes_creees[data['nom']] = classe
        if created:
            print(f"  ✅ Classe créée : {data['nom']}")

    # ============================================================
    # 3. MATIÈRES DU LYCÉE
    # ============================================================
    matieres_data = [
        # Langues et Communication
        {'nom': 'Français', 'domaine': 'LC', 'ordre': 1},
        {'nom': 'Linguistique', 'domaine': 'LC', 'ordre': 2},
        {'nom': 'Anglais (LV1)', 'domaine': 'LC', 'ordre': 3},
        {'nom': 'Arabe (LV1)', 'domaine': 'LC', 'ordre': 4},
        {'nom': 'Allemand (LV2)', 'domaine': 'LC', 'ordre': 5},
        {'nom': 'Russe (LV2)', 'domaine': 'LC', 'ordre': 6},
        {'nom': 'Espagnol (LV2)', 'domaine': 'LC', 'ordre': 7},
        # Sciences, Mathématiques et Technologies
        {'nom': 'Mathématiques', 'domaine': 'SMT', 'ordre': 8},
        {'nom': 'Physique-Chimie', 'domaine': 'SMT', 'ordre': 9},
        {'nom': 'SVT', 'domaine': 'SMT', 'ordre': 10},
        {'nom': 'Informatique', 'domaine': 'SMT', 'ordre': 11},
        # Sciences Humaines
        {'nom': 'Histoire-Géographie', 'domaine': 'SH', 'ordre': 12},
        {'nom': 'Philosophie', 'domaine': 'SH', 'ordre': 13},
        {'nom': 'Économie', 'domaine': 'SH', 'ordre': 14},
        {'nom': 'Comptabilité', 'domaine': 'SH', 'ordre': 15},
        {'nom': 'Mathématiques Financières', 'domaine': 'SH', 'ordre': 16},
        # Développement de la Personne
        {'nom': 'EPS', 'domaine': 'DP', 'ordre': 17},
        {'nom': 'ECM', 'domaine': 'DP', 'ordre': 18},
    ]

    matieres_creees = {}
    for data in matieres_data:
        matiere, created = MatiereLycee.objects.get_or_create(
            nom=data['nom'],
            defaults={
                'domaine': data['domaine'],
                'ordre_affichage': data['ordre'],
                'obligatoire': True,
                'active': True,
            }
        )
        matieres_creees[data['nom']] = matiere
        if created:
            print(f"  ✅ Matière créée : {data['nom']}")

    # ============================================================
    # 4. COEFFICIENTS PAR (MATIÈRE, NIVEAU, SÉRIE)
    # ============================================================
    # Correspondance nom court → nom complet
    corr = {
        'SVT': 'SVT',
        'EPS': 'EPS',
        'ECM': 'ECM',
        'Anglais': 'Anglais (LV1)',
        'Arabe': 'Arabe (LV1)',
        'Allemand': 'Allemand (LV2)',
        'Russe': 'Russe (LV2)',
        'Espagnol': 'Espagnol (LV2)',
    }

    coefficients_data = [
        # ============================================================
        # 10ème CG (Commune Générale) - Tronc commun
        # ============================================================
        ('Français', '10', '', 3),
        ('Mathématiques', '10', '', 3),
        ('Anglais', '10', '', 2),
        ('Physique-Chimie', '10', '', 2),
        ('SVT', '10', '', 2),
        ('Histoire-Géographie', '10', '', 2),
        ('Philosophie', '10', '', 1),
        ('Économie', '10', '', 1),
        ('Informatique', '10', '', 1),
        ('Allemand', '10', '', 1),      # ✅ LV2 réintégrée
        ('Russe', '10', '', 1),         # ✅ LV2 réintégrée
        ('EPS', '10', '', 1),
        ('ECM', '10', '', 1),
        # Note : Arabe et Espagnol n'ont pas de coefficient (options)

        # ============================================================
        # 11ème L (Lettres)
        # ============================================================
        ('Français', '11', 'L', 4),
        ('Philosophie', '11', 'L', 3),
        ('Anglais', '11', 'L', 3),
        ('Allemand', '11', 'L', 2),
        ('Russe', '11', 'L', 2),
        ('Histoire-Géographie', '11', 'L', 2),
        ('Linguistique', '11', 'L', 2),
        ('Mathématiques', '11', 'L', 1),
        ('EPS', '11', 'L', 1),
        ('ECM', '11', 'L', 1),
        # Pas d'Informatique en 11ème

        # ============================================================
        # 11ème SES (Sciences Économiques et Sociales)
        # ============================================================
        ('Économie', '11', 'SES', 4),
        ('Comptabilité', '11', 'SES', 3),
        ('Mathématiques Financières', '11', 'SES', 3),  # ✅ Ajouté
        ('Mathématiques', '11', 'SES', 3),
        ('Français', '11', 'SES', 3),
        ('Histoire-Géographie', '11', 'SES', 2),
        ('Anglais', '11', 'SES', 2),
        ('Philosophie', '11', 'SES', 2),
        ('Allemand', '11', 'SES', 1),
        ('Russe', '11', 'SES', 1),
        ('EPS', '11', 'SES', 1),
        ('ECM', '11', 'SES', 1),
        # Pas d'Informatique en 11ème

        # ============================================================
        # 11ème S (Sciences)
        # ============================================================
        ('Mathématiques', '11', 'S', 4),
        ('Physique-Chimie', '11', 'S', 4),
        ('SVT', '11', 'S', 3),
        ('Français', '11', 'S', 2),
        ('Anglais', '11', 'S', 2),
        ('Philosophie', '11', 'S', 1),
        ('Histoire-Géographie', '11', 'S', 1),
        ('Allemand', '11', 'S', 1),
        ('Russe', '11', 'S', 1),
        ('EPS', '11', 'S', 1),
        ('ECM', '11', 'S', 1),
        # Pas d'Informatique en 11ème

        # ============================================================
        # Terminale TLL - ✅ Coefficients OFFICIELS
        # ============================================================
        ('Français', '12', 'TLL', 4),
        ('Philosophie', '12', 'TLL', 3),
        ('Anglais', '12', 'TLL', 3),
        ('Allemand', '12', 'TLL', 3),
        ('Russe', '12', 'TLL', 3),
        ('Linguistique', '12', 'TLL', 2),
        ('Mathématiques', '12', 'TLL', 1),

        # ============================================================
        # Terminale TAL (Arts et Lettres)
        # ============================================================
        ('Français', '12', 'TAL', 4),
        ('Philosophie', '12', 'TAL', 3),
        ('Anglais', '12', 'TAL', 3),
        ('Allemand', '12', 'TAL', 2),
        ('Russe', '12', 'TAL', 2),
        ('Histoire-Géographie', '12', 'TAL', 2),
        ('Linguistique', '12', 'TAL', 2),
        ('Mathématiques', '12', 'TAL', 1),

        # ============================================================
        # Terminale TSS (Sciences Sociales)
        # ============================================================
        ('Philosophie', '12', 'TSS', 4),
        ('Histoire-Géographie', '12', 'TSS', 3),
        ('Mathématiques', '12', 'TSS', 3),
        ('Français', '12', 'TSS', 2),
        ('Anglais', '12', 'TSS', 2),
        ('Économie', '12', 'TSS', 2),
        ('Allemand', '12', 'TSS', 1),
        ('Russe', '12', 'TSS', 1),

        # ============================================================
        # Terminale TSEco (Sciences Économiques)
        # ============================================================
        ('Économie', '12', 'TSEco', 5),
        ('Comptabilité', '12', 'TSEco', 3),
        ('Mathématiques Financières', '12', 'TSEco', 3),  # ✅ Ajouté
        ('Mathématiques', '12', 'TSEco', 4),
        ('Français', '12', 'TSEco', 3),
        ('Philosophie', '12', 'TSEco', 2),
        ('Histoire-Géographie', '12', 'TSEco', 2),
        ('Anglais', '12', 'TSEco', 2),
        ('Allemand', '12', 'TSEco', 1),
        ('Russe', '12', 'TSEco', 1),

        # ============================================================
        # Terminale TSExp (Sciences Expérimentales)
        # ============================================================
        ('Mathématiques', '12', 'TSExp', 5),
        ('Physique-Chimie', '12', 'TSExp', 4),
        ('SVT', '12', 'TSExp', 4),
        ('Français', '12', 'TSExp', 2),
        ('Philosophie', '12', 'TSExp', 2),
        ('Anglais', '12', 'TSExp', 2),
        ('Histoire-Géographie', '12', 'TSExp', 1),
        ('Allemand', '12', 'TSExp', 1),
        ('Russe', '12', 'TSExp', 1),

        # ============================================================
        # Terminale TSE (Sciences Exactes)
        # ============================================================
        ('Mathématiques', '12', 'TSE', 6),
        ('Physique-Chimie', '12', 'TSE', 5),
        ('SVT', '12', 'TSE', 3),
        ('Français', '12', 'TSE', 2),
        ('Philosophie', '12', 'TSE', 1),
        ('Anglais', '12', 'TSE', 1),
        ('Histoire-Géographie', '12', 'TSE', 1),
        ('Allemand', '12', 'TSE', 1),
        ('Russe', '12', 'TSE', 1),
    ]

    for nom_court, niveau, serie, coef in coefficients_data:
        nom_complet = corr.get(nom_court, nom_court)
        matiere = matieres_creees.get(nom_complet)
        if not matiere:
            print(f"  ⚠️ Matière introuvable : {nom_complet}")
            continue

        coefficient, created = CoefficientLycee.objects.get_or_create(
            matiere=matiere,
            niveau=niveau,
            serie=serie,
            defaults={'coefficient': Decimal(str(coef))}
        )
        if created:
            print(f"  ✅ Coefficient : {nom_complet} ({niveau} {serie or 'CG'}) = {coef}")

    # ============================================================
    # 5. ASSOCIER LES MATIÈRES AUX CLASSES
    # ============================================================
    for nom_classe, classe in classes_creees.items():
        coefficients_classe = CoefficientLycee.objects.filter(
            niveau=classe.niveau,
            serie=classe.serie or ''
        ).select_related('matiere').order_by('matiere__ordre_affichage')

        for coef in coefficients_classe:
            mc, created = MatiereClasseLycee.objects.get_or_create(
                classe=classe,
                matiere=coef.matiere,
                defaults={
                    'ordre_affichage': coef.matiere.ordre_affichage,
                    'obligatoire': True,
                }
            )
            if created:
                print(f"  ✅ Association : {nom_classe} ← {coef.matiere.nom}")

    print("\n🎉 Initialisation du lycée terminée !")
    print("⚠️  Vérifiez les coefficients dans l'admin si nécessaire.")


def reverse_initialisation(apps, schema_editor):
    """Supprime toutes les données créées par cette migration."""
    MatiereClasseLycee = apps.get_model('ecole', 'MatiereClasseLycee')
    CoefficientLycee = apps.get_model('ecole', 'CoefficientLycee')
    MatiereLycee = apps.get_model('ecole', 'MatiereLycee')
    ClasseLycee = apps.get_model('ecole', 'ClasseLycee')

    # Supprimer dans l'ordre inverse des dépendances
    MatiereClasseLycee.objects.all().delete()
    CoefficientLycee.objects.all().delete()
    MatiereLycee.objects.all().delete()
    ClasseLycee.objects.all().delete()
    print("🗑️  Données du lycée supprimées.")


class Migration(migrations.Migration):

    dependencies = [
        ('ecole', '0020_ecoleinfo_activer_fondamental_and_more'),
    ]

    operations = [
        migrations.RunPython(initialiser_lycee, reverse_initialisation),
    ]