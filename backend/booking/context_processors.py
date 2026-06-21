def language(request):
    from django.utils import translation

    return {
        "CURRENT_LANGUAGE": translation.get_language(),
    }
