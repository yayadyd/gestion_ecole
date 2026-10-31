#!/usr/bin/env python3
"""
OUTIL DU VENDEUR — à garder chez vous, NE JAMAIS LIVRER AU CLIENT.

Placez ce fichier à la racine du projet (le dossier qui contient « ecole/ »).

1) Une seule fois, créer votre paire de clés :
       python outils_licence.py genkeys
   → cle_privee_licence.key : SECRÈTE, à sauvegarder en lieu sûr (si vous la
                              perdez, plus aucune nouvelle clé n'est possible)
   → cle_publique.py        : à copier dans ecole/utils/ (livré avec l'application)

2) Pour chaque vente (le client vous envoie son CODE MACHINE) :
       python outils_licence.py emettre --code A1B2-C3D4-E5F6-0718 --client "Ecole X"
       python outils_licence.py emettre --code ... --client "Ecole X" --expire 2027-10-31
   → affiche la clé à envoyer (par WhatsApp, email) et l'enregistre dans un .lic

3) Pour contrôler une clé :
       python outils_licence.py lire GE1.xxxxx
"""
import argparse
import importlib
import json
import os
import re
import sys
import types
from datetime import date

RACINE = os.path.dirname(os.path.abspath(__file__))
FICHIER_PRIVEE = "cle_privee_licence.key"


def _charger_modules():
    """Charge ed25519 et licence_signee sans importer tout le projet Django."""
    utils = os.path.join(RACINE, "ecole", "utils")
    if not os.path.isdir(utils):
        sys.exit("❌ Dossier ecole/utils introuvable : placez ce fichier à la racine du projet.")
    pkg = types.ModuleType("licence_pkg")
    pkg.__path__ = [utils]
    sys.modules["licence_pkg"] = pkg
    return (importlib.import_module("licence_pkg.ed25519"),
            importlib.import_module("licence_pkg.licence_signee"))


def _lire_privee(chemin):
    if not os.path.exists(chemin):
        sys.exit(f"❌ Clé privée introuvable : {chemin}\n   (créez-la avec : python outils_licence.py genkeys)")
    with open(chemin) as f:
        return bytes.fromhex(f.read().strip())


def cmd_genkeys(args):
    ed, signee = _charger_modules()
    chemin_privee = os.path.join(args.dossier, FICHIER_PRIVEE)
    if os.path.exists(chemin_privee):
        sys.exit(f"❌ {chemin_privee} existe déjà : refus de l'écraser (toutes vos licences deviendraient inutilisables).")

    secret = os.urandom(32)
    public = ed.secret_to_public(secret)

    with open(chemin_privee, "w") as f:
        f.write(secret.hex())
    try:
        os.chmod(chemin_privee, 0o600)
    except OSError:
        pass

    chemin_pub = os.path.join(args.dossier, "cle_publique.py")
    with open(chemin_pub, "w", encoding="utf-8") as f:
        f.write(
            '# ecole/utils/cle_publique.py\n'
            '"""Clé PUBLIQUE de vérification des licences (non secrète)."""\n'
            f'CLE_PUBLIQUE_B64 = "{signee._b64e(public)}"\n'
        )

    print(f"✅ Clé privée  : {chemin_privee}   ← SECRÈTE : sauvegardez-la, ne la livrez jamais")
    print(f"✅ Clé publique: {chemin_pub}   ← à copier dans ecole/utils/ (livré avec l'application)")


def cmd_emettre(args):
    ed, signee = _charger_modules()
    secret = _lire_privee(args.cle_privee)

    code = re.sub(r"[^0-9A-Fa-f]", "", args.code).upper()
    if len(code) != 16:
        sys.exit("❌ Code machine invalide : 16 caractères hexadécimaux attendus (ex. A1B2-C3D4-E5F6-0718).")

    expire = None
    if args.expire:
        try:
            expire = date.fromisoformat(args.expire)
        except ValueError:
            sys.exit("❌ Date d'expiration invalide : utilisez AAAA-MM-JJ (ex. 2027-10-31).")

    cle = signee.fabriquer_cle(secret, code, args.client, expire=expire, numero=args.numero or "")
    nom = re.sub(r"[^A-Za-z0-9]+", "_", args.client).strip("_") or "client"
    fichier = f"licence_{nom}_{date.today().isoformat()}.lic"
    with open(fichier, "w") as f:
        f.write(cle)

    print(f"\n✅ Licence émise pour « {args.client} »")
    print(f"   Machine : {'-'.join(code[i:i+4] for i in range(0, 16, 4))}")
    print(f"   Validité : {'jusqu au ' + expire.strftime('%d/%m/%Y') if expire else 'illimitée'}")
    print(f"   Fichier : {fichier}\n")
    print("Clé à envoyer au client :\n")
    print(cle + "\n")


def cmd_lire(args):
    ed, signee = _charger_modules()
    secret = _lire_privee(args.cle_privee)
    public = ed.secret_to_public(secret)
    cle = signee.nettoyer(args.cle)
    try:
        charge = json.loads(signee._b64d(cle[len(signee.PREFIXE):].split(".")[0]))
    except Exception:
        sys.exit("❌ Clé illisible.")
    ok, resultat = signee.verifier_cle(cle, code_machine=str(charge.get("m", "")), public=public)
    print("Contenu :", json.dumps(charge, ensure_ascii=False, indent=2))
    print("Signature :", "✅ valide (émise avec votre clé privée)" if ok else f"❌ {resultat}")


def main():
    p = argparse.ArgumentParser(description="Outil vendeur : licences signées")
    sp = p.add_subparsers(dest="cmd", required=True)

    g = sp.add_parser("genkeys", help="créer la paire de clés (une seule fois)")
    g.add_argument("--dossier", default=".")
    g.set_defaults(fn=cmd_genkeys)

    e = sp.add_parser("emettre", help="émettre une licence pour un code machine")
    e.add_argument("--code", required=True, help="code machine du client")
    e.add_argument("--client", required=True, help="nom du client / de l'école")
    e.add_argument("--expire", help="date d'expiration AAAA-MM-JJ (omise = illimitée)")
    e.add_argument("--numero", help="numéro de licence / de facture (facultatif)")
    e.add_argument("--cle-privee", default=FICHIER_PRIVEE)
    e.set_defaults(fn=cmd_emettre)

    l = sp.add_parser("lire", help="contrôler le contenu d'une clé")
    l.add_argument("cle")
    l.add_argument("--cle-privee", default=FICHIER_PRIVEE)
    l.set_defaults(fn=cmd_lire)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()