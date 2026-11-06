# ecole/management/commands/recalculer_scolarites.py
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from ecole.models import Eleve, Inscription, recalculer_parcours_eleve


def recalculer_scolarite_eleve(eleve):
    """Recalcule les compteurs en mémoire (ne sauvegarde pas)."""
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
    help = "Recalcule scolarite_* et redoublements pour tous les élèves."

    def add_arguments(self, parser):
        parser.add_argument('--eleve', type=int, help="ID d'un seul élève.")
        parser.add_argument('--dry-run', action='store_true', help="Simulation.")

    def handle(self, *args, **options):
        eleve_id = options.get('eleve')
        dry_run = options.get('dry_run', False)

        eleves = Eleve.objects.all() if not eleve_id else Eleve.objects.filter(pk=eleve_id)

        if not eleves.exists():
            self.stdout.write(self.style.ERROR("Aucun élève trouvé."))
            return

        self.stdout.write(f"Traitement de {eleves.count()} élève(s)...")
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️ Mode dry-run : rien ne sera sauvegardé."))

        total, modifies, erreurs = 0, 0, 0

        for eleve in eleves.iterator():
            try:
                ancien_1er = eleve.scolarite_1er_cycle
                ancien_2e = eleve.scolarite_2e_cycle
                ancien_total = eleve.scolarite_totale

                # --- 1. Recalcul EN MÉMOIRE ---
                recalculer_scolarite_eleve(eleve)
                recalculer_parcours_eleve(eleve)

                # --- 2. Diagnostic : ce qui va être sauvegardé ---
                self.stdout.write(
                    f"\n[{eleve.matricule}] {eleve.nomEleve} {eleve.prenomEleve}"
                )
                self.stdout.write(
                    f"  Avant : 1er={ancien_1er}, 2e={ancien_2e}, total={ancien_total}"
                )
                self.stdout.write(
                    f"  Après : 1er={eleve.scolarite_1er_cycle}, 2e={eleve.scolarite_2e_cycle}, "
                    f"total={eleve.scolarite_totale}"
                )

                a_change = (
                    ancien_1er != eleve.scolarite_1er_cycle
                    or ancien_2e != eleve.scolarite_2e_cycle
                    or ancien_total != eleve.scolarite_totale
                )

                # --- 3. Sauvegarde RÉELLE ---
                if not dry_run:
                    with transaction.atomic():
                        # 3a. Recharger l'élève depuis la base pour éviter les conflits
                        eleve_db = Eleve.objects.select_for_update().get(pk=eleve.pk)

                        # 3b. Appliquer les valeurs calculées
                        eleve_db.scolarite_1er_cycle = eleve.scolarite_1er_cycle
                        eleve_db.scolarite_2e_cycle = eleve.scolarite_2e_cycle
                        eleve_db.scolarite_totale = eleve.scolarite_totale
                        eleve_db.redoublement_1 = eleve.redoublement_1
                        eleve_db.redoublement_2 = eleve.redoublement_2
                        eleve_db.redoublement_3 = eleve.redoublement_3
                        eleve_db.save()

                    # 3c. VÉRIFICATION : relire depuis la base
                    eleve_verif = Eleve.objects.get(pk=eleve.pk)
                    if (
                        eleve_verif.scolarite_1er_cycle == eleve.scolarite_1er_cycle
                        and eleve_verif.scolarite_2e_cycle == eleve.scolarite_2e_cycle
                    ):
                        self.stdout.write(self.style.SUCCESS("  ✅ Sauvegarde vérifiée en base"))
                    else:
                        self.stdout.write(self.style.ERROR(
                            f"  ❌ INCOHÉRENCE APRÈS SAUVEGARDE : "
                            f"1er={eleve_verif.scolarite_1er_cycle}, "
                            f"2e={eleve_verif.scolarite_2e_cycle}"
                        ))
                        erreurs += 1

                if a_change:
                    modifies += 1

                total += 1

            except Exception as e:
                erreurs += 1
                self.stdout.write(self.style.ERROR(
                    f"  ✗ Erreur pour l'élève {eleve.pk} ({eleve.matricule}) : {e}"
                ))
                import traceback
                traceback.print_exc()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"✅ Terminé : {total} traité(s), {modifies} modifié(s), {erreurs} erreur(s)."
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "⚠️ Mode dry-run : aucune modification enregistrée."
            ))
