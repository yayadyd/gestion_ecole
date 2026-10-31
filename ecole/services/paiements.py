# ecole/services/paiements.py
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from ..models import EcoleInfo, Paiement, Inscription, FraisClasseAnnee


def _get_frais_classe(classe, annee_scolaire):
    """
    Récupère les frais d'une classe pour une année donnée.
    Retourne un tuple (frais_inscription, frais_scolarite).
    Si aucune configuration n'est trouvée, retourne (0, 0).
    """
    try:
        frais = FraisClasseAnnee.objects.get(classe=classe, annee_scolaire=annee_scolaire)
        return frais.frais_inscription, frais.frais_scolarite
    except FraisClasseAnnee.DoesNotExist:
        return Decimal('0'), Decimal('0')


def _repartir(total, nb):
    """
    Répartit `total` en `nb` parts entières : les nb-1 premières sont arrondies
    à l'entier inférieur et la DERNIÈRE absorbe le reste.
    100 000 en 9 → 8 × 11 111 + 11 112 (la somme fait toujours 100 000).
    """
    total = Decimal(str(total))
    base = (total / nb).quantize(Decimal('1'), rounding=ROUND_DOWN)
    parts = [base] * (nb - 1)
    parts.append(total - base * (nb - 1))
    return parts


def calculer_echeances(ecole, classe, annee_scolaire):
    """
    Retourne la liste des échéances de scolarité.
    ✅ La somme des échéances est toujours égale au montant annuel.
    """
    _, montant_annuel = _get_frais_classe(classe, annee_scolaire)
    montant_annuel = Decimal(str(montant_annuel))

    mode = ecole.mode_frais_scolarite
    echeances = []

    # MENSUEL : 9 versements
    if mode == 'mensuel':
        montants = _repartir(montant_annuel, 9)
        mois_scolaires = [
            (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre'),
            (1, 'Janvier'), (2, 'Février'), (3, 'Mars'),
            (4, 'Avril'), (5, 'Mai'), (6, 'Juin'),
        ]
        for i, (mois, nom) in enumerate(mois_scolaires, start=1):
            annee = (
                annee_scolaire.get_annee_debut() if mois >= 10
                else annee_scolaire.get_annee_fin()
            )
            echeances.append({
                'numero': i, 'libelle': nom, 'mois': mois, 'annee': annee,
                'montant': montants[i - 1], 'deja_paye': False,
            })

    # TRIMESTRIEL : 3 versements
    elif mode == 'trimestriel':
        montants = _repartir(montant_annuel, 3)
        trimestres = [
            (1, '1er Trimestre'), (2, '2ème Trimestre'), (3, '3ème Trimestre'),
        ]
        for i, (num, nom) in enumerate(trimestres, start=1):
            echeances.append({
                'numero': i, 'libelle': nom, 'mois': None,
                'annee': annee_scolaire.get_annee_debut(),
                'montant': montants[i - 1], 'deja_paye': False,
            })

    # TRANCHES : N versements
    elif mode == 'tranches':
        nb = ecole.nombre_tranches or 4
        montants = _repartir(montant_annuel, nb)
        for i in range(1, nb + 1):
            libelle = "1ère tranche" if i == 1 else f"{i}ème tranche"
            echeances.append({
                'numero': i, 'libelle': libelle, 'mois': None,
                'annee': annee_scolaire.get_annee_debut(),
                'montant': montants[i - 1], 'deja_paye': False,
            })

    # ANNUEL : 1 versement
    elif mode == 'annuel':
        echeances.append({
            'numero': 1, 'libelle': "Année complète", 'mois': None,
            'annee': annee_scolaire.get_annee_debut(),
            'montant': montant_annuel, 'deja_paye': False,
        })

    # UNIQUE : 1 versement pour tout le cursus
    elif mode == 'unique':
        echeances.append({
            'numero': 1, 'libelle': "Scolarité complète (cursus)", 'mois': None,
            'annee': annee_scolaire.get_annee_debut(),
            'montant': montant_annuel, 'deja_paye': False,
        })

    return echeances


def _deja_paye_avant(inscription, est_inscription):
    """
    True si les frais « uniques » (inscription ou scolarité) ont été payés
    ENTIÈREMENT lors d'inscriptions antérieures de cet élève.
    ✅ Comparaison de MONTANT : un acompte ne vaut plus « tout payé ».
    Si les frais de l'époque ne sont pas configurés (0), tout paiement compte.
    """
    if not inscription or not inscription.eleve_id:
        return False
    annee_courante = inscription.anneeScolaire.anneeScolaire
    autres = Inscription.objects.filter(
        eleve=inscription.eleve,
        anneeScolaire__anneeScolaire__lt=annee_courante,
    ).exclude(pk=inscription.pk).select_related('classe', 'anneeScolaire')

    paye_total = Decimal('0')
    du_max = Decimal('0')
    for ins in autres:
        montants = Paiement.objects.filter(
            inscription=ins, est_inscription=est_inscription
        ).values_list('montant', flat=True)
        paye_total += sum((Decimal(str(m)) for m in montants), Decimal('0'))
        frais_inscr, frais_scol = _get_frais_classe(ins.classe, ins.anneeScolaire)
        du_max = max(du_max, Decimal(str(frais_inscr if est_inscription else frais_scol)))

    return paye_total > 0 and (du_max <= 0 or paye_total >= du_max)


def _frais_inscription_deja_paye(inscription):
    """Frais d'inscription « unique » déjà payés dans une inscription antérieure."""
    return _deja_paye_avant(inscription, True)


def _scolarite_unique_deja_payee(inscription):
    """Scolarité « unique » déjà payée dans une inscription antérieure."""
    return _deja_paye_avant(inscription, False)


def _allouer_paiements(echeances, paiements):
    """
    Répartit les paiements de scolarité sur les échéances, PAR MONTANT.

    1. Mode mensuel : un paiement va d'abord à l'échéance de son mois.
    2. Tout le reste (excédent d'un mois, paiement sans mois ou hors calendrier,
       modes trimestriel / tranches / annuel) est réparti dans l'ordre
       chronologique sur les échéances qui ont encore un reste à payer.
    3. Un éventuel trop-perçu final est ajouté à la dernière échéance.

    Retourne une liste (même ordre que `echeances`) de
    {'paye': Decimal, 'paiements_lies': [paiements]}.
    """
    allocations = [{'paye': Decimal('0'), 'paiements_lies': []} for _ in echeances]
    restes = [[p, Decimal(str(p.montant))] for p in paiements]

    def affecter(idx, entree, montant):
        allocations[idx]['paye'] += montant
        if entree[0] not in allocations[idx]['paiements_lies']:
            allocations[idx]['paiements_lies'].append(entree[0])
        entree[1] -= montant

    # 1. Paiements rattachés à leur mois
    for idx, ech in enumerate(echeances):
        if ech['deja_paye'] or not ech.get('mois'):
            continue
        for entree in restes:
            p = entree[0]
            if p.mois == ech['mois'] and p.annee_paiement == ech['annee'] and entree[1] > 0:
                manque = ech['montant'] - allocations[idx]['paye']
                prise = min(entree[1], manque)
                if prise > 0:
                    affecter(idx, entree, prise)

    # 2. Le reste, dans l'ordre, sur ce qui n'est pas encore soldé
    for idx, ech in enumerate(echeances):
        if ech['deja_paye']:
            continue
        for entree in restes:
            manque = ech['montant'] - allocations[idx]['paye']
            if manque <= 0:
                break
            if entree[1] > 0:
                affecter(idx, entree, min(entree[1], manque))

    # 3. Trop-perçu : conservé (jamais perdu) sur la dernière échéance à payer
    cibles = [i for i, e in enumerate(echeances) if not e['deja_paye']]
    if cibles:
        for entree in restes:
            if entree[1] > 0:
                affecter(cibles[-1], entree, entree[1])

    return allocations


def calculer_montants_inscription(inscription):
    """
    Calcule les montants attendus/payés pour une inscription.
    ✅ Utilise le nouveau modèle FraisClasseAnnee.
    """
    if not inscription:
        return {}

    ecole = EcoleInfo.get_solo()
    classe = inscription.classe
    annee = inscription.anneeScolaire
    eleve = inscription.eleve

    # ================================================================
    # 1. RÉCUPÉRATION DES FRAIS DEPUIS LE NOUVEAU MODÈLE
    # ================================================================
    frais_inscription_base, frais_scolarite_base = _get_frais_classe(classe, annee)

    # ================================================================
    # 2. FRAIS D'INSCRIPTION
    # ================================================================
    frais_inscription_attendu = Decimal('0')
    frais_inscription_paye = Decimal('0')

    if ecole.mode_frais_inscription == 'annuel':
        frais_inscription_attendu = frais_inscription_base
    elif ecole.mode_frais_inscription == 'unique':
        deja_paye = _frais_inscription_deja_paye(inscription)
        if not deja_paye:
            frais_inscription_attendu = frais_inscription_base

    paiements_inscription_liste = list(
        inscription.paiement_set.filter(est_inscription=True).order_by('date_paiement', 'idPaiement')
    )
    for p in paiements_inscription_liste:
        frais_inscription_paye += Decimal(str(p.montant))

    # ================================================================
    # 3. SCOLARITÉ
    # ================================================================
    echeances = calculer_echeances(ecole, classe, annee)

    if ecole.mode_frais_scolarite == 'unique':
        if _scolarite_unique_deja_payee(inscription):
            for ech in echeances:
                ech['deja_paye'] = True
                ech['montant'] = Decimal('0')

    paiements_scolarite = list(
        inscription.paiement_set.filter(est_inscription=False).order_by('date_paiement', 'idPaiement')
    )

        # ================================================================
    # 4. ASSOCIER LES PAIEMENTS AUX ÉCHÉANCES (par montant)
    # ================================================================
    allocations = _allouer_paiements(echeances, paiements_scolarite)

    detail_echeances = []
    scolarite_attendue = Decimal('0')
    scolarite_payee = Decimal('0')
    nb_echeances_payees = 0

    for ech, alloc in zip(echeances, allocations):
        montant_attendu = ech['montant']
        scolarite_attendue += montant_attendu

        if ech['deja_paye']:
            montant_paye = montant_attendu
            paiements_lies = []
            nb_echeances_payees += 1
        else:
            montant_paye = alloc['paye']
            paiements_lies = alloc['paiements_lies']
            if montant_attendu > 0 and montant_paye >= montant_attendu:
                nb_echeances_payees += 1

        scolarite_payee += montant_paye

        reste_echeance = (
            max(Decimal('0'), montant_attendu - montant_paye)
            if not ech['deja_paye'] else Decimal('0')
        )

        detail_echeances.append({
            'numero': ech['numero'],
            'libelle': ech['libelle'],
            'mois': ech.get('mois'),
            'annee': ech.get('annee'),
            'attendu': montant_attendu,
            'paye': montant_paye,
            'reste': reste_echeance,
            'paiements_lies': paiements_lies,
            'nb_paiements': len(paiements_lies),
            'deja_paye': ech['deja_paye'],
        })

    # ================================================================
    # 5. TOTAUX
    # ================================================================
        # ================================================================
    # 5. TOTAUX
    # ================================================================
    # ✅ FIX : Si les frais d'inscription sont "Payés avant l'app", 
    # on les considère comme payés dans le total.
    frais_inscription_reellement_payes = frais_inscription_paye
    if inscription.frais_inscription_historique:
        frais_inscription_reellement_payes = frais_inscription_attendu

    total_attendu = frais_inscription_attendu + scolarite_attendue
    total_paye = frais_inscription_reellement_payes + scolarite_payee
    
    # ✅ Le reste est calculé sur la base du vrai total payé
    reste = max(Decimal('0'), total_attendu - total_paye)

    pourcentage_frais = (
        min(100, int(frais_inscription_paye / frais_inscription_attendu * 100))
        if frais_inscription_attendu > 0 else 0
    )
    pourcentage_scolarite = (
        min(100, int(scolarite_payee / scolarite_attendue * 100))
        if scolarite_attendue > 0 else 0
    )
    pourcentage_total = (
        min(100, int(total_paye / total_attendu * 100))
        if total_attendu > 0 else 0
    )

    historique_paiements = inscription.paiement_set.order_by('-date_paiement', '-idPaiement')

    return {
        'mode_frais_inscription': ecole.get_mode_frais_inscription_display(),
        'mode_frais_scolarite': ecole.get_mode_frais_scolarite_display(),
        'mode_frais_inscription_code': ecole.mode_frais_inscription,
        'mode_frais_scolarite_code': ecole.mode_frais_scolarite,
        'nombre_tranches': ecole.nombre_tranches,
        'frais_inscription_historique': inscription.frais_inscription_historique,

        'frais_inscription_attendu': frais_inscription_attendu,
        'frais_inscription_paye': frais_inscription_paye,
        'frais_inscription_reste': max(Decimal('0'), frais_inscription_attendu - frais_inscription_paye),
        'paiements_inscription_liste': paiements_inscription_liste,

        'scolarite_attendue': scolarite_attendue,
        'scolarite_payee': scolarite_payee,
        'scolarite_reste': max(Decimal('0'), scolarite_attendue - scolarite_payee),
        'detail_echeances': detail_echeances,
        'nb_echeances': len(detail_echeances),
        'nb_echeances_payees': nb_echeances_payees,

        'total_attendu': total_attendu,
        'total_paye': total_paye,
        'reste': reste,

        'pourcentage_frais': pourcentage_frais,
        'pourcentage_scolarite': pourcentage_scolarite,
        'pourcentage_total': pourcentage_total,

        'historique_paiements': historique_paiements,
        'frais_non_configures': not FraisClasseAnnee.objects.filter(
            classe=classe, annee_scolaire=annee).exists(),
    }