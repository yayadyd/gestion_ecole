# ecole/management/commands/configurer_matieres.py
"""
Commande Django pour configurer automatiquement les matières par classe.

Usage :
    python manage.py configurer_matieres
    python manage.py configurer_matieres --reset
    python manage.py configurer_matieres --cycle 1er
    python manage.py configurer_matieres --classe "3ème Année"
    python manage.py configurer_matieres --dry-run
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ecole.models import Classe, Matiere, MatiereClasse


# =====================================================================
# CONFIGURATION DES MATIÈRES PAR CYCLE
# ⚠️  Adaptez ces listes au programme réel de votre école
# =====================================================================
MATIERES_1ER_CYCLE = [
    'Langage',
    'Lecture',
    'Écriture',
    'Mathématiques',
    'Sciences d\'observation',
    'Histoire-Géographie',
    'Éducation civique et morale',
    'Dessin',
    'Chant',
    'Éducation physique et sportive',
]

MATIERES_2E_CYCLE = [
    'Français',
    'Mathématiques',
    'Physique-Chimie',
    'Sciences de la Vie et de la Terre',
    'Histoire-Géographie',
    'Éducation civique',
    'Anglais',
    'Éducation physique et sportive',
]


class Command(BaseCommand):
    help = "Configure automatiquement les matières pour toutes les classes (ou une seule)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help="Supprime TOUTES les associations existantes avant de reconfigurer.",
        )
        parser.add_argument(
            '--cycle',
            type=str,
            choices=['1er', '2e'],
            help="Limiter la configuration à un cycle (1er ou 2e).",
        )
        parser.add_argument(
            '--classe',
            type=str,
            help="Limiter la configuration à une classe précise (nom exact).",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Affiche ce qui serait fait SANS modifier la base.",
        )

    def handle(self, *args, **options):
        reset = options['reset']
        cycle_filtre = options['cycle']
        classe_filtre = options['classe']
        dry_run = options['dry_run']

        # ============================================================
        # EN-TÊTE
        # ============================================================
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n╔══════════════════════════════════════════════════════════╗\n"
            "║   CONFIGURATION DES MATIÈRES PAR CLASSE                  ║\n"
            "╚══════════════════════════════════════════════════════════╝\n"
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "⚠️  MODE DRY-RUN : aucune modification ne sera appliquée.\n"
            ))

        # ============================================================
        # 1. CRÉATION DES MATIÈRES MANQUANTES AU CATALOGUE
        # ============================================================
        self.stdout.write(self.style.HTTP_INFO("📚 Étape 1/2 : Vérification du catalogue des matières\n"))

        matieres_creees = 0
        matieres_existantes = 0

        for cycle, liste_matieres in [('1er', MATIERES_1ER_CYCLE), ('2e', MATIERES_2E_CYCLE)]:
            if cycle_filtre and cycle != cycle_filtre:
                continue

            for nom in liste_matieres:
                existante = Matiere.objects.filter(nomMatiere=nom, cycle=cycle).first()
                if existante:
                    matieres_existantes += 1
                else:
                    if not dry_run:
                        Matiere.objects.create(
                            nomMatiere=nom,
                            cycle=cycle,
                            coef=1,
                        )
                    matieres_creees += 1
                    self.stdout.write(f"  ✅ Créée : {self.style.SUCCESS(nom)} ({cycle})")

        self.stdout.write(
            f"\n  → {matieres_existantes} matière(s) déjà présente(s)\n"
            f"  → {matieres_creees} matière(s) créée(s)\n"
        )

        # ============================================================
        # 2. RESET (si demandé)
        # ============================================================
        if reset:
            if dry_run:
                nb = MatiereClasse.objects.count()
                self.stdout.write(self.style.WARNING(
                    f"  🗑️  [DRY-RUN] {nb} association(s) seraient supprimées.\n"
                ))
            else:
                nb = MatiereClasse.objects.count()
                MatiereClasse.objects.all().delete()
                self.stdout.write(self.style.WARNING(
                    f"  🗑️  {nb} association(s) supprimée(s).\n"
                ))

        # ============================================================
        # 3. ASSOCIATION AUX CLASSES
        # ============================================================
        self.stdout.write(self.style.HTTP_INFO(
            "🔗 Étape 2/2 : Association des matières aux classes\n"
        ))

        # Filtrer les classes
        classes = Classe.objects.all().order_by('cycle', 'nomClasse')
        if cycle_filtre:
            classes = classes.filter(cycle=cycle_filtre)
        if classe_filtre:
            classes = classes.filter(nomClasse=classe_filtre)
            if not classes.exists():
                raise CommandError(f"❌ Aucune classe trouvée avec le nom : '{classe_filtre}'")

        if not classes.exists():
            raise CommandError("❌ Aucune classe à configurer.")

        total_ajoutees = 0
        total_existantes = 0

        # Utilisation d'une transaction pour tout valider d'un coup
        with transaction.atomic():
            for classe in classes:
                liste = MATIERES_1ER_CYCLE if classe.cycle == '1er' else MATIERES_2E_CYCLE
                nb_avant = MatiereClasse.objects.filter(classe=classe).count()
                ajoutees = 0

                for i, nom in enumerate(liste, start=1):
                    try:
                        matiere = Matiere.objects.get(nomMatiere=nom, cycle=classe.cycle)
                    except Matiere.DoesNotExist:
                        self.stdout.write(self.style.WARNING(
                            f"    ⚠️  Matière '{nom}' absente du catalogue {classe.cycle}"
                        ))
                        continue

                    if not dry_run:
                        _, created = MatiereClasse.objects.get_or_create(
                            classe=classe,
                            matiere=matiere,
                            defaults={
                                'ordre_affichage': i,
                                'obligatoire': True,
                            }
                        )
                    else:
                        created = not MatiereClasse.objects.filter(
                            classe=classe, matiere=matiere
                        ).exists()

                    if created:
                        ajoutees += 1

                nb_apres = nb_avant + ajoutees

                # Affichage ligne par ligne
                statut = "🆕" if ajoutees > 0 else "✅"
                self.stdout.write(
                    f"  {statut} {classe.nomClasse:15} "
                    f"({classe.cycle}) : "
                    f"{nb_avant:2} → {self.style.SUCCESS(str(nb_apres)):2} matière(s) "
                    f"{f'(+{ajoutees})' if ajoutees > 0 else ''}"
                )

                total_ajoutees += ajoutees
                total_existantes += (len(liste) - ajoutees)

            if dry_run:
                # Annuler la transaction en dry-run
                transaction.set_rollback(True)

        # ============================================================
        # 4. RÉSUMÉ FINAL
        # ============================================================
        self.stdout.write("\n" + "═" * 60)
        self.stdout.write(self.style.SUCCESS("✅ CONFIGURATION TERMINÉE"))
        self.stdout.write("═" * 60)
        self.stdout.write(f"  Classes traitées       : {classes.count()}")
        self.stdout.write(f"  Matières créées        : {matieres_creees}")
        self.stdout.write(f"  Associations ajoutées  : {total_ajoutees}")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n  ⚠️  DRY-RUN : rien n'a été enregistré en base."
            ))
        else:
            total_global = MatiereClasse.objects.count()
            self.stdout.write(f"  Total associations     : {total_global}")
            self.stdout.write(self.style.SUCCESS("\n🎉 Vous pouvez maintenant utiliser le filtrage par matière !\n"))
