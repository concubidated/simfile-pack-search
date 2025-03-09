"""Api view"""

from django.http import JsonResponse

def hello_api():
    """Hello world"""
    return JsonResponse({'message': 'Hello from the API!'})
