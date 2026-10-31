import os
from django.core.exceptions import ValidationError

def validate_file_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
    if ext not in valid_extensions:
        raise ValidationError(
            f"Format non supporté. Formats acceptés : {', '.join(valid_extensions)}"
        )

def validate_file_size(value):
    limit = 5 * 1024 * 1024  # 5 Mo
    if value.size > limit:
        raise ValidationError("Le fichier dépasse la taille maximale de 5 Mo.")