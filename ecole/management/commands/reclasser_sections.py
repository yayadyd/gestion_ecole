"""
Commande de reclassement des mouvements comptables par section.

Usage :
    python manage.py reclasser_sections --dry-run
    python manage.py reclasser_sections
    python manage.py reclasser_sections --categorie "Salaires" --section commun

La commande applique à chaque dépense/recette la section définie par
défaut sur sa catégorie (`section_defaut`). Avec `--categorie`/`--section`,
elle met d'abord à jour le défaut de la catégorie puis reclasse ses lignes.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ecole.models import (
    CategorieDepense, CategorieRecette, Depense, Recette, Section,
)


class Command(BaseCommand):
    help = (
        "Reclassifie les dépenses/recettes selon la section par défaut "
        "de leur catégorie."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Affiche les changements sans rien écrire.",
        )
        parser.add_argument(
            '--categorie', type=str,
            help="Ne traiter que cette catégorie (nom exact).",
        )
        parser.add_argument(
            '--section', type=str, choices=Section.values,
            help="Section à appliquer (requiert --categorie).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry = options['dry_run']
        categorie = options.get('categorie')
        section = options.get('section')

        if section and not categorie:
            raise CommandError("--section nécessite --categorie.")

        # 1. Mise à jour du défaut de catégorie si demandé.
        if categorie and section:
            for model in (CategorieDepense, CategorieRecette):
                if dry:
                    if model.objects.filter(nom=categorie).exists():
                        self.stdout.write(
                            f"[défaut] {model.__name__} « {categorie} » → {section} (dry-run)"
                        )
                    continue
                maj = model.objects.filter(nom=categorie).update(section_defaut=section)
                if maj:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[défaut] {model.__name__} « {categorie} » → {section}"
                        )
                    )

        # 2. Reclassement des lignes.
        for modele in (Depense, Recette):
            qs = modele.objects.select_related('categorie').order_by('id')
            if categorie:
                qs = qs.filter(categorie__nom=categorie)

            for obj in qs:
                cible = obj.categorie.section_defaut or Section.COMMUN
                if obj.section == cible:
                    continue
                avant = obj.section
                if not dry:
                    obj.section = cible
                    obj.save(update_fields=['section'])
                self.stdout.write(
                    f"{modele.__name__} #{obj.pk} « {obj.libelle} » : "
                    f"{avant} → {cible}"
                )

        if dry:
            self.stdout.write(self.style.WARNING("Mode --dry-run : aucune écriture."))
        else:
            self.stdout.write(self.style.SUCCESS("Reclassement terminé."))
