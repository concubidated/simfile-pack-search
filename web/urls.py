from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from . import views

urlpatterns = [
    path("packs/", views.pack_list),
    path("pack/<int:id>", views.song_list),
    path("song/<int:songid>", views.chart_list),
    path("songs", views.list_all_songs),
    ]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

