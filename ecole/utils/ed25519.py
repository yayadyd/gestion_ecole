# ecole/utils/ed25519.py
"""
Ed25519 (RFC 8032) en Python pur — AUCUNE dépendance externe.

Sert à :
- VÉRIFIER une clé de licence dans l'application (clé publique seulement) ;
- SIGNER une licence dans l'outil du vendeur (outils_licence.py, clé privée).

Implémentation de référence de la RFC 8032 (domaine public). Elle n'est pas
« constant-time » : sans importance pour la vérification d'une signature
publique. Ne JAMAIS embarquer de clé privée dans l'application livrée.
"""
import hashlib

p = 2 ** 255 - 19
q = 2 ** 252 + 27742317777372353535851937790883648493


def _sha512(s):
    return hashlib.sha512(s).digest()


def _inv(x):
    return pow(x, p - 2, p)


_d = -121665 * _inv(121666) % p
_sqrt_m1 = pow(2, (p - 1) // 4, p)


def _sha512_modq(s):
    return int.from_bytes(_sha512(s), "little") % q


def _point_add(P, Q):
    A, B = (P[1] - P[0]) * (Q[1] - Q[0]) % p, (P[1] + P[0]) * (Q[1] + Q[0]) % p
    C, D = 2 * P[3] * Q[3] * _d % p, 2 * P[2] * Q[2] % p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F, G * H, F * G, E * H)


def _point_mul(s, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _point_add(Q, P)
        P = _point_add(P, P)
        s >>= 1
    return Q


def _point_equal(P, Q):
    if (P[0] * Q[2] - Q[0] * P[2]) % p != 0:
        return False
    if (P[1] * Q[2] - Q[1] * P[2]) % p != 0:
        return False
    return True


def _recover_x(y, sign):
    if y >= p:
        return None
    x2 = (y * y - 1) * _inv(_d * y * y + 1)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (p + 3) // 8, p)
    if (x * x - x2) % p != 0:
        x = x * _sqrt_m1 % p
    if (x * x - x2) % p != 0:
        return None
    if (x & 1) != sign:
        x = p - x
    return x


_g_y = 4 * _inv(5) % p
_g_x = _recover_x(_g_y, 0)
_G = (_g_x, _g_y, 1, _g_x * _g_y % p)


def _point_compress(P):
    zinv = _inv(P[2])
    x = P[0] * zinv % p
    y = P[1] * zinv % p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _point_decompress(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % p)


def _secret_expand(secret):
    if len(secret) != 32:
        raise ValueError("La clé privée doit faire 32 octets.")
    h = _sha512(secret)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= (1 << 254)
    return a, h[32:]


def secret_to_public(secret):
    """Clé publique (32 octets) correspondant à une clé privée (32 octets)."""
    a, _ = _secret_expand(secret)
    return _point_compress(_point_mul(a, _G))


def sign(secret, msg):
    """Signature (64 octets) de `msg` avec la clé privée `secret` (32 octets)."""
    a, prefix = _secret_expand(secret)
    A = _point_compress(_point_mul(a, _G))
    r = _sha512_modq(prefix + msg)
    Rs = _point_compress(_point_mul(r, _G))
    h = _sha512_modq(Rs + A + msg)
    s = (r + h * a) % q
    return Rs + int.to_bytes(s, 32, "little")


def verify(public, msg, signature):
    """True si `signature` (64 octets) est valide pour `msg` et la clé publique."""
    if len(public) != 32 or len(signature) != 64:
        return False
    A = _point_decompress(public)
    if not A:
        return False
    Rs = signature[:32]
    R = _point_decompress(Rs)
    if not R:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= q:
        return False
    h = _sha512_modq(Rs + public + msg)
    return _point_equal(_point_mul(s, _G), _point_add(R, _point_mul(h, A)))