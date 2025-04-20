"""web urls"""
from django.conf.urls.static import static
from django.conf import settings
from django.urls import include, path
import debug_toolbar

from . import views

urlpatterns = [
    path("pack/<int:packid>", views.pack_view),
    path("song/<int:songid>", views.chart_list),
    path("songs", views.list_all_songs),
    path("search", views.search),
    path("faq", views.faq_view),
    path("search/<str:search_type>/<str:search_query>", views.search),
    path("download/pack/<int:pack_id>/", views.download_pack, name="download_pack"),
    path("download/mirror/<int:pack_id>/", views.download_mirror, name="download_mirror"),
    path("", views.main),
    ]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += (path('__debug__/', include('debug_toolbar.urls')),)
