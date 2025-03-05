from . import views
from django.urls import include, path

urlpatterns = [
    path('', views.hello_api, name='hello_api'),
]
