def sanitize_filename(filename):
    """
    Nettoie un nom de fichier pour ne garder que les caractères sûrs.
    (Lettres, chiffres, espaces, tirets et underscores).
    Utilisé par la commande /export.
    """
    return "".join([c for c in filename if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()