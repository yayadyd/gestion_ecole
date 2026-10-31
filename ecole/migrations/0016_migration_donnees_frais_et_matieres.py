from django.db import migrations

def copier_donnees(apps, schema_editor):
    Classe = apps.get_model('ecole', 'Classe')
    AnneeScolaire = apps.get_model('ecole', 'AnneeScolaire')
    FraisClasseAnnee = apps.get_model('ecole', 'FraisClasseAnnee')
    MatiereClasse = apps.get_model('ecole', 'MatiereClasse')

    # ✅ On cherche l'année la plus récente, peu importe son ID
    annee_defaut = AnneeScolaire.objects.order_by('-anneeScolaire').first()

    if annee_defaut:
        # 1. Créer les frais pour chaque classe
        for classe in Classe.objects.all():
            FraisClasseAnnee.objects.get_or_create(
                classe=classe,
                annee_scolaire=annee_defaut,
                defaults={
                    'frais_inscription': getattr(classe, 'frais_inscription', 0),
                    'frais_scolarite': getattr(classe, 'frais_scolarite', 0),
                }
            )
        
        # 2. Assigner l'année à toutes les matières (qu'elles soient vides ou aient une valeur invalide)
        MatiereClasse.objects.all().update(annee_scolaire=annee_defaut)

def annuler_donnees(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('ecole', '0015_alter_matiereclasse_unique_together_and_more'), # Vérifiez le nom exact
    ]

    operations = [
        migrations.RunPython(copier_donnees, annuler_donnees),
    ]