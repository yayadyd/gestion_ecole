"""
Tests des résultats scolaires unifiés (Plan 2 — phase D).

Vérifie la façade de lecture : compositions du 1er cycle, trimestres
du 2e cycle, et la synthèse globale. Aucun recalcul de moyenne.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, Client

from ecole.models import (
    AnneeScolaire, Classe, CompositionMensuelle, EcoleInfo, Eleve,
    Inscription, ResultatMensuel, ResultatTrimestre,
)
from ecole.services.resultats import resume_global, resultats


class ResultatsServiceTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.annee = AnneeScolaire.objects.create(
            anneeScolaire='2025-2026', date_debut=date(2025, 9, 1), date_fin=date(2026, 6, 30))
        cls.classe_1er, _ = Classe.objects.update_or_create(
            nomClasse='1ère Année A', defaults={'cycle': '1er'})
        cls.classe_2e, _ = Classe.objects.update_or_create(
            nomClasse='7ème Année A', defaults={'cycle': '2e'})

        cls.eleve = Eleve.objects.create(
            prenomEleve='Aminata', nomEleve='Traoré',
            dateNaiss=date(2013, 5, 10), lieuNaiss='Bamako',
        )
        cls.inscription = Inscription.objects.create(
            eleve=cls.eleve, classe=cls.classe_1er, anneeScolaire=cls.annee)

        cls.composition = CompositionMensuelle.objects.create(
            mois=10, anneeScolaire=cls.annee)
        ResultatMensuel.objects.create(
            inscription=cls.inscription, composition=cls.composition,
            moyenne_generale=Decimal('8.50'), rang=1, appreciation='Bien',
        )

    def test_compositions_1er_cycle(self):
        donnees = resultats(self.annee, '1er')
        self.assertEqual(donnees['nb_resultats'], 1)
        self.assertEqual(donnees['lignes'][0]['eleve'], 'Aminata Traoré')
        self.assertEqual(donnees['lignes'][0]['moyenne'], Decimal('8.50'))
        self.assertEqual(donnees['statut'], 'calculé')
        # Une composition du 1er cycle est un mois (pas un trimestre)
        self.assertEqual(donnees['periodes'][0]['label'], 'Octobre')

    def test_section_sans_resultat_est_signalee(self):
        donnees = resultats(self.annee, '2e')
        self.assertEqual(donnees['nb_resultats'], 0)
        self.assertEqual(donnees['statut'], 'à calculer')

    def test_resume_global(self):
        resume = resume_global(self.annee)
        self.assertEqual(len(resume['lignes']), 3)
        self.assertEqual(resume['nb_resultats'], 1)


class ResultatsVuesTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username='res', email='r@example.com', password='p-123456')
        info = EcoleInfo.get_solo()
        info.setup_complete = True
        info.save(update_fields=['setup_complete'])
        cls.annee = AnneeScolaire.objects.create(
            anneeScolaire='2025-2026', date_debut=date(2025, 9, 1), date_fin=date(2026, 6, 30))

        classe, _ = Classe.objects.update_or_create(
            nomClasse='1ère Année A', defaults={'cycle': '1er'})
        eleve = Eleve.objects.create(
            prenomEleve='Moussa', nomEleve='Diarra',
            dateNaiss=date(2013, 1, 1), lieuNaiss='Ségou')
        inscription = Inscription.objects.create(
            eleve=eleve, classe=classe, anneeScolaire=cls.annee)
        composition = CompositionMensuelle.objects.create(mois=10, anneeScolaire=cls.annee)
        ResultatMensuel.objects.create(
            inscription=inscription, composition=composition,
            moyenne_generale=Decimal('7.25'), rang=2,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_page_resultats_1er(self):
        reponse = self.client.get('/fondamental/resultats/?section=1er')
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Moussa Diarra')

    def test_page_resultats_global(self):
        reponse = self.client.get('/fondamental/resultats/?section=global')
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Synthèse')

    def test_page_resultats_lycee(self):
        # La section lycée est DÉSORMAIS au lycée (vue dédiée)
        reponse = self.client.get('/fondamental/resultats/?section=lycee')
        self.assertEqual(reponse.status_code, 302)
        # La vue lycée dédiée répond 200
        reponse = self.client.get('/lycee/resultats/')
        self.assertEqual(reponse.status_code, 200)
