"""
Tests de la comptabilité multi-sections (Plan 2 — phase C).

Contrat central :
    global == 1er + 2e + lycee + commun

et aucune ligne de dépense/recette n'est comptée dans deux sections.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, Client

from ecole.models import (
    AnneeScolaire, CategorieDepense, CategorieRecette, Classe, Depense,
    EcoleInfo, Eleve, Inscription, Paiement, Recette, Section,
)
from ecole.services.comptabilite import etat_comptable


class EtatComptableTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.annee = AnneeScolaire.objects.create(
            anneeScolaire='2025-2026',
            date_debut=date(2025, 9, 1),
            date_fin=date(2026, 6, 30),
        )
        # Les classes sont créées par les migrations de données : on les réutilise.
        cls.classe_1er, _ = Classe.objects.update_or_create(
            nomClasse='1ère Année A', defaults={'cycle': '1er'})
        cls.classe_2e, _ = Classe.objects.update_or_create(
            nomClasse='7ème Année A', defaults={'cycle': '2e'})

        eleve = Eleve.objects.create(
            prenomEleve='Test', nomEleve='Eleve',
            dateNaiss=date(2012, 1, 1), lieuNaiss='Bamako',
        )
        cls.inscription = Inscription.objects.create(
            eleve=eleve, classe=cls.classe_1er, anneeScolaire=cls.annee,
        )
        Paiement.objects.create(
            inscription=cls.inscription, montant=Decimal('10000'),
            est_inscription=False, mois=10,
        )

        cat_dep, _ = CategorieDepense.objects.get_or_create(nom='Loyer')
        cat_rec, _ = CategorieRecette.objects.get_or_create(nom='Subvention')

        Depense.objects.create(
            categorie=cat_dep, libelle='Loyer école', montant=Decimal('3000'),
            date_depense=date(2025, 10, 1), anneeScolaire=cls.annee,
            section=Section.COMMUN,
        )
        Depense.objects.create(
            categorie=cat_dep, libelle='Livres 1er cycle', montant=Decimal('2000'),
            date_depense=date(2025, 10, 2), anneeScolaire=cls.annee,
            section=Section.PREMIER,
        )
        Recette.objects.create(
            categorie=cat_rec, libelle='Don', montant=Decimal('5000'),
            date_recette=date(2025, 10, 3), anneeScolaire=cls.annee,
            section=Section.COMMUN,
        )

    def test_invariant_global_egal_somme_des_sections(self):
        etat = etat_comptable(self.annee)
        sections = etat['sections'].values()
        global_ = etat['global']

        self.assertEqual(
            global_['recettes'],
            sum((s['recettes'] for s in sections), Decimal('0')),
        )
        self.assertEqual(
            global_['depenses'],
            sum((s['depenses'] for s in sections), Decimal('0')),
        )
        self.assertEqual(global_['resultat'], global_['recettes'] - global_['depenses'])

    def test_paiement_rattache_au_cycle_de_la_classe(self):
        etat = etat_comptable(self.annee)
        self.assertEqual(etat['sections'][Section.PREMIER]['recettes_paiements'],
                         Decimal('10000'))
        self.assertEqual(etat['sections'][Section.SECOND]['recettes_paiements'],
                         Decimal('0'))
        self.assertEqual(etat['sections'][Section.LYCEE]['recettes_paiements'],
                         Decimal('0'))

    def test_depenses_et_recettes_par_section(self):
        etat = etat_comptable(self.annee)
        self.assertEqual(etat['sections'][Section.COMMUN]['depenses'], Decimal('3000'))
        self.assertEqual(etat['sections'][Section.PREMIER]['depenses'], Decimal('2000'))
        self.assertEqual(etat['sections'][Section.LYCEE]['depenses'], Decimal('0'))
        self.assertEqual(etat['sections'][Section.COMMUN]['recettes_autres'], Decimal('5000'))

    def test_aucune_depense_comptee_deux_fois(self):
        etat = etat_comptable(self.annee)
        total = sum(etat['sections'][s]['depenses'] for s in Section.values)
        self.assertEqual(total, Decimal('5000'))


class ComptabiliteVuesTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username='compta', email='c@example.com', password='p-123456'
        )
        info = EcoleInfo.get_solo()
        info.setup_complete = True
        info.save(update_fields=['setup_complete'])
        AnneeScolaire.objects.create(
            anneeScolaire='2025-2026',
            date_debut=date(2025, 9, 1),
            date_fin=date(2026, 6, 30),
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_dashboard_global(self):
        reponse = self.client.get('/fondamental/comptabilite/')
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Répartition par section')

    def test_dashboard_filtre_par_section(self):
        for code in ['1er', '2e', 'lycee', 'commun']:
            with self.subTest(section=code):
                reponse = self.client.get(f'/fondamental/comptabilite/?section={code}')
                self.assertEqual(reponse.status_code, 200)

    def test_dashboard_lycee_independant(self):
        reponse = self.client.get('/lycee/comptabilite/')
        self.assertEqual(reponse.status_code, 200)
