from django.core.management.base import BaseCommand
from ecole.models import Eleve, recalculer_scolarite_eleve, recalculer_parcours_eleve

class Command(BaseCommand):
    help = "Recalcule scolarite_* et redoublements pour tous les élèves."

    def handle(self, *args, **options):
        total = 0
        for eleve in Eleve.objects.all().iterator():
            recalculer_scolarite_eleve(eleve)
            recalculer_parcours_eleve(eleve)
            eleve.save(update_fields=[
                'scolarite_1er_cycle', 'scolarite_2e_cycle', 'scolarite_totale',
                'redoublement_1', 'redoublement_2', 'redoublement_3',
            ])
            total += 1
        self.stdout.write(self.style.SUCCESS(f"{total} élève(s) recalculé(s)."))