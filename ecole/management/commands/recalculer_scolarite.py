# ecole/management/commands/recalculer_scolarites.py
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from ecole.models import Eleve, Inscription, recalculer_parcours_eleve


def recalculer_scolarite_eleve(eleve):
    """
    Recalcule scolarite_1er_cycle et scolarite_2e_cycle à partir des inscriptions.
    Source de vérité unique : la table Inscription.
    """
    compteurs = (
        Inscription.objects
        .filter(eleve=eleve)
        .values('classe__cycle')
        .annotate(nb=Count('idInscription'))
    )
    par_cycle = {item['classe__cycle']: item['nb'] for item in compteurs}

    eleve.scolarite_1er_cycle = par_cycle.get('1er', 0)
    eleve.scolarite_2e_cycle = par_cycle.get('2e', 0)
    eleve.scolarite_totale = eleve.scolarite_1er_cycle + eleve.scolarite_2e_cycle


class Command(BaseCommand):
    help = (
        "Recalcule scolarite_1er_cycle, scolarite_2e_cycle, scolarite_totale "
        "et les redoublements pour tous les élèves à partir des inscriptions existantes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--eleve',
            type=int,
            help="Recalculer uniquement pour un élève (ID).",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Afficher ce qui serait modifié, sans rien enregistrer.",
        )

    def handle(self, *args, **options):
        eleve_id = options.get('eleve')
        dry_run = options.get('dry_run', False)

        # Filtrer les élèves
        if eleve_id:
            eleves = Eleve.objects.filter(pk=eleve_id)
            if not eleves.exists():
                self.stdout.write(self.style.ERROR(f"Aucun élève avec l'ID {eleve_id}."))
                return
        else:
            eleves = Eleve.objects.all()

        total = 0
        modifies = 0
        erreurs = 0

        self.stdout.write(f"Traitement de {eleves.count()} élève(s)...")
        if dry_run:
            self.stdout.write(self.style.WARNING("Mode dry-run : aucune modification ne sera enregistrée."))

        for eleve in eleves.iterator():
            try:
                # Sauvegarder les anciennes valeurs pour comparaison
                ancien_1er = eleve.scolarite_1er_cycle
                ancien_2e = eleve.scolarite_2e_cycle
                ancien_total = eleve.scolarite_totale

                # Recalculer
                recalculer_scolarite_eleve(eleve)
                recalculer_parcours_eleve(eleve)

                # Vérifier si quelque chose a changé
                a_change = (
                    ancien_1er != eleve.scolarite_1er_cycle
                    or ancien_2e != eleve.scolarite_2e_cycle
                    or ancien_total != eleve.scolarite_totale
                )

                if a_change:
                    modifies += 1
                    self.stdout.write(
                        f"  → {eleve.matricule} {eleve.nomEleve} {eleve.prenomEleve} : "
                        f"1er {ancien_1er}→{eleve.scolarite_1er_cycle}, "
                        f"2e {ancien_2e}→{eleve.scolarite_2e_cycle}, "
                        f"total {ancien_total}→{eleve.scolarite_totale}"
                    )

                # Enregistrer (sauf en dry-run)
                if not dry_run:
                    with transaction.atomic():
                        eleve.save(update_fields=[
                            'scolarite_1er_cycle', 'scolarite_2e_cycle', 'scolarite_totale',
                            'redoublement_1', 'redoublement_2', 'redoublement_3',
                        ])

                total += 1

            except Exception as e:
                erreurs += 1
                self.stdout.write(self.style.ERROR(
                    f"  ✗ Erreur pour l'élève {eleve.pk} ({eleve.matricule}) : {e}"
                ))

        # Résumé
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"✅ Terminé : {total} élève(s) traité(s), {modifies} modification(s), {erreurs} erreur(s)."
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "⚠️  Mode dry-run : aucune modification n'a été enregistrée."
            ))